"""`scan_models_directory` against a real local SSH server (CRE-006) --
proves recursive walking of the known shared-folder subtrees, extension
filtering, and remote hashing, without mocking SSH.
"""

from __future__ import annotations

import hashlib

import pytest

from harness.core.domain import Host
from harness.hosts.ssh import SSHHost
from harness.providers.creative.assets import scan_models_directory
from tests.hosts.fixtures import RunningSSHServer, start_test_ssh_server


def _ssh_host(server: RunningSSHServer, workspace_roots: list[str]) -> SSHHost:
    return SSHHost(
        Host(
            id="host_test",
            display_name="test-ssh",
            kind="ssh",
            hostname="127.0.0.1",
            port=server.port,
            username=server.username,
            workspace_roots=workspace_roots,
        ),
        password=server.password,
    )


@pytest.fixture
async def ssh_server():
    server, info = await start_test_ssh_server()
    try:
        yield info
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_scan_finds_files_under_known_folders_and_ignores_unknown_ones(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    models = tmp_path / "Models"
    (models / "StableDiffusion").mkdir(parents=True)
    (models / "Lora").mkdir()
    (models / "SomeUnknownFolderType").mkdir()
    (models / "StableDiffusion" / "model.safetensors").write_bytes(b"checkpoint bytes")
    (models / "Lora" / "style.safetensors").write_bytes(b"lora bytes")
    (models / "SomeUnknownFolderType" / "ignored.safetensors").write_bytes(b"ignored")

    ssh_host = _ssh_host(ssh_server, [str(tmp_path)])
    found = await scan_models_directory(ssh_host, str(models))

    by_filename = {f.filename: f for f in found}
    assert set(by_filename) == {"model.safetensors", "style.safetensors"}
    assert by_filename["model.safetensors"].asset_kind == "checkpoint"
    assert by_filename["style.safetensors"].asset_kind == "lora"
    assert (
        by_filename["model.safetensors"].content_hash
        == hashlib.sha256(b"checkpoint bytes").hexdigest()
    )


@pytest.mark.asyncio
async def test_scan_ignores_non_model_extensions(ssh_server: RunningSSHServer, tmp_path) -> None:
    models = tmp_path / "Models"
    (models / "VAE").mkdir(parents=True)
    (models / "VAE" / "vae.safetensors").write_bytes(b"vae bytes")
    (models / "VAE" / "readme.txt").write_text("not a model")
    (models / "VAE" / "preview.json").write_text("{}")

    ssh_host = _ssh_host(ssh_server, [str(tmp_path)])
    found = await scan_models_directory(ssh_host, str(models))

    assert [f.filename for f in found] == ["vae.safetensors"]


@pytest.mark.asyncio
async def test_scan_descends_into_nested_subfolders(ssh_server: RunningSSHServer, tmp_path) -> None:
    models = tmp_path / "Models"
    nested = models / "ControlNet" / "sdxl"
    nested.mkdir(parents=True)
    (nested / "control.safetensors").write_bytes(b"control bytes")

    ssh_host = _ssh_host(ssh_server, [str(tmp_path)])
    found = await scan_models_directory(ssh_host, str(models))

    assert len(found) == 1
    assert found[0].asset_kind == "controlnet"
    assert found[0].path.endswith("/ControlNet/sdxl/control.safetensors")


@pytest.mark.asyncio
async def test_scan_handles_entirely_missing_models_root_gracefully(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    ssh_host = _ssh_host(ssh_server, [str(tmp_path)])
    found = await scan_models_directory(ssh_host, str(tmp_path / "Models"))
    assert found == []
