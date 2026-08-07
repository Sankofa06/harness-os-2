"""CRE-001: `POST /creative/installations/scan` reads a real Stability Matrix
`settings.json` over SFTP from a real local SSH server (matching HOST-002's
established fixture pattern), not a mock — the same path-containment rules
(`workspace_roots`) that gate `SSHHost.read_file` everywhere else apply here
too.
"""

from __future__ import annotations

import json
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
    os.environ.pop("HARNESS_TEST_CREATIVE_PASSWORD", None)


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots):
    os.environ["HARNESS_TEST_CREATIVE_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": "creative-ssh-password",
            "kind": "env",
            "target": "HARNESS_TEST_CREATIVE_PASSWORD",
        },
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "creative-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": workspace_roots,
        },
    )
    return host.json()


_SETTINGS = {
    "InstalledPackages": [
        {
            "DisplayName": "ComfyUI",
            "PackageName": "ComfyUI",
            "LibraryPath": "Packages/ComfyUI",
            "PythonVersion": "3.11.9",
        },
        {
            "DisplayName": "Fooocus",
            "PackageName": "Fooocus",
            "LibraryPath": "Packages/Fooocus",
            "PythonVersion": "3.10.9",
        },
        {
            "DisplayName": "MysteryGenerator",
            "PackageName": "mystery-generator",
            "LibraryPath": "Packages/MysteryGenerator",
            "PythonVersion": "3.12.1",
        },
    ]
}


@pytest.mark.asyncio
async def test_scan_discovers_installations_from_a_real_data_dir(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(_SETTINGS))
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])

    resp = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )
    assert resp.status_code == 200
    installations = resp.json()
    assert len(installations) == 3

    by_name = {i["package_name"]: i for i in installations}
    assert by_name["ComfyUI"]["family_id"] == "comfyui"
    assert by_name["ComfyUI"]["platform_supported"] is True
    assert by_name["Fooocus"]["family_group"] == "fooocus"
    assert by_name["mystery-generator"]["family_id"] == "unknown"
    assert by_name["mystery-generator"]["family_display_name"] == "Unknown/Custom"
    assert by_name["mystery-generator"]["raw_metadata"]["PythonVersion"] == "3.12.1"


@pytest.mark.asyncio
async def test_list_installations_after_scan(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(_SETTINGS))
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )

    listed = await client.get("/api/v1/creative/installations")
    assert len(listed.json()) == 3

    scoped = await client.get("/api/v1/creative/installations", params={"host_id": host["id"]})
    assert len(scoped.json()) == 3

    other = await client.get("/api/v1/creative/installations", params={"host_id": "host_nope"})
    assert other.json() == []


@pytest.mark.asyncio
async def test_rescanning_replaces_stale_entries(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "settings.json").write_text(json.dumps(_SETTINGS))
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )

    # ComfyUI got uninstalled; re-scan the same directory.
    smaller = {"InstalledPackages": _SETTINGS["InstalledPackages"][1:]}
    (tmp_path / "settings.json").write_text(json.dumps(smaller))
    rescanned = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )
    assert len(rescanned.json()) == 2

    listed = await client.get("/api/v1/creative/installations", params={"host_id": host["id"]})
    assert len(listed.json()) == 2
    assert "ComfyUI" not in {i["package_name"] for i in listed.json()}


@pytest.mark.asyncio
async def test_scan_rejects_path_outside_workspace_roots(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "settings.json").write_text(json.dumps(_SETTINGS))
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    host = await _create_ssh_host(client, running_ssh_server, [str(allowed)])

    resp = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(outside), "platform": "linux"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scan_rejects_non_ssh_host(client, tmp_path) -> None:
    host = await client.post("/api/v1/hosts", json={"display_name": "local-host", "kind": "local"})
    resp = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host.json()["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scan_unknown_host_404s(client, tmp_path) -> None:
    resp = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": "host_nope", "data_dir": str(tmp_path), "platform": "linux"},
    )
    assert resp.status_code == 404
