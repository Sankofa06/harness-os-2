"""Host registry endpoints (CP-004, SPEC/API_CONTRACT.md, SPEC/HOSTS_AND_NODE.md).

`/hosts/{id}/health` requires ongoing telemetry (Node/ANA-002) and isn't implemented
yet; `/hosts/{id}/test` (HOST-001) performs a real SSH connectivity + host-key check.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import Host, HostKind
from harness.core.errors import PermissionDeniedError, ProviderError, ValidationFailedError
from harness.core.ids import new_id
from harness.hosts.resolve import build_ssh_host

router = APIRouter(dependencies=[Depends(require_auth)], tags=["hosts"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class HostCreate(BaseModel):
    display_name: str
    kind: HostKind
    hostname: str | None = None
    port: int | None = None
    username: str | None = None
    secret_ref_id: str | None = None
    workspace_roots: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class HostCapabilitiesUpdate(BaseModel):
    capabilities: list[str]


@router.get("/hosts")
async def list_hosts(request: Request) -> list[Host]:
    return await _app(request).hosts.list()


@router.post("/hosts", status_code=201)
async def create_host(request: Request, body: HostCreate) -> Host:
    host = Host(id=new_id("host"), **body.model_dump())
    return await _app(request).hosts.create(host)


@router.get("/hosts/{host_id}")
async def get_host(request: Request, host_id: str) -> Host:
    return await _app(request).hosts.get(host_id)


class HostTestResult(BaseModel):
    ok: bool
    fingerprint: str | None = None
    pinned_fingerprint: str | None = None
    fingerprint_matches_pinned: bool | None = None
    error: str | None = None


@router.post("/hosts/{host_id}/test")
async def test_host(request: Request, host_id: str) -> HostTestResult:
    app = _app(request)
    host = await app.hosts.get(host_id)
    try:
        ssh_host = await build_ssh_host(host, app.secret_refs, app.secret_store)
    except ValidationFailedError as exc:
        return HostTestResult(ok=False, error=str(exc))
    try:
        fingerprint = await ssh_host.test_connection()
    except (ProviderError, PermissionDeniedError) as exc:
        return HostTestResult(ok=False, error=str(exc))
    return HostTestResult(
        ok=True,
        fingerprint=fingerprint,
        pinned_fingerprint=host.known_host_fingerprint,
        fingerprint_matches_pinned=(
            fingerprint == host.known_host_fingerprint if host.known_host_fingerprint else None
        ),
    )


@router.get("/hosts/{host_id}/capabilities")
async def get_host_capabilities(request: Request, host_id: str) -> list[str]:
    host = await _app(request).hosts.get(host_id)
    return host.capabilities


@router.put("/hosts/{host_id}/capabilities")
async def set_host_capabilities(
    request: Request, host_id: str, body: HostCapabilitiesUpdate
) -> Host:
    return await _app(request).hosts.set_capabilities(host_id, body.capabilities)


@router.delete("/hosts/{host_id}", status_code=204)
async def delete_host(request: Request, host_id: str) -> None:
    await _app(request).hosts.delete(host_id)
