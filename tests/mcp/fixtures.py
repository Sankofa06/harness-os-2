"""A real local MCP server (Streamable HTTP transport, JSON-RPC 2.0) for testing
`McpClient`/MCP-001 against actual HTTP request/response cycles rather than mocks
(TESTING/TEST_STRATEGY.md). MCP-001's server-registration flow builds its own
httpx client from a persisted `base_url`, so tests need a real bound port to
point it at — unlike the language-provider adapters, which accept an injected
`http_client` and can use `httpx.ASGITransport` in-process.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

FAKE_TOOLS = [
    {
        "name": "search_docs",
        "description": "Search internal documentation.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "create_ticket",
        "description": "Create a support ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title"],
        },
    },
]


def create_fake_mcp_app(*, required_token: str | None = None) -> FastAPI:
    """``required_token``, when set, makes every call fail with a JSON-RPC error
    unless it carries a matching ``Authorization: Bearer`` header — used to prove
    the SEC-001 bearer-token wiring actually sends the resolved secret, not just
    that the client accepts one.
    """
    app = FastAPI()

    @app.post("/mcp")
    async def rpc(request: Request) -> JSONResponse:
        payload = await request.json()
        method = payload.get("method")
        rpc_id = payload.get("id")
        if (
            required_token is not None
            and request.headers.get("authorization") != f"Bearer {required_token}"
        ):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32000, "message": "unauthorized"},
                }
            )
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture-mcp-server", "version": "0.1"},
                # Echoed back so tests can assert a bearer token was actually sent
                # (SEC-001), not just accepted by the client's constructor.
                "receivedAuthorization": request.headers.get("authorization"),
            }
        elif method == "tools/list":
            result = {"tools": FAKE_TOOLS}
        else:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"unknown method: {method}"},
                }
            )
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

    return app


@dataclass
class RunningMcpServer:
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"


async def start_fake_mcp_server(
    *, required_token: str | None = None
) -> tuple[uvicorn.Server, asyncio.Task[None], RunningMcpServer]:
    app = create_fake_mcp_app(required_token=required_token)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn.Server exposes no startup event
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, RunningMcpServer(port=port)


async def stop_fake_mcp_server(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await task
