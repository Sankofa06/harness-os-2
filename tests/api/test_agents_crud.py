import pytest


@pytest.mark.asyncio
async def test_seed_roles_present(client) -> None:
    resp = await client.get("/api/v1/roles")
    names = {r["name"] for r in resp.json()}
    assert {
        "orchestrator",
        "architect",
        "coder",
        "reviewer",
        "tester",
        "researcher",
        "designer",
        "operator",
    } <= names


@pytest.mark.asyncio
async def test_seed_personas_present(client) -> None:
    resp = await client.get("/api/v1/personas")
    names = {p["name"] for p in resp.json()}
    assert "concise" in names
    assert "test-first" in names


@pytest.mark.asyncio
async def test_create_contact_with_role_and_personas(client) -> None:
    resp = await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "role": "coder",
            "personas": ["concise"],
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["handle"] == "builder"
    assert body["binding"]["provider"] == "fake"


@pytest.mark.asyncio
async def test_create_contact_unknown_role_rejected(client) -> None:
    resp = await client.post(
        "/api/v1/contacts", json={"handle": "x", "display_name": "X", "role": "nope"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contact_identity_survives_rebinding_via_api(client) -> None:
    created = await client.post(
        "/api/v1/contacts",
        json={
            "handle": "swap",
            "display_name": "Swap",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    contact_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/contacts/{contact_id}",
        json={"binding": {"provider": "fake", "model": "fake-large"}},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["id"] == contact_id
    assert body["handle"] == "swap"
    assert body["binding"]["model"] == "fake-large"


@pytest.mark.asyncio
async def test_create_team(client) -> None:
    await client.post("/api/v1/contacts", json={"handle": "a", "display_name": "A"})
    await client.post("/api/v1/contacts", json={"handle": "b", "display_name": "B"})
    resp = await client.post(
        "/api/v1/teams",
        json={"handle": "dev-team", "display_name": "Dev Team", "members": ["a", "b"]},
    )
    assert resp.status_code == 201
    assert len(resp.json()["member_ids"]) == 2
