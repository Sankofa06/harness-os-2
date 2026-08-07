"""SKL-002: superpower bundle toggles gate `capabilities.search`'s discovery
surface only — they never touch PERM-001's permission policies, and a gated
tool remains directly callable and fully visible in `GET /tools` regardless
of its bundle's toggle state ("toggles modify exposed surface only").
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


async def _search(client, query: str) -> set[str]:
    resp = await client.post(
        "/api/v1/tools/capabilities.search/run", json={"arguments": {"query": query}}
    )
    job = await _wait_for_job(client, resp.json()["id"])
    assert job["status"] == "succeeded"
    runs = await client.get("/api/v1/tools/runs", params={"tool_name": "capabilities.search"})
    # most-recent-first (ORDER BY created_at DESC) — [0] is this call's own result.
    return {c["name"] for c in runs.json()[0]["result"]["candidates"]}


@pytest.mark.asyncio
async def test_list_superpowers_returns_all_seven_seed_bundles_disabled_by_default(
    client,
) -> None:
    resp = await client.get("/api/v1/superpowers")
    assert resp.status_code == 200
    by_id = {b["id"]: b for b in resp.json()}
    assert set(by_id) == {
        "coding",
        "git_github",
        "browser",
        "creative",
        "research",
        "remote_host",
        "benchmarking",
    }
    assert all(b["enabled"] is False for b in by_id.values())
    assert by_id["coding"]["tool_names"] == [
        "fs_read_file",
        "fs_write_file",
        "fs_list_dir",
        "shell_exec",
    ]
    # Undeveloped-subsystem bundles are honestly empty, not padded with placeholders.
    assert by_id["browser"]["tool_names"] == []


@pytest.mark.asyncio
async def test_toggling_unknown_bundle_404s(client) -> None:
    resp = await client.put("/api/v1/superpowers/does-not-exist", json={"enabled": True})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gated_tool_absent_from_search_until_bundle_enabled(client) -> None:
    before = await _search(client, "shell")
    assert "shell_exec" not in before

    toggled = await client.put("/api/v1/superpowers/coding", json={"enabled": True})
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is True

    after = await _search(client, "shell")
    assert "shell_exec" in after


@pytest.mark.asyncio
async def test_disabling_bundle_again_hides_it_from_search(client) -> None:
    await client.put("/api/v1/superpowers/git_github", json={"enabled": True})
    assert "git_status" in await _search(client, "git")

    await client.put("/api/v1/superpowers/git_github", json={"enabled": False})
    assert "git_status" not in await _search(client, "git")


@pytest.mark.asyncio
async def test_ungated_tools_are_always_discoverable(client) -> None:
    names = await _search(client, "")
    assert "echo" in names


@pytest.mark.asyncio
async def test_gated_tool_stays_fully_visible_in_get_tools_regardless_of_toggle(client) -> None:
    resp = await client.get("/api/v1/tools")
    by_name = {t["name"] for t in resp.json()}
    assert "shell_exec" in by_name
    assert "git_status" in by_name


@pytest.mark.asyncio
async def test_toggle_never_touches_permission_policy(client) -> None:
    before = await client.get("/api/v1/permissions/policies")
    before_by_class = {p["permission_class"]: p["policy"] for p in before.json()}

    await client.put("/api/v1/superpowers/coding", json={"enabled": True})
    await client.put("/api/v1/superpowers/git_github", json={"enabled": True})

    after = await client.get("/api/v1/permissions/policies")
    after_by_class = {p["permission_class"]: p["policy"] for p in after.json()}
    assert before_by_class == after_by_class


@pytest.mark.asyncio
async def test_gated_tool_remains_callable_even_when_bundle_disabled(client) -> None:
    """`fs_list_dir` belongs to the (currently disabled) coding bundle, so it's
    hidden from capabilities.search — but exposure gating never touches
    execution: the call still reaches the real handler, which fails on a
    genuinely unknown workspace rather than being rejected for "not exposed."
    """
    superpowers = await client.get("/api/v1/superpowers")
    assert all(b["enabled"] is False for b in superpowers.json())
    assert "fs_list_dir" not in await _search(client, "list")

    resp = await client.post(
        "/api/v1/tools/fs_list_dir/run",
        json={"arguments": {"workspace_id": "ws_doesnotexist"}},
    )
    assert resp.status_code == 202  # accepted and scheduled — not rejected as "unexposed"
    job = await _wait_for_job(client, resp.json()["id"])
    # The call reaches all the way to persisting a ToolRun against a genuinely
    # unknown workspace (a foreign-key failure deep in TOOL-002's own
    # machinery) — proof it was never turned away for exposure reasons.
    assert job["status"] == "failed"
    assert "ws_doesnotexist" in job["error"]
