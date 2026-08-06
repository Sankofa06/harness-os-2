import pytest


@pytest.mark.asyncio
async def test_mention_routes_to_contact_and_streams_reply(client) -> None:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    session = await client.post("/api/v1/sessions", json={"title": "demo", "contacts": ["builder"]})
    session_id = session.json()["id"]

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "@builder please say hello"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["runs"]) == 1
    run = body["runs"][0]
    assert run["contact_handle"] == "builder"
    assert run["status"] == "succeeded"
    assert "hello" in run["content"].lower()


@pytest.mark.asyncio
async def test_no_mention_falls_back_to_session_members(client) -> None:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "solo",
            "display_name": "Solo",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    session = await client.post("/api/v1/sessions", json={"title": "demo", "contacts": ["solo"]})
    session_id = session.json()["id"]

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "no mention here"}
    )
    body = resp.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["contact_handle"] == "solo"


@pytest.mark.asyncio
async def test_team_mention_fans_out_to_members(client) -> None:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "a",
            "display_name": "A",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "b",
            "display_name": "B",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    await client.post(
        "/api/v1/teams", json={"handle": "duo", "display_name": "Duo", "members": ["a", "b"]}
    )
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": ["a", "b"]})
    session_id = session.json()["id"]

    resp = await client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "@duo go"})
    handles = {r["contact_handle"] for r in resp.json()["runs"]}
    assert handles == {"a", "b"}


@pytest.mark.asyncio
async def test_session_binding_override_changes_model_without_losing_identity(client) -> None:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "rebind",
            "display_name": "Rebind",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    contacts = await client.get("/api/v1/contacts")
    contact_id = next(c["id"] for c in contacts.json() if c["handle"] == "rebind")

    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": ["rebind"]})
    session_id = session.json()["id"]

    override = await client.patch(
        f"/api/v1/sessions/{session_id}/contacts/{contact_id}/binding",
        json={"binding": {"model": "fake-large"}},
    )
    assert override.status_code == 200

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@rebind hi"}
    )
    run = resp.json()["runs"][0]
    assert run["contact_handle"] == "rebind"
    assert "fake-large" in run["content"]
