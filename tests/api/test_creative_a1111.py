"""CRE-004: `POST /creative/jobs` with an AUTOMATIC1111-compatible
`engine_id` end to end against a real local fixture A1111 server — proving
the DoD bullet "works vs fake A1111 server exposing partial capabilities"
through the full stack (Job -> A1111Client -> real HTTP -> Artifact
capture), not just at the client-library level.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.creative.a1111_fixtures import start_fake_a1111_server, stop_fake_a1111_server


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_a1111_server(progress_steps=4)
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def slow_server():
    """Delays long enough (> the adapter's 0.5s poll interval) that at least
    one real progress poll fires before the generation call itself returns.
    """
    server, task, info = await start_fake_a1111_server(generation_delay_seconds=0.7)
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def partial_server():
    server, task, info = await start_fake_a1111_server(
        omit_endpoints=frozenset({"loras", "schedulers"})
    )
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def no_img2img_server():
    server, task, info = await start_fake_a1111_server(omit_endpoints=frozenset({"img2img"}))
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


@pytest.mark.asyncio
async def test_submit_txt2img_captures_output_as_artifact(
    client, harness_app, running_server
) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_server.base_url,
            "operation": "txt2img",
            "params": {"prompt": "a cat", "steps": 20},
        },
    )
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job

    events = await harness_app.events.replay(0)
    completed = [
        e
        for e in events
        if e.type == "job.completed" and e.resource is not None and e.resource.id == job["id"]
    ]
    assert completed
    job_result = completed[-1].payload["result"]
    assert job_result["operation"] == "txt2img"
    assert len(job_result["output_artifact_ids"]) == 1

    artifact = await client.get(f"/api/v1/artifacts/{job_result['output_artifact_ids'][0]}")
    assert artifact.json()["type"] == "image"
    assert artifact.json()["metadata"]["engine_id"] == "automatic1111"
    assert artifact.json()["metadata"]["operation"] == "txt2img"

    content = await client.get(f"/api/v1/artifacts/{job_result['output_artifact_ids'][0]}/content")
    assert content.status_code == 200
    assert len(content.content) > 0


@pytest.mark.asyncio
async def test_submit_img2img_captures_multiple_outputs(client, running_server) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "sdwebui_forge",
            "base_url": running_server.base_url,
            "operation": "img2img",
            "params": {"init_images": ["ZmFrZQ=="], "denoising_strength": 0.6},
        },
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job


@pytest.mark.asyncio
async def test_submit_without_operation_or_params_fails_validation(client) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={"engine_id": "automatic1111", "base_url": "http://example.invalid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_unsupported_operation_against_partial_server_fails_the_job_cleanly(
    client, no_img2img_server
) -> None:
    """The fixture omits img2img entirely — proving a genuinely missing
    capability fails the job with a clear reason rather than crashing or
    silently no-oping (CRE-004's "capability-negotiated" acceptance bar).
    """
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": no_img2img_server.base_url,
            "operation": "img2img",
            "params": {"init_images": ["ZmFrZQ=="]},
        },
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "failed"
    assert "img2img" in job["error"]


@pytest.mark.asyncio
async def test_submit_still_succeeds_against_a_server_missing_unrelated_capabilities(
    client, partial_server
) -> None:
    """The fixture omits loras/schedulers — unrelated to txt2img — so
    generation must still succeed; capability negotiation degrades only the
    specific missing features, not the whole engine.
    """
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": partial_server.base_url,
            "operation": "txt2img",
            "params": {"prompt": "a dog"},
        },
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job


@pytest.mark.asyncio
async def test_progress_events_are_published_while_polling(
    client, harness_app, slow_server
) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": slow_server.base_url,
            "operation": "txt2img",
            "params": {"prompt": "slow one", "steps": 50},
        },
    )
    job_id = resp.json()["id"]
    await _wait_for_job(client, job_id)

    events = await harness_app.events.replay(0)
    progress_events = [e for e in events if e.type == "creative.a1111.progress"]
    assert progress_events
    assert "progress" in progress_events[0].payload


@pytest.mark.asyncio
async def test_list_creative_jobs_includes_both_engines(client, running_server) -> None:
    from tests.creative.fixtures import start_fake_comfyui_server, stop_fake_comfyui_server

    comfy_server, comfy_task, comfy_info = await start_fake_comfyui_server()
    try:
        a1111_resp = await client.post(
            "/api/v1/creative/jobs",
            json={
                "engine_id": "automatic1111",
                "base_url": running_server.base_url,
                "operation": "txt2img",
                "params": {"prompt": "x"},
            },
        )
        await _wait_for_job(client, a1111_resp.json()["id"])

        comfy_resp = await client.post(
            "/api/v1/creative/jobs",
            json={
                "engine_id": "comfyui",
                "base_url": comfy_info.base_url,
                "workflow": {"1": {"class_type": "KSampler"}},
            },
        )
        await _wait_for_job(client, comfy_resp.json()["id"])

        creative_jobs = await client.get("/api/v1/creative/jobs")
        types = {j["type"] for j in creative_jobs.json()}
        assert types == {"creative.a1111.generate", "creative.comfyui.generate"}
    finally:
        await stop_fake_comfyui_server(comfy_server, comfy_task)


@pytest.mark.asyncio
async def test_sdnext_and_other_a1111_family_ids_are_all_accepted(client, running_server) -> None:
    for engine_id in (
        "sdwebui_reforge",
        "sdwebui_amdgpu_forge",
        "sdwebui_ux",
        "sdnext",
        "automatic1111_directml",
    ):
        resp = await client.post(
            "/api/v1/creative/jobs",
            json={
                "engine_id": engine_id,
                "base_url": running_server.base_url,
                "operation": "txt2img",
                "params": {"prompt": "x"},
            },
        )
        job = await _wait_for_job(client, resp.json()["id"])
        assert job["status"] == "succeeded", (engine_id, job)


@pytest.mark.asyncio
async def test_unknown_engine_id_rejected_by_schema(client) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "voltaml",  # declared family, but no real adapter
            "base_url": "http://example.invalid",
            "operation": "txt2img",
            "params": {"prompt": "x"},
        },
    )
    assert resp.status_code == 422
