import asyncio

import pytest


@pytest.mark.asyncio
async def test_list_jobs_empty_initially(client) -> None:
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_job_lifecycle_via_manager_visible_over_api(client, harness_app) -> None:
    async def work(handle):
        await asyncio.sleep(10)

    job = await harness_app.job_manager.submit("demo", work)

    resp = await client.get(f"/api/v1/jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("queued", "running")

    cancel_resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert cancel_resp.status_code == 200

    for _ in range(50):
        check = await client.get(f"/api/v1/jobs/{job.id}")
        if check.json()["status"] == "canceled":
            break
        await asyncio.sleep(0.01)
    assert check.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_cancel_missing_job_404s(client) -> None:
    resp = await client.post("/api/v1/jobs/job_doesnotexist00000000000/cancel")
    assert resp.status_code == 404
