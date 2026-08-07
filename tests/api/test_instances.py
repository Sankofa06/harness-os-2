import asyncio

import pytest


async def _wait_for_job(client, job_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/api/v1/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


@pytest.mark.asyncio
async def test_list_models_aggregates_across_enabled_providers(client) -> None:
    await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "instances-fake"}
    )
    resp = await client.get("/api/v1/language/models")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()}
    assert "fake-mini" in ids


@pytest.mark.asyncio
async def test_list_models_scoped_to_one_provider(client) -> None:
    created = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "scoped-fake"}
    )
    provider_id = created.json()["id"]
    resp = await client.get(f"/api/v1/language/models?provider_config_id={provider_id}")
    assert resp.status_code == 200
    assert {m["id"] for m in resp.json()} == {"fake-mini", "fake-large"}


@pytest.mark.asyncio
async def test_load_then_unload_instance_via_job(client) -> None:
    created = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "load-fake"}
    )
    provider_id = created.json()["id"]

    load_resp = await client.post(
        "/api/v1/language/instances/load",
        json={"provider_config_id": provider_id, "model_id": "fake-mini"},
    )
    assert load_resp.status_code == 202
    job = await _wait_for_job(client, load_resp.json()["id"])
    assert job["status"] == "succeeded"

    instances = await client.get("/api/v1/language/instances")
    matching = [i for i in instances.json() if i["provider_config_id"] == provider_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "loaded"
    instance_id = matching[0]["id"]

    unload_resp = await client.post(f"/api/v1/language/instances/{instance_id}/unload")
    assert unload_resp.status_code == 202
    unload_job = await _wait_for_job(client, unload_resp.json()["id"])
    assert unload_job["status"] == "succeeded"

    final = await client.get(f"/api/v1/language/instances/{instance_id}")
    assert final.json()["status"] == "unloaded"


@pytest.mark.asyncio
async def test_settings_schema_and_update(client) -> None:
    created = await client.post(
        "/api/v1/language/providers", json={"type": "fake", "display_name": "settings-fake"}
    )
    provider_id = created.json()["id"]
    load_resp = await client.post(
        "/api/v1/language/instances/load",
        json={"provider_config_id": provider_id, "model_id": "fake-mini"},
    )
    await _wait_for_job(client, load_resp.json()["id"])
    instances = await client.get("/api/v1/language/instances")
    instance_id = instances.json()[0]["id"]

    schema = await client.get(f"/api/v1/language/instances/{instance_id}/settings-schema")
    assert schema.status_code == 200
    assert "common" in schema.json()

    updated = await client.patch(
        f"/api/v1/language/instances/{instance_id}/settings",
        json={"settings": {"common": {"temperature": 0.5}}},
    )
    assert updated.status_code == 200
    assert updated.json()["settings"]["common"]["temperature"] == 0.5

    rejected = await client.patch(
        f"/api/v1/language/instances/{instance_id}/settings",
        json={"settings": {"common": {"temperature": 99}}},
    )
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_load_unknown_provider_config_404s(client) -> None:
    resp = await client.post(
        "/api/v1/language/instances/load",
        json={"provider_config_id": "prov_missing", "model_id": "m"},
    )
    assert resp.status_code == 404
