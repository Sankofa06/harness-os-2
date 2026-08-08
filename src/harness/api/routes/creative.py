"""Stability Matrix installation discovery + engine capability model +
ComfyUI generation endpoints (CRE-001/CRE-002/CRE-003,
SPEC/CREATIVE_COMPUTE.md, SPEC/API_CONTRACT.md).

Discovery reads `<data_dir>/settings.json` from a registered SSH Host via
the same `SSHHost.read_file`/workspace-root containment HOST-002 already
established (`data_dir` must fall under that host's configured
`workspace_roots`) — there is no local/"node"-kind adapter yet, so scanning
is SSH-only today; that's a real, declared limitation, not a placeholder.

The `/creative/engines*` routes serve `harness.providers.creative.families`'s
declarative catalog directly — every engine's `implemented` field reflects
whether a live adapter actually exists (only ComfyUI's does, as of CRE-003).

`/creative/workflows` stores a workflow graph as an Artifact (ART-001) —
referenced by id, never inlined into any LLM-facing context.
`POST /creative/jobs` runs one generation as a Job (JOB-001); only
`engine_id="comfyui"` is accepted, since that's the only engine with a real
adapter — accepting any other id here would itself be a fake control.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.domain import Artifact, CreativeInstallation
from harness.core.errors import NotFoundError, ValidationFailedError
from harness.core.settings_schema import SettingsSchema
from harness.hosts.resolve import build_ssh_host
from harness.jobs.manager import JobHandle
from harness.jobs.model import Job
from harness.providers.creative.comfyui.adapter import run_comfyui_generation
from harness.providers.creative.discovery import parse_installed_packages
from harness.providers.creative.families import FAMILIES, FAMILIES_BY_ID

router = APIRouter(dependencies=[Depends(require_auth)], tags=["creative"])


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
    """No engine has a live adapter yet (CRE-003 onward), so there are no
    engine-specific settings fields to validate — only the one thing every
    Stability-Matrix-managed package genuinely supports today (CRE-001:
    each install already carries its own launch command/args).
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
    engine_id: Literal["comfyui"]
    base_url: str
    workflow: dict[str, Any] | None = None
    workflow_artifact_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None


@router.post("/creative/jobs", status_code=202)
async def submit_creative_job(request: Request, body: CreativeJobRequest) -> Job:
    """Only `engine_id="comfyui"` is accepted — the `Literal` type itself
    enforces that (FastAPI 422s any other value), so this endpoint can never
    accept a request for an engine with no real adapter.
    """
    app = _app(request)
    if body.workflow is not None:
        graph = body.workflow
    elif body.workflow_artifact_id is not None:
        artifact = await app.artifacts.get(body.workflow_artifact_id)  # 404s if unknown
        graph = json.loads(app.artifact_blobs.get(artifact.sha256))
    else:
        raise ValidationFailedError("either workflow or workflow_artifact_id is required")

    async def work(handle: JobHandle) -> dict[str, Any]:
        return await run_comfyui_generation(
            app,
            handle,
            base_url=body.base_url,
            workflow=graph,
            session_id=body.session_id,
            workspace_id=body.workspace_id,
        )

    return await app.job_manager.submit("creative.comfyui.generate", work)


@router.get("/creative/jobs")
async def list_creative_jobs(request: Request) -> list[Job]:
    return await _app(request).jobs.list(job_type="creative.comfyui.generate")
