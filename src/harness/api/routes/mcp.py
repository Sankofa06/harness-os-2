"""MCP server registry + lazy tool index endpoints (MCP-001,
SPEC/MCP_SKILLS_TOOLS.md).

`GET /mcp/tools/index` never returns a tool's full JSON Schema — only what's
needed to decide whether to activate it (name, one-line description, estimated
schema token cost, trust class). The full schema is fetched separately via
`GET /mcp/tools/{entry_id}/schema`, kept as its own endpoint so nothing accidental
pulls every registered MCP tool's schema into a response by default.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import McpServer, McpToolIndexEntry
from harness.core.ids import new_id
from harness.mcp.indexing import index_server

router = APIRouter(dependencies=[Depends(require_auth)], tags=["mcp"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class McpServerCreate(BaseModel):
    display_name: str
    base_url: str
    secret_ref_id: str | None = None


@router.post("/mcp/servers", status_code=201)
async def create_mcp_server(request: Request, body: McpServerCreate) -> McpServer:
    app = _app(request)
    server = McpServer(
        id=new_id("mcpsrv"),
        display_name=body.display_name,
        base_url=body.base_url,
        secret_ref_id=body.secret_ref_id,
    )
    return await app.mcp_servers.create(server)


@router.get("/mcp/servers")
async def list_mcp_servers(request: Request) -> list[McpServer]:
    return await _app(request).mcp_servers.list()


@router.get("/mcp/servers/{server_id}")
async def get_mcp_server(request: Request, server_id: str) -> McpServer:
    return await _app(request).mcp_servers.get(server_id)


@router.delete("/mcp/servers/{server_id}", status_code=204)
async def delete_mcp_server(request: Request, server_id: str) -> None:
    await _app(request).mcp_servers.delete(server_id)


@router.post("/mcp/servers/{server_id}/index")
async def reindex_mcp_server(request: Request, server_id: str) -> list[McpToolIndexEntry]:
    """Connect to the server (`initialize` + `tools/list`) and replace its tool
    index — names/descriptions/estimated costs only, never the full schemas
    (DoD "Schema loads only when activated").
    """
    app = _app(request)
    server = await app.mcp_servers.get(server_id)
    return await index_server(
        server, app.mcp_servers, app.mcp_index, app.secret_refs, app.secret_store
    )


@router.get("/mcp/tools/index")
async def get_mcp_tool_index(
    request: Request, server_id: str | None = Query(default=None)
) -> list[McpToolIndexEntry]:
    return await _app(request).mcp_index.list(server_id=server_id)


@router.get("/mcp/tools/{entry_id}/schema")
async def get_mcp_tool_schema(request: Request, entry_id: str) -> dict[str, Any]:
    return await _app(request).mcp_index.get_schema(entry_id)
