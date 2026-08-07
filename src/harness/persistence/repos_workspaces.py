"""Repository for persisted Workspaces (WSP-001, SPEC/WORKSPACES_ARTIFACTS.md)."""

from __future__ import annotations

from typing import Any

from harness.core.domain import Workspace
from harness.core.errors import NotFoundError
from harness.persistence.db import Database


class WorkspaceRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, workspace: Workspace) -> Workspace:
        await self._db.execute(
            "INSERT INTO workspaces (id, host_id, root_path, display_name) "
            "VALUES (:id, :host_id, :root_path, :display_name)",
            {
                "id": workspace.id,
                "host_id": workspace.host_id,
                "root_path": workspace.root_path,
                "display_name": workspace.display_name,
            },
        )
        return await self.get(workspace.id)

    async def get(self, workspace_id: str) -> Workspace:
        row = await self._db.fetch_one(
            "SELECT * FROM workspaces WHERE id = :id", {"id": workspace_id}
        )
        if row is None:
            raise NotFoundError(f"workspace not found: {workspace_id}")
        return _workspace(row)

    async def delete(self, workspace_id: str) -> None:
        await self.get(workspace_id)
        await self._db.execute("DELETE FROM workspaces WHERE id = :id", {"id": workspace_id})

    async def list(self) -> list[Workspace]:
        rows = await self._db.fetch_all("SELECT * FROM workspaces ORDER BY created_at")
        return [_workspace(r) for r in rows]


def _workspace(row: Any) -> Workspace:
    return Workspace(
        id=row["id"],
        host_id=row["host_id"],
        root_path=row["root_path"],
        display_name=row["display_name"],
        created_at=row["created_at"],
    )
