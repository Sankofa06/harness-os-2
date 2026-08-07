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


@pytest.mark.asyncio
async def test_host_test_endpoint_succeeds_with_password_secret(
    client, harness_app, running_ssh_server: RunningSSHServer
) -> None:
    secret = await client.post(
        "/api/v1/secrets",
        json={
            "name": "ssh-test-password",
            "kind": "env",
            "target": "HARNESS_TEST_SSH_PASSWORD",
        },
    )
    secret_id = secret.json()["id"]
    os.environ["HARNESS_TEST_SSH_PASSWORD"] = running_ssh_server.password

    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "real-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret_id,
        },
    )
    host_id = host.json()["id"]

    result = await client.post(f"/api/v1/hosts/{host_id}/test")
    body = result.json()
    assert body["ok"] is True
    assert body["fingerprint"] == running_ssh_server.host_key_fingerprint

    del os.environ["HARNESS_TEST_SSH_PASSWORD"]


@pytest.mark.asyncio
async def test_host_test_endpoint_reports_failure_for_bad_password(
    client, running_ssh_server: RunningSSHServer
) -> None:
    os.environ["HARNESS_TEST_SSH_BAD_PASSWORD"] = "definitely-wrong"
    secret = await client.post(
        "/api/v1/secrets",
        json={"name": "bad-pw", "kind": "env", "target": "HARNESS_TEST_SSH_BAD_PASSWORD"},
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "bad-ssh-host",
            "kind": "ssh",
            "hostname": "127.0.0.1",
            "port": running_ssh_server.port,
            "username": running_ssh_server.username,
            "secret_ref_id": secret.json()["id"],
        },
    )
    result = await client.post(f"/api/v1/hosts/{host.json()['id']}/test")
    body = result.json()
    assert body["ok"] is False
    assert body["error"]

    del os.environ["HARNESS_TEST_SSH_BAD_PASSWORD"]


@pytest.mark.asyncio
async def test_host_test_endpoint_rejects_non_ssh_host(client) -> None:
    host = await client.post("/api/v1/hosts", json={"display_name": "local-host", "kind": "local"})
    result = await client.post(f"/api/v1/hosts/{host.json()['id']}/test")
    body = result.json()
    assert body["ok"] is False
