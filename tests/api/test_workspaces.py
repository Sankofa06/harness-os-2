import asyncio
import os
import subprocess

import pytest

from tests.hosts.fixtures import RunningSSHServer, start_test_ssh_server


def _init_git_repo_with_a_commit(repo_dir) -> None:
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    (repo_dir / "tracked.txt").write_text("original\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True
    )


@pytest.fixture
async def running_ssh_server():
    server, info = await start_test_ssh_server()
    try:
        yield info
    finally:
        server.close()
        await server.wait_closed()


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots):
    os.environ["HARNESS_TEST_WSP_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={"name": "wsp-ssh-password", "kind": "env", "target": "HARNESS_TEST_WSP_PASSWORD"},
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "wsp-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": workspace_roots,
        },
    )
    return host.json()


@pytest.fixture(autouse=True)
def _cleanup_env():
    yield
    os.environ.pop("HARNESS_TEST_WSP_PASSWORD", None)


@pytest.mark.asyncio
async def test_browse_and_create_folder_at_host_level(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])

    listing = await client.get(
        f"/api/v1/hosts/{host['id']}/workspaces/browse", params={"path": str(tmp_path)}
    )
    assert listing.status_code == 200
    assert listing.json() == []

    created = await client.post(
        f"/api/v1/hosts/{host['id']}/workspaces/create-folder",
        json={"path": f"{tmp_path}/project-a"},
    )
    assert created.status_code == 201
    assert (tmp_path / "project-a").is_dir()

    listing_after = await client.get(
        f"/api/v1/hosts/{host['id']}/workspaces/browse", params={"path": str(tmp_path)}
    )
    names = [e["name"] for e in listing_after.json()]
    assert "project-a" in names


@pytest.mark.asyncio
async def test_browse_outside_workspace_roots_rejected(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [f"{tmp_path}/allowed"])
    result = await client.get(
        f"/api/v1/hosts/{host['id']}/workspaces/browse", params={"path": str(tmp_path)}
    )
    assert result.status_code == 403


@pytest.mark.asyncio
async def test_create_workspace_rejects_root_outside_host_workspace_roots(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [f"{tmp_path}/allowed"])
    result = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": str(tmp_path), "display_name": "bad"},
    )
    assert result.status_code == 403


@pytest.mark.asyncio
async def test_workspace_crud_and_file_round_trip(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    created = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": str(tmp_path), "display_name": "proj"},
    )
    assert created.status_code == 201
    workspace = created.json()

    listed = await client.get("/api/v1/workspaces")
    assert any(w["id"] == workspace["id"] for w in listed.json())

    fetched = await client.get(f"/api/v1/workspaces/{workspace['id']}")
    assert fetched.json()["root_path"] == str(tmp_path)

    write = await client.put(
        f"/api/v1/workspaces/{workspace['id']}/file",
        json={"path": "notes.txt", "content": "hello workspace"},
    )
    assert write.status_code == 204
    assert (tmp_path / "notes.txt").read_text() == "hello workspace"

    read = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/file", params={"path": "notes.txt"}
    )
    assert read.json() == {
        "path": "notes.txt",
        "content": "hello workspace",
        "size": len("hello workspace"),
        "binary": False,
    }

    tree = await client.get(f"/api/v1/workspaces/{workspace['id']}/tree")
    assert any(e["name"] == "notes.txt" for e in tree.json())

    deleted = await client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/workspaces/{workspace['id']}")).status_code == 404
    # The record is gone but the underlying file is untouched.
    assert (tmp_path / "notes.txt").exists()


@pytest.mark.asyncio
async def test_workspace_file_path_cannot_escape_workspace_root(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "proj-a").mkdir()
    (tmp_path / "proj-b").mkdir()
    (tmp_path / "proj-b" / "secret.txt").write_text("do not read from proj-a")

    # Host allows the whole tmp_path, so a workspace pinned to proj-a is a *narrower*
    # boundary than the host itself allows — the workspace-level check must still
    # reject an escape into the sibling proj-b directory.
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    created = await client.post(
        "/api/v1/workspaces",
        json={
            "host_id": host["id"],
            "root_path": str(tmp_path / "proj-a"),
            "display_name": "proj-a",
        },
    )
    workspace = created.json()

    result = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/file",
        params={"path": "../proj-b/secret.txt"},
    )
    assert result.status_code == 403


@pytest.mark.asyncio
async def test_workspace_diff_reports_not_a_git_repo(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    created = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": str(tmp_path), "display_name": "proj"},
    )
    workspace = created.json()

    diff = await client.get(f"/api/v1/workspaces/{workspace['id']}/diff")
    assert diff.status_code == 200
    assert diff.json() == {"is_git_repo": False, "diff": ""}


@pytest.mark.asyncio
async def test_workspace_diff_reports_real_git_diff(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await asyncio.to_thread(_init_git_repo_with_a_commit, tmp_path)
    (tmp_path / "tracked.txt").write_text("changed\n")

    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    created = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": str(tmp_path), "display_name": "proj"},
    )
    workspace = created.json()

    diff = await client.get(f"/api/v1/workspaces/{workspace['id']}/diff")
    body = diff.json()
    assert body["is_git_repo"] is True
    assert "-original" in body["diff"]
    assert "+changed" in body["diff"]
