"""Repositories for MCP server registration + the compact tool index (MCP-001)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import McpServer, McpToolIndexEntry
from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.persistence.db import Database


class McpServerRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, server: McpServer) -> McpServer:
        await self._db.execute(
            "INSERT INTO mcp_servers (id, display_name, base_url, secret_ref_id, "
            "enabled) VALUES (:id, :display_name, :base_url, :secret_ref_id, :enabled)",
            {
                "id": server.id,
                "display_name": server.display_name,
                "base_url": server.base_url,
                "secret_ref_id": server.secret_ref_id,
                "enabled": int(server.enabled),
            },
        )
        return await self.get(server.id)

    async def get(self, server_id: str) -> McpServer:
        row = await self._db.fetch_one(
            "SELECT * FROM mcp_servers WHERE id = :id", {"id": server_id}
        )
        if row is None:
            raise NotFoundError(f"MCP server not found: {server_id}")
        return _server(row)

    async def list(self) -> list[McpServer]:
        rows = await self._db.fetch_all("SELECT * FROM mcp_servers ORDER BY display_name")
        return [_server(r) for r in rows]

    async def delete(self, server_id: str) -> None:
        await self.get(server_id)
        await self._db.execute("DELETE FROM mcp_servers WHERE id = :id", {"id": server_id})

    async def mark_indexed(self, server_id: str) -> McpServer:
        await self.get(server_id)
        await self._db.execute(
            "UPDATE mcp_servers SET last_indexed_at = datetime('now') WHERE id = :id",
            {"id": server_id},
        )
        return await self.get(server_id)


class McpIndexRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def replace_for_server(
        self,
        server_id: str,
        entries: list[tuple[str, str, int, str, dict[str, Any]]],
    ) -> list[McpToolIndexEntry]:
        """Replace a server's entire tool index in one call — indexing always
        re-discovers the full current tool list, so stale entries from
        since-removed tools must not linger.

        Each entry is (tool_name, description, estimated_schema_tokens,
        trust_class, schema).
        """
        await self._db.execute(
            "DELETE FROM mcp_tool_index WHERE server_id = :id", {"id": server_id}
        )
        created = []
        for tool_name, description, estimated_tokens, trust_class, schema in entries:
            entry_id = new_id("mcpidx")
            await self._db.execute(
                "INSERT INTO mcp_tool_index (id, server_id, tool_name, description, "
                "estimated_schema_tokens, trust_class, schema_json) VALUES "
                "(:id, :server_id, :tool_name, :description, :estimated_schema_tokens, "
                ":trust_class, :schema_json)",
                {
                    "id": entry_id,
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "description": description,
                    "estimated_schema_tokens": estimated_tokens,
                    "trust_class": trust_class,
                    "schema_json": json.dumps(schema),
                },
            )
            created.append(
                McpToolIndexEntry(
                    id=entry_id,
                    server_id=server_id,
                    tool_name=tool_name,
                    description=description,
                    estimated_schema_tokens=estimated_tokens,
                    trust_class=trust_class,  # type: ignore[arg-type]
                )
            )
        return created

    async def list(self, *, server_id: str | None = None) -> list[McpToolIndexEntry]:
        if server_id is not None:
            rows = await self._db.fetch_all(
                "SELECT * FROM mcp_tool_index WHERE server_id = :id ORDER BY tool_name",
                {"id": server_id},
            )
        else:
            rows = await self._db.fetch_all("SELECT * FROM mcp_tool_index ORDER BY tool_name")
        return [_index_entry(r) for r in rows]

    async def get(self, entry_id: str) -> McpToolIndexEntry:
        row = await self._db.fetch_one(
            "SELECT * FROM mcp_tool_index WHERE id = :id", {"id": entry_id}
        )
        if row is None:
            raise NotFoundError(f"MCP tool index entry not found: {entry_id}")
        return _index_entry(row)

    async def get_schema(self, entry_id: str) -> dict[str, Any]:
        row = await self._db.fetch_one(
            "SELECT schema_json FROM mcp_tool_index WHERE id = :id", {"id": entry_id}
        )
        if row is None:
            raise NotFoundError(f"MCP tool index entry not found: {entry_id}")
        return dict(json.loads(row["schema_json"]))


def _server(row: Any) -> McpServer:
    return McpServer(
        id=row["id"],
        display_name=row["display_name"],
        base_url=row["base_url"],
        secret_ref_id=row["secret_ref_id"],
        enabled=bool(row["enabled"]),
        last_indexed_at=row["last_indexed_at"],
        created_at=row["created_at"],
    )


def _index_entry(row: Any) -> McpToolIndexEntry:
    return McpToolIndexEntry(
        id=row["id"],
        server_id=row["server_id"],
        tool_name=row["tool_name"],
        description=row["description"],
        estimated_schema_tokens=row["estimated_schema_tokens"],
        trust_class=row["trust_class"],
    )
