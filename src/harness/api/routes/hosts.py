"""Host registry endpoints (CP-004, SPEC/API_CONTRACT.md, SPEC/HOSTS_AND_NODE.md).

`/hosts/{id}/test` and `/hosts/{id}/health` require live connectivity (SSH/Node) and
are added with HOST-001; this module covers the persisted capability model only.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import Host, HostKind
from harness.core.ids import new_id

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
