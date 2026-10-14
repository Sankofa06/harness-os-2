"""CRE-009's acceptance bar (DoD: "Output becomes Artifact with
provenance"): every AUTOMATIC1111-compatible generation's output Artifact
carries a full provenance record (engine/host/checkpoint+hash/VAE/LoRAs/
prompt/seed/sampler/dimensions/steps/CFG/duration/timestamp), with the
checkpoint hash resolved against CRE-006's asset catalog when a matching
file has been scanned. ComfyUI's provenance is deliberately lighter
(engine/host/workflow reference/duration/timestamp only) -- proven here
too, so that scope boundary stays honest rather than silently narrowing.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from tests.creative.a1111_fixtures import start_fake_a1111_server, stop_fake_a1111_server
from tests.creative.fixtures import start_fake_comfyui_server, stop_fake_comfyui_server
from tests.hosts.fixtures import RunningSSHServer, start_test_ssh_server


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


@pytest.fixture
async def running_ssh_server():
    server, info = await start_test_ssh_server()
    try:
        yield info
    finally:
        server.close()
        await server.wait_closed()


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
async def test_a1111_output_artifact_carries_full_provenance(
    client, harness_app, running_a1111_server
) -> None:
    profile_resp = await client.post(
        "/api/v1/creative/profiles",
        json={
            "name": "provenance-profile",
            "engine_selector": "automatic1111",
            "checkpoint": "provenance-checkpoint.safetensors",
            "vae": "provenance-vae.safetensors",
            "sampler": "DPM++ 2M",
            "scheduler": "Karras",
            "loras": ["style-a"],
        },
    )
    profile_id = profile_resp.json()["id"]

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_a1111_server.base_url,
            "operation": "txt2img",
            "profile_id": profile_id,
            "params": {
                "prompt": "a lighthouse",
                "negative_prompt": "blurry",
                "width": 512,
                "height": 768,
                "steps": 30,
                "cfg_scale": 7.5,
            },
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    events = await harness_app.events.replay(0)
    completed = [e for e in events if e.type == "job.completed" and e.resource.id == finished["id"]]
    artifact_id = completed[-1].payload["result"]["output_artifact_ids"][0]

    artifact = (await client.get(f"/api/v1/artifacts/{artifact_id}")).json()
    meta = artifact["metadata"]
    assert meta["engine_id"] == "automatic1111"
    assert meta["host"] == running_a1111_server.base_url
    assert meta["profile_id"] == profile_id
    assert meta["checkpoint"] == "provenance-checkpoint.safetensors"
    assert meta["vae"] == "provenance-vae.safetensors"
    assert meta["sampler"] == "DPM++ 2M"
    assert meta["scheduler"] == "Karras"
    assert meta["loras"] == ["style-a"]
    assert meta["prompt"] == "a lighthouse"  # lora tag stripped back out
    assert meta["negative_prompt"] == "blurry"
    assert meta["width"] == 512
    assert meta["height"] == 768
    assert meta["steps"] == 30
    assert meta["cfg_scale"] == 7.5
    assert meta["seed"] == 42  # the fixture's fixed "resolved" seed from its info field
    assert meta["duration_ms"] > 0
    assert "T" in meta["timestamp"]  # ISO-8601
    assert "checkpoint_hash" not in meta  # nothing cataloged under this filename


@pytest.mark.asyncio
async def test_checkpoint_hash_resolves_against_the_asset_catalog(
    client,
    harness_app,
    running_a1111_server,
    running_ssh_server: RunningSSHServer,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HARNESS_TEST_PROVENANCE_PASSWORD", running_ssh_server.password)
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": "provenance-ssh-password",
            "kind": "env",
            "target": "HARNESS_TEST_PROVENANCE_PASSWORD",
        },
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "provenance-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": [str(tmp_path)],
        },
    )
    models = tmp_path / "Models" / "StableDiffusion"
    models.mkdir(parents=True)
    content = b"known checkpoint bytes"
    (models / "known-checkpoint.safetensors").write_bytes(content)

    scan = await client.post(
        "/api/v1/creative/assets/scan",
        json={"host_id": host.json()["id"], "models_root": str(tmp_path / "Models")},
    )
    assert scan.status_code == 200
    expected_hash = hashlib.sha256(content).hexdigest()
    assert scan.json()[0]["content_hash"] == expected_hash

    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "automatic1111",
            "base_url": running_a1111_server.base_url,
            "operation": "txt2img",
            "params": {
                "prompt": "x",
                "override_settings": {"sd_model_checkpoint": "known-checkpoint.safetensors"},
            },
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded"

    events = await harness_app.events.replay(0)
    completed = [e for e in events if e.type == "job.completed" and e.resource.id == finished["id"]]
    artifact_id = completed[-1].payload["result"]["output_artifact_ids"][0]
    artifact = (await client.get(f"/api/v1/artifacts/{artifact_id}")).json()
    assert artifact["metadata"]["checkpoint_hash"] == expected_hash


@pytest.mark.asyncio
async def test_comfyui_provenance_is_the_lighter_declared_subset(
    client, harness_app, running_comfyui_server
) -> None:
    job_resp = await client.post(
        "/api/v1/creative/jobs",
        json={
            "engine_id": "comfyui",
            "base_url": running_comfyui_server.base_url,
            "workflow": {"1": {"class_type": "KSampler", "inputs": {}}},
        },
    )
    finished = await _wait_for_job(client, job_resp.json()["id"])
    assert finished["status"] == "succeeded", finished

    events = await harness_app.events.replay(0)
    completed = [e for e in events if e.type == "job.completed" and e.resource.id == finished["id"]]
    artifact_ids = completed[-1].payload["result"]["output_artifact_ids"]
    assert artifact_ids
    artifact = (await client.get(f"/api/v1/artifacts/{artifact_ids[0]}")).json()
    meta = artifact["metadata"]
    assert meta["engine_id"] == "comfyui"
    assert meta["base_url"] == running_comfyui_server.base_url
    assert meta["duration_ms"] > 0
    assert "T" in meta["timestamp"]
    # The declared scope boundary: no parameter-level fields are guessed
    # from the workflow graph.
    assert "checkpoint" not in meta
    assert "seed" not in meta
    assert "sampler" not in meta
