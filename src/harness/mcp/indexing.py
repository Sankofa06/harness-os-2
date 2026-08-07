"""Connects to an MCP server and (re)builds its compact tool index (MCP-001).

Every discovered tool defaults to the `network` trust/permission class — the MCP
protocol carries no danger-level metadata, and *any* call to an external MCP
server is, at minimum, outbound network I/O to a third party, so `network` is the
conservative, honest default (PERM-001's `DEFAULT_POLICIES["network"]` is `ask`).

When a server has a `secret_ref_id`, it's resolved to a bearer token just-in-time
(SEC-001), the same pattern as `harness.hosts.resolve.build_ssh_host` — the token
is never persisted or logged, only sent on the outbound request.
"""

from __future__ import annotations

from harness.context.tokens import HeuristicEstimator
from harness.core.domain import McpServer, McpToolIndexEntry
from harness.core.secrets import SecretStore
from harness.mcp.client import McpClient
from harness.persistence.repos import SecretRefRepo
from harness.persistence.repos_mcp import McpIndexRepo, McpServerRepo

_estimator = HeuristicEstimator()
_DEFAULT_TRUST_CLASS = "network"


async def index_server(
    server: McpServer,
    servers: McpServerRepo,
    index: McpIndexRepo,
    secret_refs: SecretRefRepo,
    secret_store: SecretStore,
) -> list[McpToolIndexEntry]:
    auth_token: str | None = None
    if server.secret_ref_id:
        secret_ref = await secret_refs.get(server.secret_ref_id)
        auth_token = secret_store.get(secret_ref.kind, secret_ref.target)

    client = McpClient(server.base_url, auth_token=auth_token)
    try:
        await client.initialize()
        tools = await client.list_tools()
    finally:
        await client.aclose()

    entries = []
    for tool in tools:
        schema = tool.get("inputSchema", {})
        entries.append(
            (
                tool["name"],
                tool.get("description", ""),
                _estimator.estimate(str(schema)),
                _DEFAULT_TRUST_CLASS,
                schema,
            )
        )

    created = await index.replace_for_server(server.id, entries)
    await servers.mark_indexed(server.id)
    return created
