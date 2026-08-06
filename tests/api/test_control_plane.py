import pytest


@pytest.mark.asyncio
async def test_create_and_list_language_provider(client) -> None:
    resp = await client.post(
        "/api/v1/language/providers",
        json={
            "type": "openai_compatible",
            "display_name": "Local OpenAI-compatible",
            "base_url": "http://127.0.0.1:8080/v1",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "openai_compatible"
    assert body["enabled"] is True

    listing = await client.get("/api/v1/language/providers")
    assert any(p["id"] == body["id"] for p in listing.json())


@pytest.mark.asyncio
async def test_delete_language_provider(client) -> None:
    created = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "to-delete"}
    )
    provider_id = created.json()["id"]
    resp = await client.delete(f"/api/v1/language/providers/{provider_id}")
    assert resp.status_code == 204
    missing = await client.get(f"/api/v1/language/providers/{provider_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_create_host_with_capabilities(client) -> None:
    resp = await client.post(
        "/api/v1/hosts",
        json={
            "display_name": "dev-box",
            "kind": "ssh",
            "hostname": "203.0.113.20",
            "port": 22,
            "username": "dev",
            "workspace_roots": ["/srv/projects"],
            "capabilities": ["ssh_execution", "filesystem"],
        },
    )
    assert resp.status_code == 201
    host_id = resp.json()["id"]

    caps = await client.get(f"/api/v1/hosts/{host_id}/capabilities")
    assert set(caps.json()) == {"ssh_execution", "filesystem"}


@pytest.mark.asyncio
async def test_update_host_capabilities(client) -> None:
    created = await client.post("/api/v1/hosts", json={"display_name": "gpu-box", "kind": "node"})
    host_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/hosts/{host_id}/capabilities",
        json={"capabilities": ["gpu_telemetry", "creative_runtime"]},
    )
    assert set(updated.json()["capabilities"]) == {"gpu_telemetry", "creative_runtime"}
