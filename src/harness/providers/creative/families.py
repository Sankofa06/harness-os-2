"""Stability Matrix package family catalog (CRE-001, SPEC/CREATIVE_COMPUTE.md
"Stability Matrix package families"). Data-driven and declarative — like
`harness.skills.superpowers.BUNDLES` — so newly-seen package types simply
fail to match and surface as ``unknown/custom`` rather than crashing
discovery (SPEC: "Package discovery MUST be data-driven so newly installed
package types can appear as unknown/custom... rather than crashing").

Matching is done by case-insensitive substring against Stability Matrix's own
``PackageName``/``DisplayName`` fields, checked in catalog order (first match
wins) — more specific families (e.g. "reForge") are listed before the more
generic ones their names overlap with (e.g. "Forge", "AUTOMATIC1111").

Provenance: Stability Matrix (github.com/LykosAI/StabilityMatrix) has no
published schema doc; this module is built from source inspection of its
`InstalledPackage`/`BasePackage` classes (verified: `settings.json`'s
`InstalledPackages` array is the *only* per-install metadata Stability Matrix
persists — there is no per-package folder metadata file — and the confirmed
`PackageName` values are ``ComfyUI``, ``stable-diffusion-webui``,
``stable-diffusion-webui-forge``, ``Fooocus``, and ``InvokeAI``). The other
~15 families below (Fooocus variants, SD.Next, StableSwarmUI, training
engines, etc.) are declared from SPEC/CREATIVE_COMPUTE.md's required family
list using their public display names as match patterns — their exact
`PackageName` strings were not independently verified against source, so
matching falls back to the human-readable `DisplayName` Stability Matrix
already shows the user, which is the same string a real operator would
recognize their installation by.
"""

from __future__ import annotations

from dataclasses import dataclass

Platform = str  # "windows" | "macos" | "linux"


@dataclass(frozen=True)
class CreativePackageFamily:
    id: str
    display_name: str
    group: str
    name_patterns: tuple[str, ...]
    supported_platforms: tuple[Platform, ...]


# Order matters: more specific patterns must precede the generic ones their
# names are substrings of (reForge/AMDGPU Forge/Forge before AUTOMATIC1111;
# DirectML variant before the plain one; Fooocus variants before bare
# Fooocus).
FAMILIES: tuple[CreativePackageFamily, ...] = (
    CreativePackageFamily(
        id="sdwebui_reforge",
        display_name="Stable Diffusion WebUI reForge",
        group="sd_webui",
        name_patterns=("reforge",),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="sdwebui_amdgpu_forge",
        display_name="Stable Diffusion WebUI AMDGPU Forge",
        group="sd_webui",
        name_patterns=("amdgpu forge", "amdgpu-forge", "forge-amdgpu"),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="sdwebui_forge",
        display_name="Stable Diffusion WebUI Forge",
        group="sd_webui",
        name_patterns=("webui-forge", "webui forge", "sd-forge"),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="automatic1111_directml",
        display_name="AUTOMATIC1111 DirectML",
        group="sd_webui",
        name_patterns=("directml",),
        supported_platforms=("windows",),
    ),
    CreativePackageFamily(
        id="sdwebui_ux",
        display_name="SD Web UI-UX",
        group="sd_webui",
        name_patterns=("webui-ux", "webui ux"),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="sdnext",
        display_name="SD.Next",
        group="sd_webui",
        name_patterns=("sd.next", "sdnext", "vladautomatic"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="automatic1111",
        display_name="AUTOMATIC1111",
        group="sd_webui",
        name_patterns=("automatic1111", "a1111", "stable-diffusion-webui"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="fooocus_mre",
        display_name="Fooocus MRE",
        group="fooocus",
        name_patterns=("fooocus mre", "fooocusmre"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="fooocus_controlnet_sdxl",
        display_name="Fooocus ControlNet SDXL",
        group="fooocus",
        name_patterns=("fooocus controlnet",),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="ruined_fooocus",
        display_name="Ruined Fooocus",
        group="fooocus",
        name_patterns=("ruined fooocus", "ruinedfooocus"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="fooocus_1up",
        display_name="Fooocus 1-Up Edition",
        group="fooocus",
        name_patterns=("1-up", "fooocus 1-up"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="simplesdxl",
        display_name="SimpleSDXL",
        group="fooocus",
        name_patterns=("simplesdxl",),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="fooocus",
        display_name="Fooocus",
        group="fooocus",
        name_patterns=("fooocus",),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="comfyui",
        display_name="ComfyUI",
        group="node_workflow",
        name_patterns=("comfyui",),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="stableswarmui",
        display_name="StableSwarmUI / SwarmUI",
        group="node_workflow",
        name_patterns=("swarmui", "stableswarm"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="sdfx",
        display_name="SDFX",
        group="node_workflow",
        name_patterns=("sdfx",),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="voltaml",
        display_name="VoltaML",
        group="other_inference",
        name_patterns=("voltaml",),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="invokeai",
        display_name="InvokeAI",
        group="other_inference",
        name_patterns=("invokeai", "invoke-ai", "invoke ai"),
        supported_platforms=("windows", "linux", "macos"),
    ),
    CreativePackageFamily(
        id="kohya_gui",
        display_name="Kohya GUI",
        group="training",
        name_patterns=("kohya",),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="onetrainer",
        display_name="OneTrainer",
        group="training",
        name_patterns=("onetrainer", "one trainer"),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="fluxgym",
        display_name="FluxGym",
        group="training",
        name_patterns=("fluxgym", "flux gym"),
        supported_platforms=("windows", "linux"),
    ),
    CreativePackageFamily(
        id="cogstudio",
        display_name="CogVideo via CogStudio",
        group="video",
        name_patterns=("cogstudio", "cogvideo"),
        supported_platforms=("windows", "linux"),
    ),
)

FAMILIES_BY_ID: dict[str, CreativePackageFamily] = {f.id: f for f in FAMILIES}

UNKNOWN_FAMILY_ID = "unknown"
UNKNOWN_FAMILY_DISPLAY_NAME = "Unknown/Custom"
UNKNOWN_FAMILY_GROUP = "unknown"


def match_family(package_name: str, display_name: str) -> CreativePackageFamily | None:
    haystack = f"{package_name} {display_name}".lower()
    for family in FAMILIES:
        if any(pattern in haystack for pattern in family.name_patterns):
            return family
    return None
