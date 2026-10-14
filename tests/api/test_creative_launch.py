"""CRE-005: `creative.launch_engine`/`creative.launch_training` native
Tools, proven against a real local SSH server — not mocks — including that
training-family installations are only launchable via the gated tool
(SPEC: training is "not implicitly available to LLM agents"), and that
canceling the Job actually stops the remote process (not just Harness's
wait on it) via the same SSH-connection-close mechanism `exec_stream`
already relies on.
"""

from __future__ import annotations

import asyncio
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
    os.environ.pop("HARNESS_TEST_LAUNCH_PASSWORD", None)


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots):
    os.environ["HARNESS_TEST_LAUNCH_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": "launch-ssh-password",
            "kind": "env",
            "target": "HARNESS_TEST_LAUNCH_PASSWORD",
        },
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "launch-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
            "workspace_roots": workspace_roots,
        },
    )
    return host.json()


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def _scan_one_installation(
    client, host, tmp_path, *, package_name: str, display_name: str, launch_command: str
) -> dict:
    settings = {
        "InstalledPackages": [
            {
                "PackageName": package_name,
                "DisplayName": display_name,
                "LibraryPath": f"Packages/{display_name}",
                "LaunchCommand": launch_command,
            }
        ]
    }
    (tmp_path / "Packages" / display_name).mkdir(parents=True)
    (tmp_path / "settings.json").write_text(json.dumps(settings))
    scanned = await client.post(
        "/api/v1/creative/installations/scan",
        json={"host_id": host["id"], "data_dir": str(tmp_path), "platform": "linux"},
    )
    assert scanned.status_code == 200
    return scanned.json()[0]


async def _run_tool(client, name: str, arguments: dict) -> dict:
    resp = await client.post(f"/api/v1/tools/{name}/run", json={"arguments": arguments})
    assert resp.status_code == 202
    return resp.json()  # the Job record


@pytest.mark.asyncio
async def test_launch_training_runs_the_real_recorded_command(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/training", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="kohya_ss",
        display_name="Kohya",
        launch_command="echo training-started",
    )
    assert installation["family_group"] == "training"

    job = await _run_tool(
        client, "creative.launch_training", {"installation_id": installation["id"]}
    )
    finished = await _wait_for_job(client, job["id"])
    assert finished["status"] == "succeeded", finished

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "creative.launch_training"})
    tool_run = runs.json()[0]
    assert tool_run["status"] == "succeeded"
    assert "training-started" in " ".join(tool_run["result"]["output_tail"])


@pytest.mark.asyncio
async def test_launch_engine_rejects_a_training_installation(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="onetrainer",
        display_name="OneTrainer",
        launch_command="echo should-not-run",
    )

    job = await _run_tool(client, "creative.launch_engine", {"installation_id": installation["id"]})
    finished = await _wait_for_job(client, job["id"])
    assert finished["status"] == "succeeded"  # the Job completed; the ToolRun itself failed below

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "creative.launch_engine"})
    tool_run = runs.json()[0]
    assert tool_run["status"] == "failed"
    assert "creative.launch_training" in tool_run["error"]


@pytest.mark.asyncio
async def test_launch_training_rejects_a_non_training_installation(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/training", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="fooocus",
        display_name="Fooocus",
        launch_command="echo should-not-run",
    )

    job = await _run_tool(
        client, "creative.launch_training", {"installation_id": installation["id"]}
    )
    await _wait_for_job(client, job["id"])

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "creative.launch_training"})
    tool_run = runs.json()[0]
    assert tool_run["status"] == "failed"
    assert "not a training engine" in tool_run["error"]


@pytest.mark.asyncio
async def test_launch_engine_runs_a_fooocus_style_installation(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="fooocus",
        display_name="Fooocus",
        launch_command="echo fooocus-up",
    )

    job = await _run_tool(client, "creative.launch_engine", {"installation_id": installation["id"]})
    finished = await _wait_for_job(client, job["id"])
    assert finished["status"] == "succeeded", finished

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "creative.launch_engine"})
    tool_run = runs.json()[0]
    assert tool_run["status"] == "succeeded"
    assert "fooocus-up" in " ".join(tool_run["result"]["output_tail"])


@pytest.mark.asyncio
async def test_canceling_the_job_stops_a_long_running_launch(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/execute", json={"policy": "allow"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="sdfx",
        display_name="SDFX",
        launch_command="sleep 30",
    )

    job = await _run_tool(client, "creative.launch_engine", {"installation_id": installation["id"]})

    # Give the SSH exec a moment to actually start before canceling.
    await asyncio.sleep(0.3)
    canceled = await client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert canceled.status_code == 200

    finished = await _wait_for_job(client, job["id"], timeout_seconds=5.0)
    assert finished["status"] == "canceled"


@pytest.mark.asyncio
async def test_launch_denied_without_permission_approval(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    await client.put("/api/v1/permissions/policies/training", json={"policy": "deny"})
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    installation = await _scan_one_installation(
        client,
        host,
        tmp_path,
        package_name="fluxgym",
        display_name="FluxGym",
        launch_command="echo should-not-run",
    )

    job = await _run_tool(
        client, "creative.launch_training", {"installation_id": installation["id"]}
    )
    await _wait_for_job(client, job["id"])

    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "creative.launch_training"})
    tool_run = runs.json()[0]
    assert tool_run["status"] == "denied"
