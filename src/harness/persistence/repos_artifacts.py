"""Repository for persisted Artifact metadata (ART-001)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import Artifact
from harness.core.errors import NotFoundError
from harness.persistence.db import Database


class ArtifactRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, artifact: Artifact) -> Artifact:
        await self._db.execute(
            "INSERT INTO artifacts (id, type, mime_type, display_name, size, "
            "sha256, run_id, session_id, workspace_id, source_path, metadata_json) "
            "VALUES (:id, :type, :mime_type, :display_name, :size, :sha256, "
            ":run_id, :session_id, :workspace_id, :source_path, :metadata_json)",
            {
                "id": artifact.id,
                "type": artifact.type,
                "mime_type": artifact.mime_type,
                "display_name": artifact.display_name,
                "size": artifact.size,
                "sha256": artifact.sha256,
                "run_id": artifact.run_id,
                "session_id": artifact.session_id,
                "workspace_id": artifact.workspace_id,
                "source_path": artifact.source_path,
                "metadata_json": json.dumps(artifact.metadata),
            },
        )
        return await self.get(artifact.id)

    async def get(self, artifact_id: str) -> Artifact:
        row = await self._db.fetch_one(
            "SELECT * FROM artifacts WHERE id = :id", {"id": artifact_id}
        )
        if row is None:
            raise NotFoundError(f"artifact not found: {artifact_id}")
        return _artifact(row)

    async def delete(self, artifact_id: str) -> None:
        await self.get(artifact_id)
        await self._db.execute("DELETE FROM artifacts WHERE id = :id", {"id": artifact_id})

    async def list(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[Artifact]:
        clauses = []
        params: dict[str, Any] = {}
        if run_id is not None:
            clauses.append("run_id = :run_id")
            params["run_id"] = run_id
        if session_id is not None:
            clauses.append("session_id = :session_id")
            params["session_id"] = session_id
        if artifact_type is not None:
            clauses.append("type = :type")
            params["type"] = artifact_type
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await self._db.fetch_all(
            f"SELECT * FROM artifacts{where} ORDER BY created_at DESC", params
        )
        return [_artifact(r) for r in rows]


def _artifact(row: Any) -> Artifact:
    return Artifact(
        id=row["id"],
        type=row["type"],
        mime_type=row["mime_type"],
        display_name=row["display_name"],
        size=row["size"],
        sha256=row["sha256"],
        run_id=row["run_id"],
        session_id=row["session_id"],
        workspace_id=row["workspace_id"],
        source_path=row["source_path"],
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
    )
