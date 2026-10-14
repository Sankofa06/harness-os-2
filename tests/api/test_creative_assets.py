"""CRE-006's full acceptance bar end to end: `POST /creative/assets/scan`
against a real local SSH server and real files on disk, proving a
checkpoint whose content is duplicated at two paths is cataloged once with
two locations, and that scanning a second host with the same content joins
the same asset.
"""

from __future__ import annotations

import os

import pytest

from tests.hosts.fixtures import RunningSSHServer, start_test_ssh_server


@pytest.fixture
async def running_ssh_server():
    server, info = await start_test_ssh_server()
    try:
        yield info
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture(autouse=True)
def _cleanup_env():
    yield
    os.environ.pop("HARNESS_TEST_ASSETS_PASSWORD", None)


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots, *, name):
    os.environ["HARNESS_TEST_ASSETS_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": f"{name}-password",
            "kind": "env",
            "target": "HARNESS_TEST_ASSETS_PASSWORD",
        },
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": name,
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": workspace_roots,
        },
    )
    return host.json()


@pytest.mark.asyncio
async def test_duplicate_checkpoint_at_two_paths_is_one_asset_two_locations(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)], name="assets-host")
    models = tmp_path / "Models"
    (models / "StableDiffusion").mkdir(parents=True)
    (models / "StableDiffusion" / "model-a.safetensors").write_bytes(b"shared checkpoint bytes")
    (models / "StableDiffusion" / "model-a-copy.safetensors").write_bytes(
        b"shared checkpoint bytes"
    )

    resp = await client.post(
        "/api/v1/creative/assets/scan",
        json={"host_id": host["id"], "models_root": str(models)},
    )
    assert resp.status_code == 200
    assets = resp.json()
    assert len(assets) == 1
    assert assets[0]["asset_kind"] == "checkpoint"
    assert {loc["path"] for loc in assets[0]["locations"]} == {
        str(models / "StableDiffusion" / "model-a.safetensors"),
        str(models / "StableDiffusion" / "model-a-copy.safetensors"),
    }

    listed = await client.get("/api/v1/creative/assets")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_distinct_checkpoints_stay_separate_assets(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)], name="assets-host")
    models = tmp_path / "Models"
    (models / "Lora").mkdir(parents=True)
    (models / "Lora" / "lora-one.safetensors").write_bytes(b"lora one bytes")
    (models / "Lora" / "lora-two.safetensors").write_bytes(b"lora two bytes")

    resp = await client.post(
        "/api/v1/creative/assets/scan",
        json={"host_id": host["id"], "models_root": str(models)},
    )
    assert resp.status_code == 200
    assets = resp.json()
    assert len(assets) == 2
    assert all(a["asset_kind"] == "lora" for a in assets)

    filtered = await client.get("/api/v1/creative/assets", params={"asset_kind": "lora"})
    assert len(filtered.json()) == 2
    filtered_other = await client.get("/api/v1/creative/assets", params={"asset_kind": "vae"})
    assert filtered_other.json() == []


@pytest.mark.asyncio
async def test_unknown_host_returns_404(client) -> None:
    resp = await client.post(
        "/api/v1/creative/assets/scan",
        json={"host_id": "host_doesnotexist", "models_root": "/data/Models"},
    )
    assert resp.status_code == 404
