import asyncio

import pytest


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def _create_contact(client, handle: str, role_id: str | None = None) -> dict:
    body = {
        "handle": handle,
        "display_name": handle.title(),
        "binding": {"provider": "fake", "model": "fake-mini"},
    }
    if role_id:
        body["role_id"] = role_id
    resp = await client.post("/api/v1/contacts", json=body)
    return resp.json()


@pytest.mark.asyncio
async def test_agents_delegate_is_registered_as_a_tool(client) -> None:
    resp = await client.get("/api/v1/tools")
    by_name = {t["name"]: t for t in resp.json()}
    assert "agents.delegate" in by_name
    assert by_name["agents.delegate"]["permission_class"] == "execute"
    assert set(by_name["agents.delegate"]["parameters_schema"]["required"]) == {
        "session_id",
        "target_handle",
        "message",
        "parent_run_id",
    }


@pytest.mark.asyncio
async def test_delegate_spawns_a_run_for_the_target_contact(client, harness_app) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    await _create_contact(client, "orchestrator")
    implementer = await _create_contact(client, "implementer")
    session = await client.post(
        "/api/v1/sessions",
        json={"title": "t", "contacts": ["orchestrator", "implementer"]},
    )
    session_id = session.json()["id"]

    # A direct @mention creates the orchestrator's own Run first, giving the
    # delegate tool call a real parent_run_id to attribute the delegation to.
    kickoff = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@orchestrator start"}
    )
    parent_run_id = kickoff.json()["runs"][0]["run_id"]

    delegate_resp = await client.post(
        "/api/v1/tools/agents.delegate/run",
        json={
            "arguments": {
                "session_id": session_id,
                "target_handle": "implementer",
                "message": "please implement the login form",
                "parent_run_id": parent_run_id,
            }
        },
    )
    assert delegate_resp.status_code == 202
    job = await _wait_for_job(client, delegate_resp.json()["id"])
    assert job["status"] == "succeeded"

    tool_runs = await client.get("/api/v1/tools/runs", params={"tool_name": "agents.delegate"})
    assert len(tool_runs.json()) == 1
    result = tool_runs.json()[0]["result"]
    assert result["contact_handle"] == "implementer"
    assert result["status"] == "succeeded"
    assert "login form" in result["content"].lower()

    # The delegated run is real: a second, independent Run exists for
    # `implementer`, with parent_run_id pointing at the orchestrator's Run.
    delegated_run = await harness_app.runs.get(result["run_id"])
    assert delegated_run.contact_id == implementer["id"]
    assert delegated_run.parent_run_id == parent_run_id
    assert delegated_run.status == "succeeded"

    # The delegation instruction is visible in the shared session transcript.
    history = await harness_app.messages.list_for_session(session_id)
    assert any("please implement the login form" in m.content for m in history)

    events = await harness_app.events.replay(0)
    spawned = [e for e in events if e.type == "agent.spawned"]
    assert any(e.resource is not None and e.resource.id == result["run_id"] for e in spawned)


@pytest.mark.asyncio
async def test_delegate_to_unknown_contact_fails_the_tool_run(client) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    await _create_contact(client, "orchestrator")
    session = await client.post(
        "/api/v1/sessions", json={"title": "t", "contacts": ["orchestrator"]}
    )
    session_id = session.json()["id"]
    kickoff = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@orchestrator start"}
    )
    parent_run_id = kickoff.json()["runs"][0]["run_id"]

    delegate_resp = await client.post(
        "/api/v1/tools/agents.delegate/run",
        json={
            "arguments": {
                "session_id": session_id,
                "target_handle": "does-not-exist",
                "message": "hello?",
                "parent_run_id": parent_run_id,
            }
        },
    )
    job = await _wait_for_job(client, delegate_resp.json()["id"])
    assert job["status"] == "succeeded"

    tool_runs = await client.get("/api/v1/tools/runs", params={"tool_name": "agents.delegate"})
    assert tool_runs.json()[0]["status"] == "failed"
    assert "not found" in tool_runs.json()[0]["error"]


@pytest.mark.asyncio
async def test_parallel_delegation_to_two_contacts_runs_concurrently(client) -> None:
    """Plan -> review + implement in parallel: the orchestrator delegates to two
    contacts via two concurrent tool calls, matching how AGT-007 already proved
    concurrent @mention fan-out.
    """
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    await _create_contact(client, "orchestrator")
    await _create_contact(client, "reviewer")
    await _create_contact(client, "implementer")
    session = await client.post(
        "/api/v1/sessions",
        json={"title": "t", "contacts": ["orchestrator", "reviewer", "implementer"]},
    )
    session_id = session.json()["id"]
    kickoff = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@orchestrator plan"}
    )
    parent_run_id = kickoff.json()["runs"][0]["run_id"]

    async def delegate_to(handle: str) -> dict:
        resp = await client.post(
            "/api/v1/tools/agents.delegate/run",
            json={
                "arguments": {
                    "session_id": session_id,
                    "target_handle": handle,
                    "message": f"please handle the {handle} step",
                    "parent_run_id": parent_run_id,
                }
            },
        )
        job = await _wait_for_job(client, resp.json()["id"])
        assert job["status"] == "succeeded"
        return job

    await asyncio.gather(delegate_to("reviewer"), delegate_to("implementer"))

    tool_runs = await client.get("/api/v1/tools/runs", params={"tool_name": "agents.delegate"})
    handles = {r["result"]["contact_handle"] for r in tool_runs.json()}
    assert handles == {"reviewer", "implementer"}
    assert all(r["result"]["status"] == "succeeded" for r in tool_runs.json())


@pytest.mark.asyncio
async def test_session_graph_reflects_a_delegation(client) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    await _create_contact(client, "orchestrator")
    await _create_contact(client, "implementer")
    session = await client.post(
        "/api/v1/sessions",
        json={"title": "t", "contacts": ["orchestrator", "implementer"]},
    )
    session_id = session.json()["id"]

    empty_graph = await client.get(f"/api/v1/sessions/{session_id}/graph")
    assert empty_graph.json() == {"nodes": [], "edges": []}

    kickoff = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@orchestrator start"}
    )
    parent_run_id = kickoff.json()["runs"][0]["run_id"]

    delegate_resp = await client.post(
        "/api/v1/tools/agents.delegate/run",
        json={
            "arguments": {
                "session_id": session_id,
                "target_handle": "implementer",
                "message": "build the thing",
                "parent_run_id": parent_run_id,
            }
        },
    )
    await _wait_for_job(client, delegate_resp.json()["id"])

    graph = (await client.get(f"/api/v1/sessions/{session_id}/graph")).json()
    node_ids = {n["id"] for n in graph["nodes"]}
    node_types = {n["id"]: n["type"] for n in graph["nodes"]}
    assert "user" in node_ids
    assert node_types["user"] == "user"

    contact_nodes = {n["id"]: n for n in graph["nodes"] if n["type"] == "contact"}
    assert len(contact_nodes) == 2
    labels = {n["label"] for n in contact_nodes.values()}
    assert labels == {"@orchestrator", "@implementer"}

    edge_types = [e["type"] for e in graph["edges"]]
    assert edge_types.count("message") == 1
    assert edge_types.count("delegation") == 1

    delegation_edge = next(e for e in graph["edges"] if e["type"] == "delegation")
    message_edge = next(e for e in graph["edges"] if e["type"] == "message")
    assert message_edge["source"] == "user"
    assert delegation_edge["source"] == message_edge["target"]


@pytest.mark.asyncio
async def test_session_graph_for_unknown_session_404s(client) -> None:
    resp = await client.get("/api/v1/sessions/ses_doesnotexist/graph")
    assert resp.status_code == 404
