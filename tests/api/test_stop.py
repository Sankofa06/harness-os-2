import asyncio

import pytest

from harness.providers.language.fake import FakeProvider


async def _register_slow_fake_provider(client, harness_app, *, delay: float) -> str:
    """A FakeProvider instance with a real inter-token delay, registered under a
    freshly-created ProviderConfig's own ID — the same provider_id override
    build_provider() performs, done directly here so the test controls timing
    without needing network I/O or a new production config knob.
    """
    created = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "slow-fake"}
    )
    provider_id = created.json()["id"]
    slow_provider = FakeProvider(inter_token_delay=delay)
    slow_provider.provider_id = provider_id
    harness_app.providers.register(slow_provider)
    return provider_id


@pytest.mark.asyncio
async def test_stop_session_cancels_an_in_flight_run(client, harness_app) -> None:
    provider_id = await _register_slow_fake_provider(client, harness_app, delay=0.2)
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "binding": {"provider": provider_id, "model": "fake-mini"},
        },
    )
    session = await client.post("/api/v1/sessions", json={"title": "demo", "contacts": ["builder"]})
    session_id = session.json()["id"]

    messages_task = asyncio.ensure_future(
        client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"content": "@builder please say hello"},
        )
    )
    await asyncio.sleep(0.1)  # let the run start streaming before we cancel it

    stop_resp = await client.post(f"/api/v1/sessions/{session_id}/stop")
    assert stop_resp.status_code == 200
    assert len(stop_resp.json()["canceled_run_ids"]) == 1

    resp = await messages_task
    assert resp.status_code == 200
    run = resp.json()["runs"][0]
    assert run["status"] == "canceled"
    assert run["content"] == ""

    persisted = await harness_app.runs.get(run["run_id"])
    assert persisted.status == "canceled"
    assert persisted.finished_at is not None


@pytest.mark.asyncio
async def test_stop_session_with_nothing_running_cancels_nothing(client) -> None:
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": []})
    session_id = session.json()["id"]

    resp = await client.post(f"/api/v1/sessions/{session_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["canceled_run_ids"] == []


@pytest.mark.asyncio
async def test_stop_session_for_unknown_session_404s(client) -> None:
    resp = await client.post("/api/v1/sessions/ses_doesnotexist/stop")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stop_only_cancels_the_targeted_session(client, harness_app) -> None:
    provider_id = await _register_slow_fake_provider(client, harness_app, delay=0.2)
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "binding": {"provider": provider_id, "model": "fake-mini"},
        },
    )
    session_a = await client.post("/api/v1/sessions", json={"title": "a", "contacts": ["builder"]})
    session_b = await client.post("/api/v1/sessions", json={"title": "b", "contacts": ["builder"]})
    session_a_id = session_a.json()["id"]
    session_b_id = session_b.json()["id"]

    task_a = asyncio.ensure_future(
        client.post(f"/api/v1/sessions/{session_a_id}/messages", json={"content": "@builder hi"})
    )
    task_b = asyncio.ensure_future(
        client.post(f"/api/v1/sessions/{session_b_id}/messages", json={"content": "@builder hi"})
    )
    await asyncio.sleep(0.1)

    stop_resp = await client.post(f"/api/v1/sessions/{session_a_id}/stop")
    assert len(stop_resp.json()["canceled_run_ids"]) == 1

    resp_a = await task_a
    resp_b = await task_b
    assert resp_a.json()["runs"][0]["status"] == "canceled"
    assert resp_b.json()["runs"][0]["status"] == "succeeded"
