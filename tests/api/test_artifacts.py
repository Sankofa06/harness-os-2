import base64
import hashlib
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
    os.environ.pop("HARNESS_TEST_ART_PASSWORD", None)


async def _create_ssh_host(client, running_ssh_server: RunningSSHServer, workspace_roots):
    os.environ["HARNESS_TEST_ART_PASSWORD"] = running_ssh_server.password
    secret = await client.post(
        "/api/v1/secrets",
        json={"name": "art-ssh-password", "kind": "env", "target": "HARNESS_TEST_ART_PASSWORD"},
    )
    host = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "art-ssh-host",
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


@pytest.mark.asyncio
async def test_create_artifact_from_inline_content(client) -> None:
    content = b"print('hello harness')\n"
    resp = await client.post(
        "/api/v1/artifacts",
        json={
            "type": "code_file",
            "display_name": "hello.py",
            "content_base64": base64.b64encode(content).decode(),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["size"] == len(content)
    assert body["sha256"] == hashlib.sha256(content).hexdigest()
    assert body["mime_type"] == "text/x-python"

    fetched = await client.get(f"/api/v1/artifacts/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["display_name"] == "hello.py"


@pytest.mark.asyncio
async def test_artifact_content_is_lazy_and_fetched_separately(client) -> None:
    content = b"the actual bytes"
    created = await client.post(
        "/api/v1/artifacts",
        json={
            "type": "arbitrary_file",
            "display_name": "data.bin",
            "content_base64": base64.b64encode(content).decode(),
            "mime_type": "application/octet-stream",
        },
    )
    body = created.json()
    assert "content" not in body
    assert "content_base64" not in body

    fetched = await client.get(f"/api/v1/artifacts/{body['id']}")
    assert "content" not in fetched.json()

    content_resp = await client.get(f"/api/v1/artifacts/{body['id']}/content")
    assert content_resp.status_code == 200
    assert content_resp.content == content
    assert content_resp.headers["content-type"] == "application/octet-stream"


@pytest.mark.asyncio
async def test_create_artifact_rejects_invalid_base64(client) -> None:
    resp = await client.post(
        "/api/v1/artifacts",
        json={
            "type": "arbitrary_file",
            "display_name": "bad.bin",
            "content_base64": "not valid base64!!!",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_identical_content_shares_one_blob(client) -> None:
    content = b"shared content"
    encoded = base64.b64encode(content).decode()
    first = await client.post(
        "/api/v1/artifacts",
        json={"type": "log", "display_name": "a.log", "content_base64": encoded},
    )
    second = await client.post(
        "/api/v1/artifacts",
        json={"type": "log", "display_name": "b.log", "content_base64": encoded},
    )
    assert first.json()["sha256"] == second.json()["sha256"]
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.asyncio
async def test_list_artifacts_filters_by_run_id_and_type(client) -> None:
    encoded = base64.b64encode(b"x").decode()
    await client.post(
        "/api/v1/artifacts",
        json={
            "type": "log",
            "display_name": "run-a.log",
            "content_base64": encoded,
            "run_id": "run_a",
        },
    )
    await client.post(
        "/api/v1/artifacts",
        json={
            "type": "plan",
            "display_name": "run-a.plan",
            "content_base64": encoded,
            "run_id": "run_a",
        },
    )
    await client.post(
        "/api/v1/artifacts",
        json={
            "type": "log",
            "display_name": "run-b.log",
            "content_base64": encoded,
            "run_id": "run_b",
        },
    )

    by_run = await client.get("/api/v1/artifacts", params={"run_id": "run_a"})
    assert len(by_run.json()) == 2

    by_type = await client.get("/api/v1/artifacts", params={"type": "log"})
    assert {a["display_name"] for a in by_type.json()} == {"run-a.log", "run-b.log"}

    by_both = await client.get("/api/v1/artifacts", params={"run_id": "run_a", "type": "plan"})
    assert [a["display_name"] for a in by_both.json()] == ["run-a.plan"]


@pytest.mark.asyncio
async def test_delete_artifact_removes_the_catalog_record(client) -> None:
    encoded = base64.b64encode(b"gone soon").decode()
    created = await client.post(
        "/api/v1/artifacts",
        json={"type": "log", "display_name": "temp.log", "content_base64": encoded},
    )
    artifact_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/artifacts/{artifact_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/artifacts/{artifact_id}")).status_code == 404


@pytest.mark.asyncio
async def test_pull_artifact_from_workspace_host(
    client, harness_app, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "report.txt").write_text("build succeeded\n")
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    pulled = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/artifacts/pull",
        json={"path": "report.txt", "type": "test_report"},
    )
    assert pulled.status_code == 201
    body = pulled.json()
    assert body["display_name"] == "report.txt"
    assert body["workspace_id"] == workspace["id"]
    assert body["source_path"] == "report.txt"
    assert body["sha256"] == hashlib.sha256(b"build succeeded\n").hexdigest()

    content_resp = await client.get(f"/api/v1/artifacts/{body['id']}/content")
    assert content_resp.content == b"build succeeded\n"

    events = await harness_app.events.replay(0)
    created_events = [e for e in events if e.type == "artifact.created"]
    assert any(e.resource is not None and e.resource.id == body["id"] for e in created_events)


@pytest.mark.asyncio
async def test_pull_artifact_rejects_path_outside_workspace(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "workspace").mkdir()
    (tmp_path / "secret.txt").write_text("not yours")
    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path / "workspace"))

    resp = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/artifacts/pull",
        json={"path": "../secret.txt", "type": "document"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_push_artifact_to_workspace_host(
    client, harness_app, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    content = b"deployed by harness\n"
    created = await client.post(
        "/api/v1/artifacts",
        json={
            "type": "arbitrary_file",
            "display_name": "deploy.txt",
            "content_base64": base64.b64encode(content).decode(),
        },
    )
    artifact_id = created.json()["id"]

    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    pushed = await client.post(
        f"/api/v1/artifacts/{artifact_id}/push",
        json={"workspace_id": workspace["id"], "path": "deploy.txt"},
    )
    assert pushed.status_code == 200
    assert pushed.json()["sha256"] == created.json()["sha256"]
    assert (tmp_path / "deploy.txt").read_bytes() == content

    events = await harness_app.events.replay(0)
    transferred = [e for e in events if e.type == "artifact.transferred"]
    assert any(e.resource is not None and e.resource.id == artifact_id for e in transferred)


@pytest.mark.asyncio
async def test_push_then_pull_round_trip(
    client, running_ssh_server: RunningSSHServer, tmp_path
) -> None:
    content = b"round trip through a real host\n"
    created = await client.post(
        "/api/v1/artifacts",
        json={
            "type": "arbitrary_file",
            "display_name": "roundtrip.txt",
            "content_base64": base64.b64encode(content).decode(),
        },
    )
    artifact_id = created.json()["id"]

    host = await _create_ssh_host(client, running_ssh_server, [str(tmp_path)])
    workspace = await _create_workspace(client, host, str(tmp_path))

    await client.post(
        f"/api/v1/artifacts/{artifact_id}/push",
        json={"workspace_id": workspace["id"], "path": "roundtrip.txt"},
    )
    pulled_back = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/artifacts/pull",
        json={"path": "roundtrip.txt", "type": "arbitrary_file"},
    )
    assert pulled_back.json()["sha256"] == created.json()["sha256"]
