"""CRE-002: per-engine capability model — unit tests over the declarative
`harness.providers.creative.families` catalog directly (no API/network
needed; this is pure data), proving the catalog matches SPEC/
CREATIVE_COMPUTE.md's integration-strategy hierarchy and, critically, that
"no fake controls" holds: every family is honestly `implemented=False` since
no live adapter exists yet.
"""

from __future__ import annotations

from harness.providers.creative.families import FAMILIES, FAMILIES_BY_ID, match_family


def test_every_family_declares_a_full_capability_model() -> None:
    for family in FAMILIES:
        assert family.supported_platforms, family.id
        assert family.acceleration_backends, family.id
        assert family.api_strategy in {
            "native_api",
            "compat_layer",
            "http_adapter",
            "launch_fs",
            "read_only",
        }, family.id
        assert family.launch_strategy == "managed_process", family.id
        assert family.asset_types, family.id
        assert family.capability_set, family.id


def test_no_fake_controls_nothing_is_implemented_yet() -> None:
    """CRE-002's acceptance bar: this milestone only builds the declarative
    model. Any family claiming `implemented=True` here would be a fake
    control, since no live adapter (CRE-003+) exists yet.
    """
    assert all(not family.implemented for family in FAMILIES)


def test_comfyui_is_http_adapter_tier_with_deep_capabilities() -> None:
    comfy = FAMILIES_BY_ID["comfyui"]
    assert comfy.api_strategy == "http_adapter"
    assert "workflow_submit" in comfy.capability_set
    assert "workflow_storage_by_reference" in comfy.capability_set
    assert "workflow" in comfy.asset_types


def test_automatic1111_compatible_family_is_compat_layer_tier() -> None:
    a1111 = FAMILIES_BY_ID["automatic1111"]
    assert a1111.api_strategy == "compat_layer"
    assert {"txt2img", "img2img", "loras", "vaes"} <= set(a1111.capability_set)


def test_invokeai_is_native_api_tier_not_assumed_a1111_compatible() -> None:
    """SPEC: "Use its native API if detected... do not assume A1111
    compatibility." InvokeAI must not share AUTOMATIC1111's capability_set.
    """
    invoke = FAMILIES_BY_ID["invokeai"]
    assert invoke.api_strategy == "native_api"
    assert "txt2img" not in invoke.capability_set


def test_fooocus_family_without_stable_api_is_launch_fs_tier() -> None:
    """SPEC: "Prefer launch/health/read-only asset integration unless a
    reliable local API is explicitly detected" for Fooocus-family packages.
    """
    for family_id in (
        "fooocus",
        "fooocus_mre",
        "fooocus_controlnet_sdxl",
        "ruined_fooocus",
        "fooocus_1up",
        "simplesdxl",
    ):
        family = FAMILIES_BY_ID[family_id]
        assert family.api_strategy == "launch_fs", family_id
        assert "launch" in family.capability_set


def test_directml_and_amd_variants_declare_the_matching_backend_not_cuda() -> None:
    directml = FAMILIES_BY_ID["automatic1111_directml"]
    assert directml.acceleration_backends == ("directml", "cpu")
    assert "cuda" not in directml.acceleration_backends

    amdgpu_forge = FAMILIES_BY_ID["sdwebui_amdgpu_forge"]
    assert "rocm_hip" in amdgpu_forge.acceleration_backends
    assert "directml" in amdgpu_forge.acceleration_backends
    assert "cuda" not in amdgpu_forge.acceleration_backends


def test_training_engines_are_launch_fs_not_directly_agent_controllable() -> None:
    """SPEC: training engines "are not implicitly available to LLM agents"."""
    for family_id in ("kohya_gui", "onetrainer", "fluxgym"):
        family = FAMILIES_BY_ID[family_id]
        assert family.api_strategy == "launch_fs", family_id
        assert "training_output" in family.asset_types


def test_all_spec_required_families_are_present() -> None:
    # SPEC/CREATIVE_COMPUTE.md's family lists: SD WebUI (7) + Fooocus (6) +
    # node/workflow (3) + other inference (2) + training (3) + video (1).
    assert len(FAMILIES) == 22
    assert len({f.id for f in FAMILIES}) == 22  # no duplicate ids


def test_match_family_still_works_after_capability_fields_were_added() -> None:
    """Regression guard: CRE-002 extended CreativePackageFamily with new
    fields but must not have changed CRE-001's matching behavior.
    """
    forge = match_family("stable-diffusion-webui-forge", "Stable Diffusion WebUI Forge")
    assert forge is not None
    assert forge.id == "sdwebui_forge"
