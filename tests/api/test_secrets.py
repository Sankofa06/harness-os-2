import pytest


@pytest.mark.asyncio
async def test_create_and_list_secret_metadata_never_leaks_value(client) -> None:
    resp = await client.post(
        "/api/v1/secrets",
        json={"name": "openai-key", "kind": "env", "target": "OPENAI_API_KEY"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "openai-key"
    assert "value" not in body

    listing = await client.get("/api/v1/secrets/metadata")
    assert any(s["name"] == "openai-key" for s in listing.json())
    for entry in listing.json():
        assert "value" not in entry


@pytest.mark.asyncio
async def test_secret_test_endpoint_reports_resolvability(client, monkeypatch) -> None:
    import os

    os.environ["HARNESS_API_TEST_SECRET"] = "present"
    created = await client.post(
        "/api/v1/secrets",
        json={"name": "present-secret", "kind": "env", "target": "HARNESS_API_TEST_SECRET"},
    )
    secret_id = created.json()["id"]

    result = await client.post(f"/api/v1/secrets/{secret_id}/test")
    assert result.json() == {"ok": True}

    del os.environ["HARNESS_API_TEST_SECRET"]
    result = await client.post(f"/api/v1/secrets/{secret_id}/test")
    assert result.json() == {"ok": False}


@pytest.mark.asyncio
async def test_duplicate_secret_name_rejected(client) -> None:
    await client.post("/api/v1/secrets", json={"name": "dup", "kind": "env", "target": "A"})
    resp = await client.post("/api/v1/secrets", json={"name": "dup", "kind": "env", "target": "B"})
    assert resp.status_code == 409
