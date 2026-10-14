"""CRE-007's acceptance bar: a Creative Profile actually drives a real
generation call against a fixture engine — proven end to end (API ->
profile merge -> real HTTP to a fixture A1111/ComfyUI server), not just at
the merge-function level.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from tests.creative.a1111_fixtures import start_fake_a1111_server, stop_fake_a1111_server
from tests.creative.fixtures import start_fake_comfyui_server, stop_fake_comfyui_server


@pytest.fixture
async def running_a1111_server():
    server, task, info = await start_fake_a1111_server()
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def running_comfyui_server():
    server, task, info = await start_fake_comfyui_server()
    try:
        yield info
    finally:
        await stop_fake_comfyui_server(server, task)


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
async def test_a1111_profile_drives_checkpoint_vae_sampler_and_loras(
    client, harness_app, running_a1111_server
) -> None:
    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={
            "name": "app-icon-preset",
            "engine_selector": "automatic1111",
            "checkpoint": "icon-model.safetensors",
            "vae": "icon-vae.safetensors",
            "sampler": "DPM++ 2M",
            "scheduler": "Karras",
            "loras": ["icon-style"],
            "settings": {"width": 1024, "height": 1024},
        },
    )
    assert profile_resp.status_code == 201
    profile = profile_resp.json()

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_a1111_server.base_url,
            "operation": "txt2img",
            "profile_id": profile["id"],
            "params": {"prompt": "an app icon"},
        },
    )
    assert job_resp.status_code == 202
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    async with httpx.AsyncClient() as http:
        state = (await http.get(f"{running_a1111_server.base_url}/__state__")).json()
    sent = state["last_txt2img_body"]
    assert sent["prompt"] == "an app icon<lora:icon-style:1.0>"
    assert sent["override_settings"] == {
        "sd_model_checkpoint": "icon-model.safetensors",
        "sd_vae": "icon-vae.safetensors",
    }
    assert sent["sampler_name"] == "DPM++ 2M"
    assert sent["scheduler"] == "Karras"


@pytest.mark.asyncio
async def test_explicit_request_params_win_over_profile_defaults(
    client, harness_app, running_a1111_server
) -> None:
    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={
            "name": "override-test",
            "engine_selector": "automatic1111",
            "checkpoint": "profile-model.safetensors",
            "sampler": "Euler",
        },
    )
    profile = profile_resp.json()

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_a1111_server.base_url,
            "operation": "txt2img",
            "profile_id": profile["id"],
            "params": {
                "prompt": "a cat",
                "sampler_name": "Euler a",
                "override_settings": {"sd_model_checkpoint": "request-model.safetensors"},
            },
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded"

    async with httpx.AsyncClient() as http:
        state = (await http.get(f"{running_a1111_server.base_url}/__state__")).json()
    sent = state["last_txt2img_body"]
    assert sent["sampler_name"] == "Euler a"
    assert sent["override_settings"] == {"sd_model_checkpoint": "request-model.safetensors"}


@pytest.mark.asyncio
async def test_comfyui_profile_supplies_default_workflow(
    client, harness_app, running_comfyui_server
) -> None:
    workflow_resp = await client.post(
        "/api/v1/creative/workflows",
        json={
            "engine_id": "comfyui",
            "display_name": "profile-workflow",
            "graph": {"1": {"class_type": "KSampler", "inputs": {}}},
        },
    )
    assert workflow_resp.status_code == 201
    workflow_artifact_id = workflow_resp.json()["id"]

    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={
            "name": "comfyui-preset",
            "engine_selector": "comfyui",
            "workflow_artifact_id": workflow_artifact_id,
        },
    )
    assert profile_resp.status_code == 201
    profile = profile_resp.json()

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_comfyui_server.base_url,
            "profile_id": profile["id"],
        },
    )
    assert job_resp.status_code == 202
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished


@pytest.mark.asyncio
async def test_profile_engine_mismatch_rejected(client, harness_app, running_a1111_server) -> None:
    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={"name": "comfyui-only", "engine_selector": "comfyui"},
    )
    profile = profile_resp.json()

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_a1111_server.base_url,
            "operation": "txt2img",
            "profile_id": profile["id"],
            "params": {"prompt": "x"},
        },
    )
    assert job_resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_profile_name_rejected(client) -> None:
    body = {"name": "dup-profile", "engine_selector": "comfyui"}
    first = await client.post("/api/v1/creative/profiles", json=body)
    assert first.status_code == 201
    second = await client.post("/api/v1/creative/profiles", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_unknown_engine_selector_rejected(client) -> None:
    resp = await client.post(
        "/api/v1/creative/profiles",
        json={"name": "bad-engine", "engine_selector": "not-a-real-engine"},
    )
    assert resp.status_code == 422
