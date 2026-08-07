import pytest


@pytest.mark.asyncio
async def test_get_transcript_state_defaults_to_empty(client) -> None:
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": []})
    session_id = session.json()["id"]

    resp = await client.get(f"/api/v1/sessions/{session_id}/transcript-state")
    assert resp.status_code == 200
    assert resp.json() == {
        "session_id": session_id,
        "unresolved_requirements": [],
        "current_plan": "",
        "changed_files": [],
        "failing_tests": [],
        "permission_decisions": [],
        "rolling_summary": "",
        "updated_at": "",
    }


@pytest.mark.asyncio
async def test_get_transcript_state_for_unknown_session_404s(client) -> None:
    resp = await client.get("/api/v1/sessions/ses_doesnotexist/transcript-state")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_transcript_state_updates_only_given_fields(client) -> None:
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": []})
    session_id = session.json()["id"]

    first = await client.patch(
        f"/api/v1/sessions/{session_id}/transcript-state",
        json={
            "unresolved_requirements": ["add login"],
            "current_plan": "wire up auth",
        },
    )
    assert first.status_code == 200
    assert first.json()["unresolved_requirements"] == ["add login"]
    assert first.json()["current_plan"] == "wire up auth"

    second = await client.patch(
        f"/api/v1/sessions/{session_id}/transcript-state",
        json={"changed_files": ["src/auth.py"]},
    )
    assert second.status_code == 200
    # Fields not included in this PATCH are untouched.
    assert second.json()["unresolved_requirements"] == ["add login"]
    assert second.json()["current_plan"] == "wire up auth"
    assert second.json()["changed_files"] == ["src/auth.py"]

    fetched = await client.get(f"/api/v1/sessions/{session_id}/transcript-state")
    assert fetched.json()["changed_files"] == ["src/auth.py"]


@pytest.mark.asyncio
async def test_run_loop_compiles_protected_facts_into_context(client, harness_app) -> None:
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

    await client.patch(
        f"/api/v1/sessions/{session_id}/transcript-state",
        json={
            "unresolved_requirements": ["ship the login page"],
            "failing_tests": ["test_login_redirects"],
        },
    )

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "@builder status?"},
    )
    assert resp.status_code == 200

    events = await harness_app.events.replay(0)
    compiled_events = [
        e
        for e in events
        if e.type == "context.compiled" and e.context.get("session_id") == session_id
    ]
    assert len(compiled_events) == 1
    assert compiled_events[0].payload["sections"]["protected_facts"] > 0
