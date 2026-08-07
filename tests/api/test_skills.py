"""SKL-001: skill package registry — metadata indexes without loading the
SKILL.md body; activation (via `POST /skills/{id}/activate` or the
`skills.activate` meta-tool) fetches the body and adds it to that session's
next context compile only, proven through the real run loop and
ContextCompiler, not by asserting on the repo functions alone.
"""

from __future__ import annotations

import asyncio

import pytest


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def _run_tool(client, tool_name: str, arguments: dict) -> dict:
    resp = await client.post(f"/api/v1/tools/{tool_name}/run", json={"arguments": arguments})
    assert resp.status_code == 202
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded", job
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": tool_name})
    return runs.json()[0]["result"]  # most-recent-first (ORDER BY created_at DESC)


_SKILL_BODY = (
    "Run tests with `pytest -q`. Prefer real fixtures over mocks. Add a regression "
    "test alongside every bug fix."
)


async def _create_skill(client, name: str = "python-testing") -> dict:
    resp = await client.post(
        "/api/v1/skills",
        json={
            "name": name,
            "description": "Python testing methodology.",
            "activation_hints": ["*.py", "pytest"],
            "required_capabilities": ["shell.exec"],
            "scripts": ["run_tests.sh"],
            "reference_docs": ["pytest_conventions.md"],
            "body": _SKILL_BODY,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_skill_estimates_tokens_when_not_given(client) -> None:
    skill = await _create_skill(client)
    assert skill["name"] == "python-testing"
    assert skill["estimated_tokens"] > 0
    assert skill["scripts"] == ["run_tests.sh"]
    assert skill["reference_docs"] == ["pytest_conventions.md"]
    assert skill["body"] == _SKILL_BODY


@pytest.mark.asyncio
async def test_create_skill_honors_explicit_estimated_tokens(client) -> None:
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "explicit-cost", "body": "x", "estimated_tokens": 700},
    )
    assert resp.json()["estimated_tokens"] == 700


@pytest.mark.asyncio
async def test_list_skills_never_returns_the_body(client) -> None:
    await _create_skill(client)
    listed = await client.get("/api/v1/skills")
    assert listed.status_code == 200
    entries = listed.json()
    assert len(entries) == 1
    assert entries[0]["name"] == "python-testing"
    assert "body" not in entries[0]
    assert "scripts" not in entries[0]
    assert "reference_docs" not in entries[0]


@pytest.mark.asyncio
async def test_duplicate_skill_name_rejected(client) -> None:
    await _create_skill(client)
    dup = await client.post("/api/v1/skills", json={"name": "python-testing", "body": "x"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_delete_skill(client) -> None:
    skill = await _create_skill(client)
    deleted = await client.delete(f"/api/v1/skills/{skill['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/skills")).json() == []


@pytest.mark.asyncio
async def test_skills_activate_is_registered_as_a_tool(client) -> None:
    resp = await client.get("/api/v1/tools")
    by_name = {t["name"]: t for t in resp.json()}
    assert by_name["skills.activate"]["permission_class"] == "read"
    assert set(by_name["skills.activate"]["parameters_schema"]["required"]) == {
        "session_id",
        "skill_id",
    }


@pytest.mark.asyncio
async def test_capabilities_search_finds_the_skill(client) -> None:
    await _create_skill(client)
    result = await _run_tool(client, "capabilities.search", {"query": "pytest"})
    candidates = result["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["kind"] == "skill"
    assert candidates[0]["name"] == "python-testing"
    assert candidates[0]["trust_class"] == "read"
    # The compact search result never carries the skill body.
    assert "body" not in candidates[0]


async def _create_contact_and_session(client) -> str:
    await client.post(
        "/api/v1/contacts",
        json={
            "handle": "builder",
            "display_name": "Builder",
            "binding": {"provider": "fake", "model": "fake-mini"},
        },
    )
    session = await client.post("/api/v1/sessions", json={"title": "t", "contacts": ["builder"]})
    return session.json()["id"]


async def _skills_budget_for_latest_run(harness_app, session_id: str) -> int:
    events = await harness_app.events.replay(0)
    compiled = [
        e
        for e in events
        if e.type == "context.compiled" and e.context.get("session_id") == session_id
    ]
    assert compiled, "no context.compiled event recorded"
    return int(compiled[-1].payload["sections"]["skills"])


@pytest.mark.asyncio
async def test_rest_activate_adds_skill_to_next_compile_only(client, harness_app) -> None:
    skill = await _create_skill(client)
    session_id = await _create_contact_and_session(client)

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder hi there"}
    )
    assert await _skills_budget_for_latest_run(harness_app, session_id) == 0

    activate_resp = await client.post(
        f"/api/v1/skills/{skill['id']}/activate", json={"session_id": session_id}
    )
    assert activate_resp.status_code == 200
    body = activate_resp.json()
    assert body["name"] == "python-testing"
    assert body["body"] == _SKILL_BODY

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder hi again"}
    )
    assert await _skills_budget_for_latest_run(harness_app, session_id) > 0


@pytest.mark.asyncio
async def test_tool_call_activation_also_adds_skill_to_next_compile(client, harness_app) -> None:
    skill = await _create_skill(client)
    session_id = await _create_contact_and_session(client)

    describe_result = await _run_tool(
        client, "skills.activate", {"session_id": session_id, "skill_id": skill["id"]}
    )
    assert describe_result["body"] == _SKILL_BODY

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "@builder go"})
    assert await _skills_budget_for_latest_run(harness_app, session_id) > 0


@pytest.mark.asyncio
async def test_activation_is_idempotent_across_repeated_calls(client, harness_app) -> None:
    skill = await _create_skill(client)
    session_id = await _create_contact_and_session(client)
    for _ in range(3):
        await client.post(f"/api/v1/skills/{skill['id']}/activate", json={"session_id": session_id})

    activated = await harness_app.skill_activations.list_for_session(session_id)
    assert len(activated) == 1


@pytest.mark.asyncio
async def test_activating_unknown_skill_404s(client) -> None:
    resp = await client.post(
        "/api/v1/skills/skill_doesnotexist/activate", json={"session_id": "ses_x"}
    )
    assert resp.status_code == 404
