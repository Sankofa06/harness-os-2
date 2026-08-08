"""Stability Matrix package family + engine capability catalog (CRE-001/
CRE-002, SPEC/CREATIVE_COMPUTE.md "Stability Matrix package families",
"Platform behavior", "Integration strategy hierarchy"). Data-driven and
declarative — like `harness.skills.superpowers.BUNDLES` — so newly-seen
package types simply fail to match and surface as ``unknown/custom`` rather
than crashing discovery (SPEC: "Package discovery MUST be data-driven so
newly installed package types can appear as unknown/custom... rather than
crashing").

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
~17 families below (Fooocus variants, SD.Next, StableSwarmUI, training
engines, etc.) are declared from SPEC/CREATIVE_COMPUTE.md's required family
list using their public display names as match patterns — their exact
`PackageName` strings were not independently verified against source, so
matching falls back to the human-readable `DisplayName` Stability Matrix
already shows the user, which is the same string a real operator would
recognize their installation by.

CRE-002 adds the per-engine capability model SPEC's "Platform behavior"
section calls for (``acceleration_backends``/``api_strategy``/
``launch_strategy``/``asset_types``/``capability_set``), plus ``implemented``
— every family is ``implemented=False`` right now, because CRE-002 is the
*declarative* capability model only; no live adapter exists yet for any
engine (that's CRE-003 onward, one engine at a time). ``capability_set``
describes what SPEC documents the underlying tool as *capable of*, not what
Harness can currently *do* — keeping the two separate is exactly what "no
fake controls" (CRE-002's acceptance criterion) means: a caller must be able
to tell the difference between "this engine supports X" and "Harness can
exercise X right now."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = str  # "windows" | "macos" | "linux"

# SPEC/CREATIVE_COMPUTE.md's "Integration strategy hierarchy", tiers 1-5.
ApiStrategy = Literal["native_api", "compat_layer", "http_adapter", "launch_fs", "read_only"]

# Every package Stability Matrix manages is launched the same way: it stores
# a per-install LaunchCommand and spawns that as a process (verified via
# CRE-001's source inspection) — there is no engine that skips this, so a
# single shared launch strategy is accurate, not a simplification.
_MANAGED_PROCESS = "managed_process"

_ALL_PLATFORM_BACKENDS = ("cuda", "rocm_hip", "metal_mps", "cpu")
_WIN_LINUX_BACKENDS = ("cuda", "rocm_hip", "cpu")
_CUDA_ONLY_BACKENDS = ("cuda", "cpu")
_DIRECTML_BACKENDS = ("directml", "cpu")
_AMD_BACKENDS = ("rocm_hip", "directml", "cpu")

_SD_WEBUI_ASSET_TYPES = (
    "checkpoint",
    "lora",
    "vae",
    "embedding",
    "controlnet",
    "upscaler",
    "image",
)
_SD_WEBUI_CAPABILITIES = (
    "txt2img",
    "img2img",
    "options",
    "samplers_schedulers",
    "models_checkpoints",
    "vaes",
    "loras",
    "progress",
    "interrupt",
    "extras_upscale",
)

_FOOOCUS_ASSET_TYPES = ("checkpoint", "lora", "vae", "image")
_LAUNCH_FS_CAPABILITIES = ("launch", "health_check", "read_only_asset_discovery")

_NODE_WORKFLOW_ASSET_TYPES = (
    "checkpoint",
    "diffusion_model",
    "lora",
    "vae",
    "embedding",
    "controlnet",
    "text_encoder",
    "clip",
    "upscaler",
    "workflow",
    "image",
)
_COMFYUI_CAPABILITIES = (
    "health",
    "object_info",
    "queue",
    "workflow_submit",
    "progress_events",
    "interrupt",
    "history",
    "image_upload",
    "workflow_storage_by_reference",
    "output_capture",
    "asset_discovery",
)
_STABLESWARMUI_CAPABILITIES = ("health", "queue", "workflow_submit", "progress_events")

_INVOKEAI_ASSET_TYPES = ("checkpoint", "lora", "vae", "controlnet", "image")
_INVOKEAI_CAPABILITIES = ("native_api_discovery", "capability_mapping")

_TRAINING_ASSET_TYPES = ("checkpoint", "lora", "training_output")
_VIDEO_ASSET_TYPES = ("checkpoint", "video")


@dataclass(frozen=True)
class CreativePackageFamily:
    id: str
    display_name: str
    group: str
    name_patterns: tuple[str, ...]
    supported_platforms: tuple[Platform, ...]
    acceleration_backends: tuple[str, ...] = field(default_factory=tuple)
    api_strategy: ApiStrategy = "read_only"
    launch_strategy: str = _MANAGED_PROCESS
    asset_types: tuple[str, ...] = field(default_factory=tuple)
    capability_set: tuple[str, ...] = field(default_factory=tuple)
    implemented: bool = False


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
        acceleration_backends=_WIN_LINUX_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="sdwebui_amdgpu_forge",
        display_name="Stable Diffusion WebUI AMDGPU Forge",
        group="sd_webui",
        name_patterns=("amdgpu forge", "amdgpu-forge", "forge-amdgpu"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_AMD_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="sdwebui_forge",
        display_name="Stable Diffusion WebUI Forge",
        group="sd_webui",
        name_patterns=("webui-forge", "webui forge", "sd-forge"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_WIN_LINUX_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="automatic1111_directml",
        display_name="AUTOMATIC1111 DirectML",
        group="sd_webui",
        name_patterns=("directml",),
        supported_platforms=("windows",),
        acceleration_backends=_DIRECTML_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="sdwebui_ux",
        display_name="SD Web UI-UX",
        group="sd_webui",
        name_patterns=("webui-ux", "webui ux"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_WIN_LINUX_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="sdnext",
        display_name="SD.Next",
        group="sd_webui",
        name_patterns=("sd.next", "sdnext", "vladautomatic"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="automatic1111",
        display_name="AUTOMATIC1111",
        group="sd_webui",
        name_patterns=("automatic1111", "a1111", "stable-diffusion-webui"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="compat_layer",
        asset_types=_SD_WEBUI_ASSET_TYPES,
        capability_set=_SD_WEBUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="fooocus_mre",
        display_name="Fooocus MRE",
        group="fooocus",
        name_patterns=("fooocus mre", "fooocusmre"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_FOOOCUS_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="fooocus_controlnet_sdxl",
        display_name="Fooocus ControlNet SDXL",
        group="fooocus",
        name_patterns=("fooocus controlnet",),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=(*_FOOOCUS_ASSET_TYPES, "controlnet"),
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="ruined_fooocus",
        display_name="Ruined Fooocus",
        group="fooocus",
        name_patterns=("ruined fooocus", "ruinedfooocus"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_FOOOCUS_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="fooocus_1up",
        display_name="Fooocus 1-Up Edition",
        group="fooocus",
        name_patterns=("1-up", "fooocus 1-up"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_FOOOCUS_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="simplesdxl",
        display_name="SimpleSDXL",
        group="fooocus",
        name_patterns=("simplesdxl",),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_FOOOCUS_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="fooocus",
        display_name="Fooocus",
        group="fooocus",
        name_patterns=("fooocus",),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_FOOOCUS_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="comfyui",
        display_name="ComfyUI",
        group="node_workflow",
        name_patterns=("comfyui",),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="http_adapter",
        asset_types=_NODE_WORKFLOW_ASSET_TYPES,
        capability_set=_COMFYUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="stableswarmui",
        display_name="StableSwarmUI / SwarmUI",
        group="node_workflow",
        name_patterns=("swarmui", "stableswarm"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="http_adapter",
        asset_types=_NODE_WORKFLOW_ASSET_TYPES,
        capability_set=_STABLESWARMUI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="sdfx",
        display_name="SDFX",
        group="node_workflow",
        name_patterns=("sdfx",),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_NODE_WORKFLOW_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="voltaml",
        display_name="VoltaML",
        group="other_inference",
        name_patterns=("voltaml",),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_CUDA_ONLY_BACKENDS,
        api_strategy="launch_fs",
        asset_types=("checkpoint", "lora", "vae", "image"),
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="invokeai",
        display_name="InvokeAI",
        group="other_inference",
        name_patterns=("invokeai", "invoke-ai", "invoke ai"),
        supported_platforms=("windows", "linux", "macos"),
        acceleration_backends=_ALL_PLATFORM_BACKENDS,
        api_strategy="native_api",
        asset_types=_INVOKEAI_ASSET_TYPES,
        capability_set=_INVOKEAI_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="kohya_gui",
        display_name="Kohya GUI",
        group="training",
        name_patterns=("kohya",),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_CUDA_ONLY_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_TRAINING_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="onetrainer",
        display_name="OneTrainer",
        group="training",
        name_patterns=("onetrainer", "one trainer"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_CUDA_ONLY_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_TRAINING_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="fluxgym",
        display_name="FluxGym",
        group="training",
        name_patterns=("fluxgym", "flux gym"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_CUDA_ONLY_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_TRAINING_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
    ),
    CreativePackageFamily(
        id="cogstudio",
        display_name="CogVideo via CogStudio",
        group="video",
        name_patterns=("cogstudio", "cogvideo"),
        supported_platforms=("windows", "linux"),
        acceleration_backends=_CUDA_ONLY_BACKENDS,
        api_strategy="launch_fs",
        asset_types=_VIDEO_ASSET_TYPES,
        capability_set=_LAUNCH_FS_CAPABILITIES,
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
