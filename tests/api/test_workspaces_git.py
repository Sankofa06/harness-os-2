import os

import pytest

from tests.api.test_workspaces import _create_ssh_host
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
    os.environ.pop("HARNESS_TEST_WSP_PASSWORD", None)


async def _create_workspace(client, host, root_path, display_name="proj"):
    created = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": root_path, "display_name": display_name},
    )
    assert created.status_code == 201
    return created.json()


@pytest.mark.asyncio
async def test_git_status_reports_not_a_repo_before_init(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    status = await client.get(f"/api/v1/workspaces/{workspace['id']}/git/status")
    assert status.json() == {"is_git_repo": False, "branch": None, "entries": []}


@pytest.mark.asyncio
async def test_git_init_add_commit_status_log_round_trip(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))
    ws_id = workspace["id"]

    init = await client.post(f"/api/v1/workspaces/{ws_id}/git/init")
    assert init.status_code == 200
    assert init.json()["ok"] is True
    assert (tmp_path / ".git").is_dir()

    (tmp_path / "readme.md").write_text("# hello\n")
    status = await client.get(f"/api/v1/workspaces/{ws_id}/git/status")
    body = status.json()
    assert body["is_git_repo"] is True
    assert {"status": "??", "path": "readme.md"} in body["entries"]

    added = await client.post(f"/api/v1/workspaces/{ws_id}/git/add", json={"paths": ["readme.md"]})
    assert added.status_code == 200

    status_after_add = await client.get(f"/api/v1/workspaces/{ws_id}/git/status")
    assert {"status": "A ", "path": "readme.md"} in status_after_add.json()["entries"]

    commit = await client.post(
        f"/api/v1/workspaces/{ws_id}/git/commit",
        json={
            "message": "initial commit",
            "author_name": "Harness Test",
            "author_email": "harness-test@example.com",
        },
    )
    assert commit.status_code == 200
    commit_body = commit.json()
    assert commit_body["ok"] is True
    assert commit_body["commit_hash"]

    status_after_commit = await client.get(f"/api/v1/workspaces/{ws_id}/git/status")
    assert status_after_commit.json()["entries"] == []

    log = await client.get(f"/api/v1/workspaces/{ws_id}/git/log")
    entries = log.json()
    assert len(entries) == 1
    assert entries[0]["commit_hash"] == commit_body["commit_hash"]
    assert entries[0]["subject"] == "initial commit"
    assert entries[0]["author"] == "Harness Test"


@pytest.mark.asyncio
async def test_git_commit_with_nothing_staged_reports_failure_not_error(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))
    await client.post(f"/api/v1/workspaces/{workspace['id']}/git/init")

    commit = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/git/commit",
        json={
            "message": "nothing to commit",
            "author_name": "Harness Test",
            "author_email": "harness-test@example.com",
        },
    )
    assert commit.status_code == 200
    assert commit.json()["ok"] is False


@pytest.mark.asyncio
async def test_git_branch_list_and_create(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))
    ws_id = workspace["id"]
    await client.post(f"/api/v1/workspaces/{ws_id}/git/init")
    (tmp_path / "a.txt").write_text("a\n")
    await client.post(f"/api/v1/workspaces/{ws_id}/git/add", json={"paths": ["a.txt"]})
    await client.post(
        f"/api/v1/workspaces/{ws_id}/git/commit",
        json={
            "message": "first",
            "author_name": "Harness Test",
            "author_email": "harness-test@example.com",
        },
    )

    branches_before = await client.get(f"/api/v1/workspaces/{ws_id}/git/branch")
    assert len(branches_before.json()) == 1
    assert branches_before.json()[0]["current"] is True

    created = await client.post(
        f"/api/v1/workspaces/{ws_id}/git/branch",
        json={"name": "feature-x", "checkout": True},
    )
    assert created.status_code == 200

    branches_after = await client.get(f"/api/v1/workspaces/{ws_id}/git/branch")
    by_name = {b["name"]: b["current"] for b in branches_after.json()}
    assert by_name.get("feature-x") is True


@pytest.mark.asyncio
async def test_git_diff_namespaced_endpoint_matches_top_level(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))
    ws_id = workspace["id"]
    await client.post(f"/api/v1/workspaces/{ws_id}/git/init")
    (tmp_path / "f.txt").write_text("v1\n")
    await client.post(f"/api/v1/workspaces/{ws_id}/git/add", json={"paths": ["f.txt"]})
    await client.post(
        f"/api/v1/workspaces/{ws_id}/git/commit",
        json={
            "message": "v1",
            "author_name": "Harness Test",
            "author_email": "harness-test@example.com",
        },
    )
    (tmp_path / "f.txt").write_text("v2\n")

    top_level = await client.get(f"/api/v1/workspaces/{ws_id}/diff")
    namespaced = await client.get(f"/api/v1/workspaces/{ws_id}/git/diff")
    assert top_level.json() == namespaced.json()
    assert "-v1" in top_level.json()["diff"]
    assert "+v2" in top_level.json()["diff"]
