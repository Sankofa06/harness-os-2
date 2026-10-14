"""CRE-008's acceptance bar (SPEC/DEFINITION_OF_DONE.md "Batch checkpoint/
profile comparison works with deterministic fixture"): one prompt across N
checkpoints/profiles, a controlled seed, sequential/parallel scheduling,
capacity-aware placement across candidate engine instances, and a result
manifest artifact -- proven end to end against real local fixture A1111
servers, not mocks.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from tests.creative.a1111_fixtures import start_fake_a1111_server, stop_fake_a1111_server


@pytest.fixture
async def server_a():
    server, task, info = await start_fake_a1111_server()
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def server_b():
    server, task, info = await start_fake_a1111_server()
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def slow_server():
    server, task, info = await start_fake_a1111_server(generation_delay_seconds=1.0)
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


async def _state(server) -> dict:
    async with httpx.AsyncClient() as http:
        return (await http.get(f"{server.base_url}/__state__")).json()


async def _job_result(harness_app, job_id: str) -> dict:
    events = await harness_app.events.replay(0)
    completed = [
        e
        for e in events
        if e.type == "job.completed" and e.resource is not None and e.resource.id == job_id
    ]
    assert completed, f"no job.completed event found for job {job_id}"
    return completed[-1].payload["result"]


@pytest.mark.asyncio
async def test_sequential_batch_compares_profiles_and_a_raw_checkpoint_with_shared_seed(
    client, harness_app, server_a
) -> None:
    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={
            "name": "batch-profile-one",
            "engine_selector": "automatic1111",
            "checkpoint": "profile-checkpoint.safetensors",
        },
    )
    profile_id = profile_resp.json()["id"]

    job_resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [server_a.base_url],
            "prompt": "a cat",
            "seed": 42,
            "scheduling": "sequential",
            "cells": [
                {"profile_id": profile_id},
                {"checkpoint": "raw-checkpoint.safetensors"},
            ],
        },
    )
    assert job_resp.status_code == 202
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    result = await _job_result(harness_app, finished["id"])
    assert len(result["cells"]) == 2
    assert all(c["status"] == "succeeded" for c in result["cells"])
    assert all(c["seed"] == 42 for c in result["cells"])
    assert result["cells"][0]["checkpoint"] == "profile-checkpoint.safetensors"
    assert result["cells"][1]["checkpoint"] == "raw-checkpoint.safetensors"
    assert len(result["cells"][0]["output_artifact_ids"]) == 1
    assert len(result["cells"][1]["output_artifact_ids"]) == 1

    state = await _state(server_a)
    bodies = state["txt2img_bodies"]
    assert len(bodies) == 2
    assert bodies[0]["seed"] == 42
    assert bodies[0]["override_settings"] == {
        "sd_model_checkpoint": "profile-checkpoint.safetensors"
    }
    assert bodies[1]["override_settings"] == {"sd_model_checkpoint": "raw-checkpoint.safetensors"}

    manifest_resp = await client.get(f"/api/v1/artifacts/{result['manifest_artifact_id']}/content")
    assert manifest_resp.status_code == 200
    manifest = json.loads(manifest_resp.content)
    assert manifest["prompt"] == "a cat"
    assert manifest["seed"] == 42
    assert len(manifest["cells"]) == 2


@pytest.mark.asyncio
async def test_parallel_batch_distributes_cells_across_candidate_base_urls(
    client, harness_app, server_a, server_b
) -> None:
    job_resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [server_a.base_url, server_b.base_url],
            "prompt": "a dog",
            "seed": 7,
            "scheduling": "parallel",
            "cells": [
                {"checkpoint": "ckpt-1.safetensors"},
                {"checkpoint": "ckpt-2.safetensors"},
                {"checkpoint": "ckpt-3.safetensors"},
                {"checkpoint": "ckpt-4.safetensors"},
            ],
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    cells = (await _job_result(harness_app, finished["id"]))["cells"]
    assert all(c["status"] == "succeeded" for c in cells)
    base_urls_used = [c["base_url"] for c in cells]
    assert set(base_urls_used) == {server_a.base_url, server_b.base_url}
    # Capacity-aware placement: 4 cells over 2 equally-idle candidates lands
    # 2 on each, not all 4 piled onto one.
    assert base_urls_used.count(server_a.base_url) == 2
    assert base_urls_used.count(server_b.base_url) == 2


@pytest.mark.asyncio
async def test_one_failing_cell_does_not_abort_the_rest_of_the_batch(
    client, harness_app, server_a
) -> None:
    job_resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [server_a.base_url],
            "prompt": "a bird",
            "seed": 1,
            "cells": [
                {"profile_id": "prof_doesnotexist"},
                {"checkpoint": "real-checkpoint.safetensors"},
            ],
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    cells = (await _job_result(harness_app, finished["id"]))["cells"]
    assert cells[0]["status"] == "failed"
    assert cells[0]["error"]
    assert cells[1]["status"] == "succeeded"
    assert len(cells[1]["output_artifact_ids"]) == 1


@pytest.mark.asyncio
async def test_canceling_the_batch_job_stops_in_flight_generations(
    client, harness_app, slow_server
) -> None:
    job_resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [slow_server.base_url],
            "prompt": "x",
            "seed": 1,
            "scheduling": "parallel",
            "cells": [{"checkpoint": "a.safetensors"}, {"checkpoint": "b.safetensors"}],
        },
    )
    job_id = job_resp.json()["id"]
    await asyncio.sleep(0.1)
    canceled = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert canceled.status_code == 200

    finished = await _wait_for_job(client, job_id)
    assert finished["status"] == "canceled"


@pytest.mark.asyncio
async def test_comfyui_is_rejected_batch_is_a1111_only(client, server_a) -> None:
    resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "comfyui",
            "base_urls": [server_a.base_url],
            "prompt": "x",
            "seed": 1,
            "cells": [{"checkpoint": "a.safetensors"}],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cell_with_both_profile_and_checkpoint_rejected(client, server_a) -> None:
    resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [server_a.base_url],
            "prompt": "x",
            "seed": 1,
            "cells": [{"profile_id": "prof_x", "checkpoint": "a.safetensors"}],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cell_with_neither_profile_nor_checkpoint_rejected(client, server_a) -> None:
    resp = await client.post(
        "/api/v1/creative/batch",
        json={
            "engine_id": "automatic1111",
            "base_urls": [server_a.base_url],
            "prompt": "x",
            "seed": 1,
            "cells": [{}],
        },
    )
    assert resp.status_code == 422
