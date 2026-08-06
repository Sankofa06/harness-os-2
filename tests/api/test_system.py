import pytest


@pytest.mark.asyncio
async def test_health(client) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_versioned_prefix(client) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_system_info(client) -> None:
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["demo_mode"] is True
    assert body["context_budget"]["bootstrap_target_tokens"] == 4096


@pytest.mark.asyncio
async def test_capabilities_lists_fake_provider(client) -> None:
    resp = await client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    providers = resp.json()["language_providers"]
    assert any(p["id"] == "fake" for p in providers)


@pytest.mark.asyncio
async def test_openapi_served(client) -> None:
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Harness OS API"


@pytest.mark.asyncio
async def test_not_found_has_structured_error_shape(client) -> None:
    resp = await client.get("/api/v1/contacts/con_missing")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "not_found"
