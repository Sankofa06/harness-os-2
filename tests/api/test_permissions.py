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


async def _wait_for_pending_run(client, *, timeout_seconds: float = 2.0) -> str:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        pending = await client.get("/api/v1/permissions/pending")
        if pending.json():
            return pending.json()[0]
        await asyncio.sleep(0.01)
    raise AssertionError("no tool run became pending_approval in time")


@pytest.mark.asyncio
async def test_list_policies_returns_all_ten_classes_with_defaults(client) -> None:
    resp = await client.get("/api/v1/permissions/policies")
    assert resp.status_code == 200
    by_class = {p["permission_class"]: p["policy"] for p in resp.json()}
    assert by_class == {
        "read": "allow",
        "write": "ask",
        "execute": "ask",
        "network": "ask",
        "git": "ask",
        "process": "ask",
        "model_lifecycle": "allow",
        "creative_generation": "ask",
        "training": "ask",
        "destructive": "deny",
    }


@pytest.mark.asyncio
async def test_set_policy_overrides_the_default(client) -> None:
    updated = await client.put("/api/v1/permissions/policies/destructive", json={"policy": "ask"})
    assert updated.status_code == 200
    assert updated.json() == {"permission_class": "destructive", "policy": "ask"}

    listed = await client.get("/api/v1/permissions/policies")
    by_class = {p["permission_class"]: p["policy"] for p in listed.json()}
    assert by_class["destructive"] == "ask"


@pytest.mark.asyncio
async def test_immediate_allow_decision_is_logged(client) -> None:
    run_resp = await client.post("/api/v1/tools/echo/run", json={"arguments": {"text": "hi"}})
    await _wait_for_job(client, run_resp.json()["id"])

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "echo"})
    run_id = runs.json()[0]["id"]

    decisions = await client.get("/api/v1/permissions/decisions", params={"tool_run_id": run_id})
    assert decisions.status_code == 200
    logged = decisions.json()
    assert len(logged) == 1
    assert logged[0]["permission_class"] == "read"
    assert logged[0]["policy"] == "allow"
    assert logged[0]["outcome"] == "allow"
    assert logged[0]["decided_by"] is None


@pytest.mark.asyncio
async def test_ask_policy_blocks_until_approved(client) -> None:
    await client.put("/api/v1/permissions/policies/read", json={"policy": "ask"})

    run_resp = await client.post(
        "/api/v1/tools/echo/run", json={"arguments": {"text": "needs approval"}}
    )
    job_id = run_resp.json()["id"]

    run_id = await _wait_for_pending_run(client)
    tool_run = await client.get(f"/api/v1/tools/runs/{run_id}")
    assert tool_run.json()["status"] == "pending_approval"

    # The Job is still running (or about to be) — approval hasn't landed yet.
    still_running = await client.get(f"/api/v1/jobs/{job_id}")
    assert still_running.json()["status"] in ("queued", "running")

    approved = await client.post(
        f"/api/v1/permissions/decisions/{run_id}/approve", json={"decided_by": "test-operator"}
    )
    assert approved.status_code == 200

    job = await _wait_for_job(client, job_id)
    assert job["status"] == "succeeded"

    final = await client.get(f"/api/v1/tools/runs/{run_id}")
    assert final.json()["status"] == "succeeded"
    assert final.json()["result"] == {"text": "needs approval"}

    decisions = await client.get("/api/v1/permissions/decisions", params={"tool_run_id": run_id})
    assert decisions.json() == [
        {
            "id": decisions.json()[0]["id"],
            "tool_run_id": run_id,
            "permission_class": "read",
            "policy": "ask",
            "outcome": "allow",
            "decided_by": "test-operator",
            "created_at": decisions.json()[0]["created_at"],
        }
    ]

    pending_after = await client.get("/api/v1/permissions/pending")
    assert run_id not in pending_after.json()


@pytest.mark.asyncio
async def test_ask_policy_rejected_denies_the_run(client) -> None:
    await client.put("/api/v1/permissions/policies/read", json={"policy": "ask"})

    run_resp = await client.post("/api/v1/tools/echo/run", json={"arguments": {"text": "no"}})
    job_id = run_resp.json()["id"]

    run_id = await _wait_for_pending_run(client)
    rejected = await client.post(f"/api/v1/permissions/decisions/{run_id}/reject", json={})
    assert rejected.status_code == 200

    job = await _wait_for_job(client, job_id)
    assert job["status"] == "succeeded"  # the Job succeeds; the *tool run* was denied

    final = await client.get(f"/api/v1/tools/runs/{run_id}")
    assert final.json()["status"] == "denied"
    assert final.json()["result"] is None


@pytest.mark.asyncio
async def test_deny_policy_prevents_execution_without_asking(client) -> None:
    await client.put("/api/v1/permissions/policies/read", json={"policy": "deny"})

    run_resp = await client.post("/api/v1/tools/echo/run", json={"arguments": {"text": "nope"}})
    job = await _wait_for_job(client, run_resp.json()["id"])
    assert job["status"] == "succeeded"

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "echo"})
    assert runs.json()[0]["status"] == "denied"

    pending = await client.get("/api/v1/permissions/pending")
    assert pending.json() == []


@pytest.mark.asyncio
async def test_approving_a_run_with_no_pending_approval_returns_error(client) -> None:
    resp = await client.post("/api/v1/permissions/decisions/trun_doesnotexist/approve", json={})
    assert resp.status_code in (404, 422)
