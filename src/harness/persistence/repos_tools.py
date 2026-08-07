"""Repository for persisted ToolRun lifecycle records (TOOL-001)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import ToolRun, ToolRunStatus
from harness.core.errors import NotFoundError
from harness.persistence.db import Database


class ToolRunRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, run: ToolRun) -> ToolRun:
        await self._db.execute(
            "INSERT INTO tool_runs (id, tool_name, arguments_json, permission_class, "
            "status, workspace_id, session_id) VALUES (:id, :tool_name, "
            ":arguments_json, :permission_class, :status, :workspace_id, :session_id)",
            {
                "id": run.id,
                "tool_name": run.tool_name,
                "arguments_json": json.dumps(run.arguments),
                "permission_class": run.permission_class,
                "status": run.status,
                "workspace_id": run.workspace_id,
                "session_id": run.session_id,
            },
        )
        return await self.get(run.id)

    async def get(self, run_id: str) -> ToolRun:
        row = await self._db.fetch_one("SELECT * FROM tool_runs WHERE id = :id", {"id": run_id})
        if row is None:
            raise NotFoundError(f"tool run not found: {run_id}")
        return _tool_run(row)

    async def list(
        self, *, tool_name: str | None = None, session_id: str | None = None
    ) -> list[ToolRun]:
        clauses = []
        params: dict[str, Any] = {}
        if tool_name is not None:
            clauses.append("tool_name = :tool_name")
            params["tool_name"] = tool_name
        if session_id is not None:
            clauses.append("session_id = :session_id")
            params["session_id"] = session_id
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await self._db.fetch_all(
            f"SELECT * FROM tool_runs{where} ORDER BY created_at DESC, rowid DESC", params
        )
        return [_tool_run(r) for r in rows]

    async def set_status(
        self,
        run_id: str,
        status: ToolRunStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ToolRun:
        await self.get(run_id)
        updates = ["status = :status"]
        params: dict[str, Any] = {"status": status, "id": run_id}
        if status in ("succeeded", "failed", "denied"):
            updates.append("finished_at = datetime('now')")
        if result is not None:
            updates.append("result_json = :result")
            params["result"] = json.dumps(result)
        if error is not None:
            updates.append("error = :error")
            params["error"] = error
        await self._db.execute(f"UPDATE tool_runs SET {', '.join(updates)} WHERE id = :id", params)
        return await self.get(run_id)


def _tool_run(row: Any) -> ToolRun:
    return ToolRun(
        id=row["id"],
        tool_name=row["tool_name"],
        arguments=json.loads(row["arguments_json"]),
        permission_class=row["permission_class"],
        status=row["status"],
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error"],
        workspace_id=row["workspace_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )
