"""CRE-003: `POST /creative/workflows` + `POST /creative/jobs` end to end
against a real local fixture ComfyUI server — proving the DoD bullet
"ComfyUI deep adapter can submit workflow and capture output" through the
full stack (Job -> ComfyUIClient -> real HTTP+WS -> Artifact capture), not
just at the client-library level.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.creative.fixtures import start_fake_comfyui_server, stop_fake_comfyui_server

_WORKFLOW = {"1": {"class_type": "KSampler", "inputs": {}}}


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_comfyui_server()
    try:
        yield info
    finally:
        await stop_fake_comfyui_server(server, task)


@pytest.fixture
async def failing_server():
    server, task, info = await start_fake_comfyui_server(fail_node="1")
    try:
        yield info
    finally:
        await stop_fake_comfyui_server(server, task)


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


@pytest.mark.asyncio
async def test_create_and_list_workflows(client) -> None:
    created = await client.post(
        "/api/v1/creative/workflows",
        json={"engine_id": "comfyui", "display_name": "my-workflow.json", "graph": _WORKFLOW},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["type"] == "workflow"
    assert body["display_name"] == "my-workflow.json"
    assert body["mime_type"] == "application/json"

    listed = await client.get("/api/v1/creative/workflows")
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]

    # The workflow content is fetched separately, never inlined into the
    # catalog listing (ART-001's lazy-content rule; SPEC's "MUST NOT be
    # injected into LLM context by default").
    assert "graph" not in listed.json()[0]


@pytest.mark.asyncio
async def test_create_workflow_rejects_unknown_engine(client) -> None:
    resp = await client.post(
        "/api/v1/creative/workflows",
        json={"engine_id": "does-not-exist", "display_name": "x", "graph": {}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_creative_job_rejects_non_comfyui_engine(client) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={"engine_id": "automatic1111", "base_url": "http://example.invalid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_inline_workflow_captures_output_as_artifacts(
    client, harness_app, running_server
) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_server.base_url,
            "workflow": _WORKFLOW,
        },
    )
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job

    # Job itself carries no result field (JOB-001) — the generation's summary
    # (prompt_id/artifact ids) only exists in the job.completed event payload.
    events = await harness_app.events.replay(0)
    completed = [
        e
        for e in events
        if e.type == "job.completed" and e.resource is not None and e.resource.id == job["id"]
    ]
    assert completed
    job_result = completed[-1].payload["result"]

    assert job_result["prompt_id"]
    assert job_result["workflow_artifact_id"]
    assert len(job_result["output_artifact_ids"]) == 1

    workflow_artifact = await client.get(f"/api/v1/artifacts/{job_result['workflow_artifact_id']}")
    assert workflow_artifact.json()["type"] == "workflow"

    output_artifact_id = job_result["output_artifact_ids"][0]
    output_artifact = await client.get(f"/api/v1/artifacts/{output_artifact_id}")
    assert output_artifact.json()["type"] == "image"
    assert output_artifact.json()["metadata"]["engine_id"] == "comfyui"
    assert output_artifact.json()["metadata"]["prompt_id"] == job_result["prompt_id"]

    content = await client.get(f"/api/v1/artifacts/{output_artifact_id}/content")
    assert content.status_code == 200
    assert len(content.content) > 0


@pytest.mark.asyncio
async def test_submit_via_workflow_artifact_reference(client, running_server) -> None:
    stored = await client.post(
        "/api/v1/creative/workflows",
        json={"engine_id": "comfyui", "display_name": "wf.json", "graph": _WORKFLOW},
    )
    workflow_artifact_id = stored.json()["id"]

    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_server.base_url,
            "workflow_artifact_id": workflow_artifact_id,
        },
    )
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job


@pytest.mark.asyncio
async def test_submit_without_workflow_or_reference_fails_validation(client) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={"engine_id": "comfyui", "base_url": "http://example.invalid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_execution_error_fails_the_job_cleanly(client, failing_server) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": failing_server.base_url,
            "workflow": _WORKFLOW,
        },
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "failed"
    assert "simulated failure" in job["error"]


@pytest.mark.asyncio
async def test_list_creative_jobs_only_includes_comfyui_generations(client, running_server) -> None:
    await client.post("/api/v1/tools/echo/run", json={"arguments": {"text": "unrelated"}})
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_server.base_url,
            "workflow": _WORKFLOW,
        },
    )
    await _wait_for_job(client, resp.json()["id"])

    creative_jobs = await client.get("/api/v1/creative/jobs")
    assert len(creative_jobs.json()) == 1
    assert creative_jobs.json()[0]["type"] == "creative.comfyui.generate"


@pytest.mark.asyncio
async def test_progress_events_are_published_during_generation(
    client, harness_app, running_server
) -> None:
    resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_server.base_url,
            "workflow": _WORKFLOW,
        },
    )
    job_id = resp.json()["id"]
    await _wait_for_job(client, job_id)

    events = await harness_app.events.replay(0)
    comfyui_events = [e for e in events if e.type.startswith("creative.comfyui.")]
    types = {e.type for e in comfyui_events}
    assert "creative.comfyui.executing" in types
    assert "creative.comfyui.execution_success" in types
