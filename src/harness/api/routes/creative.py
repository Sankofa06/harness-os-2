"""Stability Matrix installation discovery + engine capability model
endpoints (CRE-001/CRE-002, SPEC/CREATIVE_COMPUTE.md, SPEC/API_CONTRACT.md).

Discovery reads `<data_dir>/settings.json` from a registered SSH Host via
the same `SSHHost.read_file`/workspace-root containment HOST-002 already
established (`data_dir` must fall under that host's configured
`workspace_roots`) — there is no local/"node"-kind adapter yet, so scanning
is SSH-only today; that's a real, declared limitation, not a placeholder.

The `/creative/engines*` routes serve `harness.providers.creative.families`'s
declarative catalog directly — there is no live engine communication here
(that starts with CRE-003's ComfyUI adapter), so every engine's
`implemented` field is `false`: the capability model describes what SPEC
documents an engine as *capable of*, never what Harness can currently do.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import CreativeInstallation
from harness.core.errors import NotFoundError
from harness.core.settings_schema import SettingsSchema
from harness.hosts.resolve import build_ssh_host
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
