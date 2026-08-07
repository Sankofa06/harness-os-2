"""Stability Matrix installation discovery endpoints (CRE-001,
SPEC/CREATIVE_COMPUTE.md, SPEC/API_CONTRACT.md).

Discovery reads `<data_dir>/settings.json` from a registered SSH Host via
the same `SSHHost.read_file`/workspace-root containment HOST-002 already
established (`data_dir` must fall under that host's configured
`workspace_roots`) — there is no local/"node"-kind adapter yet, so scanning
is SSH-only today; that's a real, declared limitation, not a placeholder.
"""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import CreativeInstallation
from harness.hosts.resolve import build_ssh_host
from harness.providers.creative.discovery import parse_installed_packages

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
