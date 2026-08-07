"""CRE-001: Stability Matrix installation discovery, tested directly against a
fixture `settings.json` text — the real (verified via source inspection, see
`harness.providers.creative.families`) shape Stability Matrix itself writes,
with one deliberately-unrecognized package to prove the `unknown/custom`
fallback (SPEC/CREATIVE_COMPUTE.md: "unknown packages MUST appear as
unknown/custom with detectable... metadata rather than crashing").
"""

from __future__ import annotations

import json

from harness.providers.creative.discovery import parse_installed_packages

FIXTURE_SETTINGS = {
    "InstalledPackages": [
        {
            "Id": "11111111-1111-1111-1111-111111111111",
            "DisplayName": "ComfyUI",
            "PackageName": "ComfyUI",
            "LibraryPath": "Packages/ComfyUI",
            "LaunchCommand": "main.py",
            "PythonVersion": "3.11.9",
            "Version": {"InstalledReleaseVersion": "0.3.7"},
        },
        {
            "Id": "22222222-2222-2222-2222-222222222222",
            "DisplayName": "Stable Diffusion WebUI Forge",
            "PackageName": "stable-diffusion-webui-forge",
            "LibraryPath": "Packages/stable-diffusion-webui-forge",
            "LaunchCommand": "launch.py",
            "PythonVersion": "3.10.11",
        },
        {
            "Id": "33333333-3333-3333-3333-333333333333",
            "DisplayName": "AUTOMATIC1111",
            "PackageName": "stable-diffusion-webui",
            "LibraryPath": "Packages/stable-diffusion-webui",
            "LaunchCommand": "webui-user.bat",
            "PythonVersion": "3.10.6",
        },
        {
            "Id": "44444444-4444-4444-4444-444444444444",
            "DisplayName": "Fooocus",
            "PackageName": "Fooocus",
            "LibraryPath": "Packages/Fooocus",
            "PythonVersion": "3.10.9",
        },
        {
            "Id": "55555555-5555-5555-5555-555555555555",
            "DisplayName": "InvokeAI",
            "PackageName": "InvokeAI",
            "LibraryPath": "Packages/InvokeAI",
            "PythonVersion": "3.11.4",
        },
        {
            "Id": "66666666-6666-6666-6666-666666666666",
            "DisplayName": "SomeBrandNewGenerator",
            "PackageName": "some-brand-new-generator",
            "LibraryPath": "Packages/SomeBrandNewGenerator",
            "LaunchCommand": "run.sh",
            "PythonVersion": "3.12.0",
        },
        {
            "Id": "77777777-7777-7777-7777-777777777777",
            "DisplayName": "AUTOMATIC1111 DirectML",
            "PackageName": "stable-diffusion-webui-directml",
            "LibraryPath": "Packages/stable-diffusion-webui-directml",
            "PythonVersion": "3.10.6",
        },
    ]
}


def test_discovers_all_entries() -> None:
    results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="windows")
    assert len(results) == len(FIXTURE_SETTINGS["InstalledPackages"])


def test_comfyui_matches_its_family() -> None:
    results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="windows")
    comfy = next(r for r in results if r.package_name == "ComfyUI")
    assert comfy.family_id == "comfyui"
    assert comfy.family_display_name == "ComfyUI"
    assert comfy.family_group == "node_workflow"
    assert comfy.platform_supported is True
    assert comfy.library_path == "Packages/ComfyUI"
    assert comfy.python_version == "3.11.9"


def test_forge_is_distinguished_from_bare_automatic1111() -> None:
    """`stable-diffusion-webui-forge` contains `stable-diffusion-webui` as a
    literal substring — the family catalog's match order must not let it fall
    through to the generic AUTOMATIC1111 family.
    """
    results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="windows")
    forge = next(r for r in results if r.package_name == "stable-diffusion-webui-forge")
    a1111 = next(r for r in results if r.package_name == "stable-diffusion-webui")
    assert forge.family_id == "sdwebui_forge"
    assert a1111.family_id == "automatic1111"
    assert forge.family_id != a1111.family_id


def test_fooocus_and_invokeai_match_their_families() -> None:
    results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="linux")
    fooocus = next(r for r in results if r.package_name == "Fooocus")
    invoke = next(r for r in results if r.package_name == "InvokeAI")
    assert fooocus.family_id == "fooocus"
    assert fooocus.family_group == "fooocus"
    assert invoke.family_id == "invokeai"
    assert invoke.family_group == "other_inference"


def test_unrecognized_package_falls_back_to_unknown_custom_with_raw_metadata() -> None:
    results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="linux")
    unknown = next(r for r in results if r.package_name == "some-brand-new-generator")
    assert unknown.family_id == "unknown"
    assert unknown.family_display_name == "Unknown/Custom"
    assert unknown.family_group == "unknown"
    assert unknown.supported_platforms == ()
    assert unknown.platform_supported is False
    # Detected metadata is preserved even though the package wasn't recognized.
    assert unknown.raw["LaunchCommand"] == "run.sh"
    assert unknown.raw["PythonVersion"] == "3.12.0"


def test_platform_supported_reflects_the_scanned_platform() -> None:
    """AUTOMATIC1111 DirectML is declared Windows-only — the same installed
    package must report supported on a Windows scan and unsupported on a
    macOS/Linux scan of the exact same Data directory.
    """
    windows_results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="windows")
    macos_results = parse_installed_packages(json.dumps(FIXTURE_SETTINGS), platform="macos")

    windows_directml = next(
        r for r in windows_results if r.package_name == "stable-diffusion-webui-directml"
    )
    macos_directml = next(
        r for r in macos_results if r.package_name == "stable-diffusion-webui-directml"
    )
    assert windows_directml.family_id == "automatic1111_directml"
    assert windows_directml.platform_supported is True
    assert macos_directml.platform_supported is False


def test_empty_installed_packages_returns_empty_list() -> None:
    results = parse_installed_packages(json.dumps({"InstalledPackages": []}), platform="windows")
    assert results == []


def test_missing_installed_packages_key_returns_empty_list() -> None:
    results = parse_installed_packages(json.dumps({}), platform="windows")
    assert results == []
