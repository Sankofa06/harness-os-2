import asyncio

import pytest


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


@pytest.mark.asyncio
async def test_list_tools_includes_builtin_echo(client) -> None:
    resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    by_name = {t["name"]: t for t in resp.json()}
    assert "echo" in by_name
    assert by_name["echo"]["permission_class"] == "read"
    assert by_name["echo"]["parameters_schema"]["required"] == ["text"]


@pytest.mark.asyncio
async def test_run_echo_tool_via_job_records_tool_run_and_events(client, harness_app) -> None:
    run_resp = await client.post(
        "/api/v1/tools/echo/run", json={"arguments": {"text": "hello tool lifecycle"}}
    )
    assert run_resp.status_code == 202
    job = await _wait_for_job(client, run_resp.json()["id"])
    assert job["status"] == "succeeded"

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "echo"})
    assert len(runs.json()) == 1
    tool_run_id = runs.json()[0]["id"]

    fetched = await client.get(f"/api/v1/tools/runs/{tool_run_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["tool_name"] == "echo"
    assert body["status"] == "succeeded"
    assert body["permission_class"] == "read"
    assert body["result"] == {"text": "hello tool lifecycle"}
    assert body["finished_at"] is not None

    events = await harness_app.events.replay(0)
    event_types = [e.type for e in events if e.context.get("tool_run_id") == tool_run_id]
    assert event_types == ["tool.requested", "tool.started", "tool.completed"]


@pytest.mark.asyncio
async def test_run_unknown_tool_returns_not_found(client) -> None:
    resp = await client.post("/api/v1/tools/does-not-exist/run", json={"arguments": {}})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_tool_with_invalid_arguments_fails_the_job(client) -> None:
    run_resp = await client.post("/api/v1/tools/echo/run", json={"arguments": {}})
    assert run_resp.status_code == 202
    job = await _wait_for_job(client, run_resp.json()["id"])
    assert job["status"] == "failed"
    assert "invalid arguments" in job["error"]

    # No ToolRun should have been persisted for arguments that never passed validation.
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "echo"})
    assert runs.json() == []


@pytest.mark.asyncio
async def test_list_tool_runs_filters_by_tool_name(client) -> None:
    run_resp = await client.post("/api/v1/tools/echo/run", json={"arguments": {"text": "x"}})
    await _wait_for_job(client, run_resp.json()["id"])

    matching = await client.get("/api/v1/tools/runs", params={"tool_name": "echo"})
    assert len(matching.json()) == 1
    assert matching.json()[0]["tool_name"] == "echo"

    other = await client.get("/api/v1/tools/runs", params={"tool_name": "nonexistent-tool"})
    assert other.json() == []
