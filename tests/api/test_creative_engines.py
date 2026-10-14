"""CRE-002: `GET /creative/engines*` endpoints — served entirely from the
declarative capability catalog, no Host/network involved.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_engines_returns_all_families(client) -> None:
    resp = await client.get("/api/v1/creative/engines")
    assert resp.status_code == 200
    engines = resp.json()
    assert len(engines) == 22
    by_id = {e["id"]: e for e in engines}
    # ComfyUI (CRE-003), the AUTOMATIC1111-compatible family (CRE-004), and
    # everything else at its honest launch_fs/native-detection tier
    # (CRE-005) all have real, if differently-deep, implementations now.
    assert by_id["comfyui"]["implemented"] is True
    assert by_id["automatic1111"]["implemented"] is True
    assert by_id["invokeai"]["implemented"] is True
    assert by_id["fooocus"]["implemented"] is True


@pytest.mark.asyncio
async def test_get_single_engine(client) -> None:
    resp = await client.get("/api/v1/creative/engines/comfyui")
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "ComfyUI"
    assert body["api_strategy"] == "http_adapter"
    assert "workflow_submit" in body["capability_set"]


@pytest.mark.asyncio
async def test_get_unknown_engine_404s(client) -> None:
    resp = await client.get("/api/v1/creative/engines/does-not-exist")
    assert resp.status_code == 404

    capabilities = await client.get("/api/v1/creative/engines/does-not-exist/capabilities")
    assert capabilities.status_code == 404

    schema = await client.get("/api/v1/creative/engines/does-not-exist/settings-schema")
    assert schema.status_code == 404


@pytest.mark.asyncio
async def test_engine_capabilities_endpoint_matches_engine_listing(client) -> None:
    engine = (await client.get("/api/v1/creative/engines/automatic1111")).json()
    capabilities = (await client.get("/api/v1/creative/engines/automatic1111/capabilities")).json()
    assert capabilities["capability_set"] == engine["capability_set"]
    assert capabilities["asset_types"] == engine["asset_types"]
    assert capabilities["implemented"] is True  # CRE-004 gave it a real adapter


@pytest.mark.asyncio
async def test_fooocus_family_declares_the_lighter_launch_fs_tier_honestly(client) -> None:
    """Fooocus has no documented control API — its capability_set must stay
    at the generic launch/health level CRE-005 actually built, never claim
    generation verbs it can't back (SPEC: "no fake controls").
    """
    capabilities = (await client.get("/api/v1/creative/engines/fooocus/capabilities")).json()
    assert capabilities["api_strategy"] == "launch_fs"
    assert "txt2img" not in capabilities["capability_set"]
    assert {"launch", "health_check"} <= set(capabilities["capability_set"])
    assert capabilities["implemented"] is True


@pytest.mark.asyncio
async def test_engine_settings_schema_is_generic_launch_args_only(client) -> None:
    """No engine has settings-schema-validated per-request fields yet, so
    the settings schema must not fabricate engine-specific fields — only
    the genuinely real, Stability-Matrix-tracked launch-args concept.
    """
    resp = await client.get("/api/v1/creative/engines/comfyui/settings-schema")
    assert resp.status_code == 200
    schema = resp.json()
    assert "extra_launch_args" in schema["common"]["properties"]
    assert schema["provider"] == {}
    assert schema["allow_passthrough"] is False
