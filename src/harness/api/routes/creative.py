"""Stability Matrix installation discovery + engine capability model +
ComfyUI/A1111/launch_fs generation endpoints + creative asset catalog +
creative profiles (CRE-001 through CRE-007, SPEC/CREATIVE_COMPUTE.md,
SPEC/API_CONTRACT.md).

Discovery reads `<data_dir>/settings.json` from a registered SSH Host via
the same `SSHHost.read_file`/workspace-root containment HOST-002 already
established (`data_dir` must fall under that host's configured
`workspace_roots`) — there is no local/"node"-kind adapter yet, so scanning
is SSH-only today; that's a real, declared limitation, not a placeholder.

The `/creative/engines*` routes serve `harness.providers.creative.families`'s
declarative catalog directly — every engine's `implemented` field reflects
whether a live adapter actually exists (ComfyUI since CRE-003; the
AUTOMATIC1111-compatible family since CRE-004; everything else — Fooocus and
its variants, StableSwarmUI, SDFX, VoltaML, InvokeAI, the training engines,
CogStudio — at the lighter launch_fs/native-detection level since CRE-005).

`/creative/workflows` stores a workflow graph as an Artifact (ART-001) —
referenced by id, never inlined into any LLM-facing context.
`POST /creative/jobs` runs one generation as a Job (JOB-001); only engines
with a real adapter are accepted — accepting any other id here would itself
be a fake control. ComfyUI's job is workflow-graph-based (`workflow`/
`workflow_artifact_id`); the A1111-compatible family's is a direct
txt2img/img2img call (`operation`/`params`) — the two protocols are
genuinely different shapes, not forced into one.

`POST /creative/health-check` and `POST /creative/invokeai/detect` are the
generic launch_fs reachability check and InvokeAI's specific native-API
detection, respectively; `creative.launch_engine`/`creative.launch_training`
(registered as native Tools, not REST routes here — see
`harness.providers.creative.launch_fs`) launch an already-discovered
installation's own recorded command over SSH.

`POST /creative/assets/scan` walks a host's shared Stability Matrix
``Models`` directory (CRE-006, `harness.providers.creative.assets`),
hashing each recognized model file remotely and deduping by content hash
so the same checkpoint found at multiple paths/hosts is cataloged once
with multiple locations.

`POST /creative/profiles` stores a Creative Profile (CRE-007) -- a reusable
preset, explicitly not a Persona. Passing ``profile_id`` on `POST
/creative/jobs` drives that generation from it: for ComfyUI, the profile's
``workflow_artifact_id`` is used when the request itself doesn't specify a
workflow; for the AUTOMATIC1111-compatible family, `_merge_a1111_profile_
params` applies the profile's checkpoint/VAE/sampler/scheduler/LoRAs as
real txt2img/img2img request fields (verified from A1111 source, not
guessed), with any field the request sets explicitly taking precedence.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.domain import Artifact, CreativeAsset, CreativeInstallation, CreativeProfile
from harness.core.errors import NotFoundError, ValidationFailedError
from harness.core.ids import new_id
from harness.core.settings_schema import SettingsSchema
from harness.hosts.resolve import build_ssh_host
from harness.jobs.manager import JobHandle
from harness.jobs.model import Job
from harness.providers.creative.a1111.adapter import run_a1111_generation
from harness.providers.creative.assets import scan_models_directory
from harness.providers.creative.comfyui.adapter import run_comfyui_generation
from harness.providers.creative.discovery import parse_installed_packages
from harness.providers.creative.families import FAMILIES, FAMILIES_BY_ID
from harness.providers.creative.invokeai.detect import detect_invokeai
from harness.providers.creative.launch_fs import check_reachable

router = APIRouter(dependencies=[Depends(require_auth)], tags=["creative"])

_A1111_COMPATIBLE_ENGINE_IDS = frozenset(
    {
        "automatic1111",
        "sdwebui_forge",
        "sdwebui_reforge",
        "sdwebui_amdgpu_forge",
        "sdwebui_ux",
        "sdnext",
        "automatic1111_directml",
    }
)


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class InstallationScanRequest(BaseModel):
    host_id: str
    data_dir: str
    platform: Literal["windows", "macos", "linux"]


@router.post("/creative/installations/scan")
async def scan_installations(
    request: Request, body: InstallationScanRequest
) -> list[CreativeInstallation]:
    app = _app(request)
    host = await app.hosts.get(body.host_id)  # 404s if unknown
    ssh_host = await build_ssh_host(host, app.secret_refs, app.secret_store)
    settings_path = body.data_dir.rstrip("/") + "/settings.json"
    raw = await ssh_host.read_file(settings_path)
    installations = parse_installed_packages(raw.decode("utf-8"), body.platform)
    return await app.creative_installations.replace_for_scan(
        body.host_id, body.data_dir, body.platform, installations
    )


@router.get("/creative/installations")
async def list_installations(
    request: Request, host_id: str | None = Query(default=None)
) -> list[CreativeInstallation]:
    return await _app(request).creative_installations.list(host_id=host_id)


class CreativeEngineInfo(BaseModel):
    id: str
    display_name: str
    group: str
    supported_platforms: list[str]
    acceleration_backends: list[str]
    api_strategy: str
    launch_strategy: str
    asset_types: list[str]
    capability_set: list[str]
    implemented: bool


def _engine_info(family_id: str) -> CreativeEngineInfo:
    family = FAMILIES_BY_ID.get(family_id)
    if family is None:
        raise NotFoundError(f"creative engine not found: {family_id}")
    return CreativeEngineInfo(
        id=family.id,
        display_name=family.display_name,
        group=family.group,
        supported_platforms=list(family.supported_platforms),
        acceleration_backends=list(family.acceleration_backends),
        api_strategy=family.api_strategy,
        launch_strategy=family.launch_strategy,
        asset_types=list(family.asset_types),
        capability_set=list(family.capability_set),
        implemented=family.implemented,
    )


@router.get("/creative/engines")
async def list_engines(request: Request) -> list[CreativeEngineInfo]:
    return [_engine_info(f.id) for f in FAMILIES]


@router.get("/creative/engines/{engine_id}")
async def get_engine(request: Request, engine_id: str) -> CreativeEngineInfo:
    return _engine_info(engine_id)


class CreativeEngineCapabilities(BaseModel):
    id: str
    api_strategy: str
    acceleration_backends: list[str]
    asset_types: list[str]
    capability_set: list[str]
    implemented: bool


@router.get("/creative/engines/{engine_id}/capabilities")
async def get_engine_capabilities(request: Request, engine_id: str) -> CreativeEngineCapabilities:
    info = _engine_info(engine_id)
    return CreativeEngineCapabilities(
        id=info.id,
        api_strategy=info.api_strategy,
        acceleration_backends=info.acceleration_backends,
        asset_types=info.asset_types,
        capability_set=info.capability_set,
        implemented=info.implemented,
    )


@router.get("/creative/engines/{engine_id}/settings-schema")
async def get_engine_settings_schema(request: Request, engine_id: str) -> dict[str, Any]:
    """No engine has settings-schema-validated per-request fields yet — only
    the one thing every Stability-Matrix-managed package genuinely supports
    today (CRE-001: each install already carries its own launch command/
    args). ComfyUI/A1111 generation requests pass their own request bodies
    directly (`workflow`/`operation`+`params`), validated by their own
    Pydantic models rather than this namespaced schema.
    """
    _engine_info(engine_id)  # 404s for an unknown engine id
    schema = SettingsSchema(
        common={
            "type": "object",
            "properties": {
                "extra_launch_args": {"type": "array", "items": {"type": "string"}},
            },
        }
    )
    return schema.to_dict()


class WorkflowCreate(BaseModel):
    engine_id: str
    display_name: str
    graph: dict[str, Any]
    session_id: str | None = None
    workspace_id: str | None = None


@router.post("/creative/workflows", status_code=201)
async def create_workflow(request: Request, body: WorkflowCreate) -> Artifact:
    if body.engine_id not in FAMILIES_BY_ID:
        raise ValidationFailedError(f"unknown engine id: {body.engine_id}")
    return await store_and_record_artifact(
        _app(request),
        type="workflow",
        display_name=body.display_name,
        content=json.dumps(body.graph).encode("utf-8"),
        mime_type="application/json",
        session_id=body.session_id,
        workspace_id=body.workspace_id,
        metadata={"engine_id": body.engine_id},
    )


@router.get("/creative/workflows")
async def list_workflows(request: Request) -> list[Artifact]:
    return await _app(request).artifacts.list(artifact_type="workflow")


class CreativeJobRequest(BaseModel):
    engine_id: Literal[
        "comfyui",
        "automatic1111",
        "sdwebui_forge",
        "sdwebui_reforge",
        "sdwebui_amdgpu_forge",
        "sdwebui_ux",
        "sdnext",
        "automatic1111_directml",
    ]
    base_url: str
    # ComfyUI (workflow-graph based):
    workflow: dict[str, Any] | None = None
    workflow_artifact_id: str | None = None
    # AUTOMATIC1111-compatible (direct txt2img/img2img call):
    operation: Literal["txt2img", "img2img"] | None = None
    params: dict[str, Any] | None = None
    # CRE-007: a Creative Profile preset to drive this generation from. Its
    # engine_selector must match engine_id; explicit fields above always
    # win over the profile's own defaults.
    profile_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None


def _merge_a1111_profile_params(profile: CreativeProfile, params: dict[str, Any]) -> dict[str, Any]:
    """Applies a Checkpoint Profile bundle (checkpoint/vae/sampler/
    scheduler/loras) as real AUTOMATIC1111 txt2img/img2img request fields,
    verified directly from `modules/processing.py`/`extra_networks_lora.py`
    source: checkpoint/VAE go in `override_settings` (A1111 itself restores
    the prior values after the request), sampler/scheduler are top-level
    fields, and LoRAs have no structured field at all in this API -- they
    are applied by appending `<lora:name:1.0>` tokens to the prompt string,
    the built-in Lora extension's only mechanism. Explicit request
    ``params`` always win over the profile's own defaults.
    """
    override_settings: dict[str, Any] = {}
    if profile.checkpoint is not None:
        override_settings["sd_model_checkpoint"] = profile.checkpoint
    if profile.vae is not None:
        override_settings["sd_vae"] = profile.vae

    merged: dict[str, Any] = {}
    if override_settings:
        merged["override_settings"] = override_settings
    if profile.sampler is not None:
        merged["sampler_name"] = profile.sampler
    if profile.scheduler is not None:
        merged["scheduler"] = profile.scheduler

    for key, value in params.items():
        if key == "override_settings" and isinstance(value, dict) and merged.get(key):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    if profile.loras:
        lora_tags = "".join(f"<lora:{name}:1.0>" for name in profile.loras)
        merged["prompt"] = merged.get("prompt", "") + lora_tags

    return merged


@router.post("/creative/jobs", status_code=202)
async def submit_creative_job(request: Request, body: CreativeJobRequest) -> Job:
    """Only engines with a real adapter are accepted — the `Literal` type
    itself enforces that (FastAPI 422s any other value), so this endpoint
    can never accept a request for an engine with no real adapter.
    """
    app = _app(request)

    profile: CreativeProfile | None = None
    if body.profile_id is not None:
        profile = await app.creative_profiles.get(body.profile_id)  # 404s if unknown
        if profile.engine_selector != body.engine_id:
            raise ValidationFailedError(
                f"profile {profile.name!r} targets engine "
                f"{profile.engine_selector!r}, not {body.engine_id!r}"
            )

    if body.engine_id == "comfyui":
        if body.workflow is not None:
            graph = body.workflow
        elif body.workflow_artifact_id is not None:
            artifact = await app.artifacts.get(body.workflow_artifact_id)  # 404s if unknown
            graph = json.loads(app.artifact_blobs.get(artifact.sha256))
        elif profile is not None and profile.workflow_artifact_id is not None:
            artifact = await app.artifacts.get(profile.workflow_artifact_id)
            graph = json.loads(app.artifact_blobs.get(artifact.sha256))
        else:
            raise ValidationFailedError("either workflow or workflow_artifact_id is required")

        async def comfyui_work(handle: JobHandle) -> dict[str, Any]:
            return await run_comfyui_generation(
                app,
                handle,
                base_url=body.base_url,
                workflow=graph,
                session_id=body.session_id,
                workspace_id=body.workspace_id,
            )

        return await app.job_manager.submit("creative.comfyui.generate", comfyui_work)

    assert body.engine_id in _A1111_COMPATIBLE_ENGINE_IDS  # the only other Literal values
    if body.operation is None:
        raise ValidationFailedError("operation is required for an AUTOMATIC1111-compatible engine")
    if body.params is None and profile is None:
        raise ValidationFailedError(
            "params is required for an AUTOMATIC1111-compatible engine without a profile"
        )
    engine_id = body.engine_id
    operation = body.operation
    params = (
        _merge_a1111_profile_params(profile, body.params or {}) if profile else (body.params or {})
    )

    async def a1111_work(handle: JobHandle) -> dict[str, Any]:
        return await run_a1111_generation(
            app,
            handle,
            base_url=body.base_url,
            engine_id=engine_id,
            operation=operation,
            params=params,
            session_id=body.session_id,
            workspace_id=body.workspace_id,
        )

    return await app.job_manager.submit("creative.a1111.generate", a1111_work)


@router.get("/creative/jobs")
async def list_creative_jobs(request: Request) -> list[Job]:
    jobs = await _app(request).jobs.list()
    return [j for j in jobs if j.type.startswith("creative.")]


class HealthCheckRequest(BaseModel):
    base_url: str


class HealthCheckResult(BaseModel):
    reachable: bool


@router.post("/creative/health-check")
async def health_check(request: Request, body: HealthCheckRequest) -> HealthCheckResult:
    """The generic launch_fs-tier "health" check (CRE-005) — a plain HTTP
    reachability probe, since most families here have no documented API to
    check anything more specific.
    """
    return HealthCheckResult(reachable=await check_reachable(body.base_url))


class InvokeAIDetectRequest(BaseModel):
    base_url: str


class InvokeAIDetectResult(BaseModel):
    detected: bool
    version: str | None = None


@router.post("/creative/invokeai/detect")
async def invokeai_detect(request: Request, body: InvokeAIDetectRequest) -> InvokeAIDetectResult:
    """InvokeAI's own native-API detection (CRE-005) — distinct from the
    generic health check above, this confirms the server actually answers
    InvokeAI's real `/api/v1/app/version` endpoint, not just that something
    is listening (SPEC: "Use its native API if detected").
    """
    version = await detect_invokeai(body.base_url)
    return InvokeAIDetectResult(detected=version is not None, version=version)


class AssetLocationInfo(BaseModel):
    host_id: str
    path: str


class CreativeAssetWithLocations(CreativeAsset):
    locations: list[AssetLocationInfo] = Field(default_factory=list)


class AssetScanRequest(BaseModel):
    host_id: str
    models_root: str


@router.post("/creative/assets/scan")
async def scan_assets(request: Request, body: AssetScanRequest) -> list[CreativeAssetWithLocations]:
    """Scan ``models_root`` (the host's Stability Matrix shared ``Models``
    directory — not derived automatically from a `data_dir`, since Harness
    does not read Stability Matrix's own ``ModelDirectoryOverride`` setting;
    callers supply the real path rather than Harness guessing the
    un-overridden default) and record every recognized model file found
    (CRE-006).
    """
    app = _app(request)
    host = await app.hosts.get(body.host_id)  # 404s if unknown
    ssh_host = await build_ssh_host(host, app.secret_refs, app.secret_store)
    scanned = await scan_models_directory(ssh_host, body.models_root)
    assets = await app.creative_assets.record_scan(body.host_id, scanned)
    return [await _asset_with_locations(app, asset.id) for asset in assets]


@router.get("/creative/assets")
async def list_assets(
    request: Request, asset_kind: str | None = Query(default=None)
) -> list[CreativeAssetWithLocations]:
    app = _app(request)
    assets = await app.creative_assets.list(asset_kind=asset_kind)
    return [await _asset_with_locations(app, asset.id) for asset in assets]


async def _asset_with_locations(app: Application, asset_id: str) -> CreativeAssetWithLocations:
    asset = await app.creative_assets.get(asset_id)
    locations = await app.creative_assets.list_locations(asset_id)
    return CreativeAssetWithLocations(
        **asset.model_dump(),
        locations=[AssetLocationInfo(host_id=loc.host_id, path=loc.path) for loc in locations],
    )


class CreativeProfileCreate(BaseModel):
    name: str
    engine_selector: str
    workflow_artifact_id: str | None = None
    checkpoint: str | None = None
    vae: str | None = None
    loras: list[str] = Field(default_factory=list)
    sampler: str | None = None
    scheduler: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    prefer_loaded_asset: bool = False


_VALID_ENGINE_SELECTORS = frozenset({"comfyui"}) | _A1111_COMPATIBLE_ENGINE_IDS


@router.post("/creative/profiles", status_code=201)
async def create_profile(request: Request, body: CreativeProfileCreate) -> CreativeProfile:
    if body.engine_selector not in _VALID_ENGINE_SELECTORS:
        raise ValidationFailedError(f"unknown engine_selector: {body.engine_selector}")
    app = _app(request)
    if body.workflow_artifact_id is not None:
        await app.artifacts.get(body.workflow_artifact_id)  # 404s if unknown
    profile = CreativeProfile(id=new_id("prof"), **body.model_dump())
    return await app.creative_profiles.create(profile)


@router.get("/creative/profiles")
async def list_profiles(request: Request) -> list[CreativeProfile]:
    return await _app(request).creative_profiles.list()


@router.get("/creative/profiles/{profile_id}")
async def get_profile(request: Request, profile_id: str) -> CreativeProfile:
    return await _app(request).creative_profiles.get(profile_id)
