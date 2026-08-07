import pytest


@pytest.mark.asyncio
async def test_create_and_get_model_profile(client) -> None:
    provider = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "profile-provider"}
    )
    provider_id = provider.json()["id"]

    created = await client.post(
        "/api/v1/language/profiles",
        json={
            "name": "local-coder",
            "provider_config_id": provider_id,
            "model_id": "fake-mini",
            "settings": {"common": {"temperature": 0.2}},
            "placement_policy": "prefer-local",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["placement_policy"] == "prefer-local"
    assert body["load_policy"] == "on_demand"

    fetched = await client.get(f"/api/v1/language/profiles/{body['id']}")
    assert fetched.json()["model_id"] == "fake-mini"


@pytest.mark.asyncio
async def test_create_profile_with_unknown_provider_404s(client) -> None:
    resp = await client.post(
        "/api/v1/language/profiles",
        json={"name": "x", "provider_config_id": "prov_missing", "model_id": "m"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_profile_name_rejected(client) -> None:
    provider = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "dup-provider"}
    )
    provider_id = provider.json()["id"]
    await client.post(
        "/api/v1/language/profiles",
        json={"name": "dup", "provider_config_id": provider_id, "model_id": "m"},
    )
    resp = await client.post(
        "/api/v1/language/profiles",
        json={"name": "dup", "provider_config_id": provider_id, "model_id": "m"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_model_profile(client) -> None:
    provider = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "del-provider"}
    )
    created = await client.post(
        "/api/v1/language/profiles",
        json={"name": "del-me", "provider_config_id": provider.json()["id"], "model_id": "m"},
    )
    profile_id = created.json()["id"]
    resp = await client.delete(f"/api/v1/language/profiles/{profile_id}")
    assert resp.status_code == 204
    missing = await client.get(f"/api/v1/language/profiles/{profile_id}")
    assert missing.status_code == 404
