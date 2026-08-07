"""MCP-002: `capabilities.search` discovers native-tool and MCP-tool candidates
without loading schemas; `tools.describe` fetches one candidate's full schema
and activates it so it joins that session's context from the next compile on
— proven end to end against a real fixture MCP server and a real ContextCompiler
run through the agent run loop, not by asserting on the tool functions alone.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.mcp.fixtures import start_fake_mcp_server, stop_fake_mcp_server


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def _run_tool(client, tool_name: str, arguments: dict) -> dict:
    resp = await client.post(f"/api/v1/tools/{tool_name}/run", json={"arguments": arguments})
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": tool_name})
    return runs.json()[0]["result"]  # most-recent-first (ORDER BY created_at DESC)


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_mcp_server()
    try:
        yield info
    finally:
        await stop_fake_mcp_server(server, task)


@pytest.mark.asyncio
async def test_capabilities_search_and_tools_describe_are_registered_as_tools(client) -> None:
    resp = await client.get("/api/v1/tools")
    by_name = {t["name"]: t for t in resp.json()}
    assert by_name["capabilities.search"]["permission_class"] == "read"
    assert by_name["capabilities.search"]["parameters_schema"]["required"] == ["query"]
    assert by_name["tools.describe"]["permission_class"] == "read"
    assert set(by_name["tools.describe"]["parameters_schema"]["required"]) == {
        "session_id",
        "kind",
        "ref",
    }


@pytest.mark.asyncio
async def test_search_finds_native_tool_by_keyword(client) -> None:
    result = await _run_tool(client, "capabilities.search", {"query": "unchanged"})
    names = {c["name"] for c in result["candidates"]}
    assert "echo" in names
    echo = next(c for c in result["candidates"] if c["name"] == "echo")
    assert echo["kind"] == "native_tool"
    assert echo["ref"] == "echo"
    assert echo["trust_class"] == "read"
    assert echo["estimated_schema_tokens"] > 0

    # The meta-tools don't show up as results for themselves.
    assert "capabilities.search" not in names
    assert "tools.describe" not in names


@pytest.mark.asyncio
async def test_search_finds_mcp_tool_by_keyword(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    await client.post(f"/api/v1/mcp/servers/{server_id}/index")

    result = await _run_tool(client, "capabilities.search", {"query": "ticket"})
    names = {c["name"] for c in result["candidates"]}
    assert names == {"create_ticket"}
    candidate = result["candidates"][0]
    assert candidate["kind"] == "mcp_tool"
    assert candidate["trust_class"] == "network"

    # No JSON Schema body leaked into the compact search result.
    assert "schema" not in candidate
    assert "inputSchema" not in candidate


@pytest.mark.asyncio
async def test_search_with_empty_query_returns_everything(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    await client.post(f"/api/v1/mcp/servers/{server_id}/index")

    result = await _run_tool(client, "capabilities.search", {"query": ""})
    names = {c["name"] for c in result["candidates"]}
    assert {"echo", "search_docs", "create_ticket"} <= names


@pytest.mark.asyncio
async def test_describe_unknown_native_tool_fails_the_tool_run(client) -> None:
    resp = await client.post(
        "/api/v1/tools/tools.describe/run",
        json={
            "arguments": {
                "session_id": "ses_doesnotmatter",
                "kind": "native_tool",
                "ref": "does-not-exist",
            }
        },
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded"
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "tools.describe"})
    assert runs.json()[0]["status"] == "failed"
    assert "not found" in runs.json()[0]["error"]


async def _create_contact_and_session(client) -> str:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": ["builder"]})
    return session.json()["id"]


async def _tools_budget_for_latest_run(harness_app, session_id: str) -> int:
    events = await harness_app.events.replay(0)
    compiled = [
        e
        for e in events
        if e.type == "context.compiled" and e.context.get("session_id") == session_id
    ]
    assert compiled, "no context.compiled event recorded"
    return int(compiled[-1].payload["sections"]["tools"])


@pytest.mark.asyncio
async def test_tools_describe_activates_capability_for_next_compile_only(
    client, harness_app
) -> None:
    """DoD "Schema loads only when activated": the first turn's compile must not
    carry any tool schema cost; only after `tools.describe` activates one does a
    later turn's compile in the same session include it.
    """
    session_id = await _create_contact_and_session(client)

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder hi there"}
    )
    assert await _tools_budget_for_latest_run(harness_app, session_id) == 0

    describe_result = await _run_tool(
        client,
        "tools.describe",
        {"session_id": session_id, "kind": "native_tool", "ref": "echo"},
    )
    assert describe_result["name"] == "echo"
    assert describe_result["schema"]["required"] == ["text"]

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder hi again"}
    )
    assert await _tools_budget_for_latest_run(harness_app, session_id) > 0


@pytest.mark.asyncio
async def test_tools_describe_activates_an_mcp_tool_schema(
    client, harness_app, running_server
) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    indexed = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    entry_id = next(e["id"] for e in indexed.json() if e["tool_name"] == "search_docs")

    session_id = await _create_contact_and_session(client)

    describe_result = await _run_tool(
        client, "tools.describe", {"session_id": session_id, "kind": "mcp_tool", "ref": entry_id}
    )
    assert describe_result["name"] == "search_docs"
    assert describe_result["schema"]["required"] == ["query"]

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder go"}
    )
    assert resp.status_code == 200
    assert await _tools_budget_for_latest_run(harness_app, session_id) > 0


@pytest.mark.asyncio
async def test_activation_is_idempotent_across_repeated_describe_calls(client, harness_app) -> None:
    session_id = await _create_contact_and_session(client)
    for _ in range(3):
        await _run_tool(
            client,
            "tools.describe",
            {"session_id": session_id, "kind": "native_tool", "ref": "echo"},
        )

    activated = await harness_app.session_capabilities.list_for_session(session_id)
    assert len(activated) == 1
