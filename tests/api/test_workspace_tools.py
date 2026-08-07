import asyncio
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
    os.environ.pop("HARNESS_TEST_WSPTOOL_PASSWORD", None)


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots):
    os.environ["HARNESS_TEST_WSPTOOL_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": "wsptool-ssh-password",
            "kind": "env",
            "target": "HARNESS_TEST_WSPTOOL_PASSWORD",
        },
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "wsptool-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": workspace_roots,
        },
    )
    return host.json()


async def _create_workspace(client, host, root_path, display_name="proj"):
    created = await client.post(
        "/api/v1/workspaces",
        json={"host_id": host["id"], "root_path": root_path, "display_name": display_name},
    )
    assert created.status_code == 201
    return created.json()


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def _run_tool(client, name: str, arguments: dict) -> dict:
    resp = await client.post(f"/api/v1/tools/{name}/run", json={"arguments": arguments})
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": name})
    matching = [r for r in runs.json() if r["arguments"] == arguments]
    assert matching, runs.json()
    return matching[-1]


@pytest.mark.asyncio
async def test_list_tools_includes_all_workspace_tools(client) -> None:
    resp = await client.get("/api/v1/tools")
    by_name = {t["name"]: t for t in resp.json()}
    expected_classes = {
        "fs_read_file": "read",
        "fs_write_file": "write",
        "fs_list_dir": "read",
        "shell_exec": "execute",
        "git_init": "git",
        "git_status": "git",
        "git_diff": "git",
        "git_add": "git",
        "git_commit": "git",
        "git_branch_list": "git",
        "git_branch_create": "git",
        "git_log": "git",
    }
    for name, permission_class in expected_classes.items():
        assert name in by_name, f"missing tool: {name}"
        assert by_name[name]["permission_class"] == permission_class
        assert by_name[name]["workspace_scoped"] is True


@pytest.mark.asyncio
async def test_fs_read_file_default_policy_allows_immediately(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "hello.txt").write_text("hello from disk")
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    run = await _run_tool(
        client, "fs_read_file", {"workspace_id": workspace["id"], "path": "hello.txt"}
    )
    assert run["status"] == "succeeded"
    assert run["result"] == {
        "content": "hello from disk",
        "size": len("hello from disk"),
        "binary": False,
    }
    assert run["permission_class"] == "read"


@pytest.mark.asyncio
async def test_fs_write_then_read_round_trip_once_write_policy_allows(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/write", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    write_run = await _run_tool(
        client,
        "fs_write_file",
        {"workspace_id": workspace["id"], "path": "new.txt", "content": "written by a tool"},
    )
    assert write_run["result"] == {
        "path": "new.txt",
        "bytes_written": len("written by a tool"),
    }
    assert (tmp_path / "new.txt").read_text() == "written by a tool"

    read_run = await _run_tool(
        client, "fs_read_file", {"workspace_id": workspace["id"], "path": "new.txt"}
    )
    assert read_run["result"]["content"] == "written by a tool"


@pytest.mark.asyncio
async def test_fs_list_dir_defaults_to_workspace_root(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub").mkdir()
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    run = await _run_tool(client, "fs_list_dir", {"workspace_id": workspace["id"]})
    names = {e["name"]: e["is_dir"] for e in run["result"]["entries"]}
    assert names == {"a.txt": False, "sub": True}


@pytest.mark.asyncio
async def test_fs_read_file_path_traversal_is_rejected(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "workspace").mkdir()
    (tmp_path / "secret.txt").write_text("outside the workspace")
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path / "workspace"))

    arguments = {"workspace_id": workspace["id"], "path": "../secret.txt"}
    resp = await client.post("/api/v1/tools/fs_read_file/run", json={"arguments": arguments})
    job = await _wait_for_job(client, resp.json()["id"])
    # The Job succeeds (it scheduled and ran the lifecycle); the *tool run* it
    # wrapped is what failed, on the same containment check WSP-001's HTTP route
    # uses (harness.workspaces.service.resolve_within_workspace).
    assert job["status"] == "succeeded"

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "fs_read_file"})
    matching = [r for r in runs.json() if r["arguments"] == arguments]
    assert len(matching) == 1
    assert matching[0]["status"] == "failed"
    assert "outside all configured workspace roots" in matching[0]["error"]


@pytest.mark.asyncio
async def test_shell_exec_runs_in_workspace_root_by_default(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    run = await _run_tool(client, "shell_exec", {"workspace_id": workspace["id"], "argv": ["pwd"]})
    assert run["result"]["stdout"].strip() == str(tmp_path)
    assert run["result"]["exit_status"] == 0


@pytest.mark.asyncio
async def test_shell_exec_quotes_arguments_safely(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    dangerous = "hello; touch /tmp/should-not-exist-from-tool-injection && echo pwned"
    run = await _run_tool(
        client,
        "shell_exec",
        {"workspace_id": workspace["id"], "argv": ["echo", dangerous]},
    )
    stdout = run["result"]["stdout"]
    assert dangerous in stdout
    assert "pwned" not in stdout.replace(dangerous, "")


@pytest.mark.asyncio
async def test_git_workflow_via_tools(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/git", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))
    ws_id = workspace["id"]

    init_run = await _run_tool(client, "git_init", {"workspace_id": ws_id})
    assert init_run["result"]["ok"] is True
    assert (tmp_path / ".git").is_dir()

    (tmp_path / "readme.md").write_text("# hi\n")
    status_run = await _run_tool(client, "git_status", {"workspace_id": ws_id})
    assert status_run["result"]["is_git_repo"] is True
    assert {"status": "??", "path": "readme.md"} in status_run["result"]["entries"]

    add_run = await _run_tool(client, "git_add", {"workspace_id": ws_id, "paths": ["readme.md"]})
    assert add_run["result"]["ok"] is True

    commit_run = await _run_tool(
        client,
        "git_commit",
        {
            "workspace_id": ws_id,
            "message": "initial",
            "author_name": "Harness Test",
            "author_email": "harness-test@example.com",
        },
    )
    assert commit_run["result"]["ok"] is True
    commit_hash = commit_run["result"]["commit_hash"]
    assert commit_hash

    log_run = await _run_tool(client, "git_log", {"workspace_id": ws_id})
    assert len(log_run["result"]["entries"]) == 1
    assert log_run["result"]["entries"][0]["commit_hash"] == commit_hash

    branch_run = await _run_tool(
        client, "git_branch_create", {"workspace_id": ws_id, "name": "feature-x"}
    )
    assert branch_run["result"]["ok"] is True

    branches_run = await _run_tool(client, "git_branch_list", {"workspace_id": ws_id})
    names = {b["name"] for b in branches_run["result"]["branches"]}
    assert "feature-x" in names

    (tmp_path / "readme.md").write_text("# hi again\n")
    diff_run = await _run_tool(client, "git_diff", {"workspace_id": ws_id})
    assert diff_run["result"]["is_git_repo"] is True
    assert "+# hi again" in diff_run["result"]["diff"]


@pytest.mark.asyncio
async def test_shell_exec_default_ask_policy_blocks_until_approved(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    resp = await client.post(
        "/api/v1/tools/shell_exec/run",
        json={"arguments": {"workspace_id": workspace["id"], "argv": ["echo", "hi"]}},
    )
    job_id = resp.json()["id"]

    deadline = asyncio.get_event_loop().time() + 2.0
    run_id = None
    while asyncio.get_event_loop().time() < deadline:
        pending = await client.get("/api/v1/permissions/pending")
        if pending.json():
            run_id = pending.json()[0]
            break
        await asyncio.sleep(0.01)
    assert run_id is not None, "shell_exec should have required approval by default"

    still_running = await client.get(f"/api/v1/jobs/{job_id}")
    assert still_running.json()["status"] in ("queued", "running")

    approved = await client.post(f"/api/v1/permissions/decisions/{run_id}/approve", json={})
    assert approved.status_code == 200

    job = await _wait_for_job(client, job_id)
    assert job["status"] == "succeeded"

    final = await client.get(f"/api/v1/tools/runs/{run_id}")
    assert final.json()["status"] == "succeeded"
    assert final.json()["result"]["stdout"].strip() == "hi"
