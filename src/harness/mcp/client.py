"""Minimal MCP (Model Context Protocol) client — Streamable HTTP transport only
(MCP-001, SPEC/MCP_SKILLS_TOOLS.md).

Hand-rolled against httpx (JSON-RPC 2.0 over a single POST endpoint), matching
every other provider/engine adapter in this codebase rather than adding the `mcp`
SDK as the sole vendor-SDK dependency among otherwise-uniform httpx adapters.
Implements exactly the two calls MCP-001 needs: `initialize` and `tools/list`.

stdio transport (the other transport in the MCP spec, for locally-launched
servers communicating over stdin/stdout) is not implemented — declared honestly
as unsupported rather than faked, matching this codebase's capability-declaration
rule (ADR 0003).
"""

from __future__ import annotations

from typing import Any

import httpx

from harness.core.errors import ProviderError

PROTOCOL_VERSION = "2024-11-05"


class McpClient:
    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._auth_token = auth_token
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        headers = {"Accept": "application/json, text/event-stream"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        try:
            resp = await self._client.post(
                self._base_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"MCP request to {self._base_url} failed ({method}): {exc}"
            ) from exc
        data = resp.json()
        if "error" in data:
            error = data["error"]
            raise ProviderError(f"MCP server error ({method}): {error.get('message', error)}")
        return dict(data.get("result", {}))

    async def initialize(self) -> dict[str, Any]:
        return await self._call(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "harness-os", "version": "0.1"},
            },
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._call("tools/list")
        tools = result.get("tools", [])
        return list(tools)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
