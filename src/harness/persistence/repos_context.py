"""Repository for persisted TranscriptState (CTX-003)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import TranscriptState
from harness.persistence.db import Database


class TranscriptStateRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, session_id: str) -> TranscriptState:
        """Returns an empty (all-default) TranscriptState if none has been set yet
        — there is nothing to protect until a caller records something.
        """
        row = await self._db.fetch_one(
            "SELECT * FROM session_transcript_state WHERE session_id = :id",
            {"id": session_id},
        )
        if row is None:
            return TranscriptState(session_id=session_id)
        return _transcript_state(row)

    async def update(
        self,
        session_id: str,
        *,
        unresolved_requirements: list[str] | None = None,
        current_plan: str | None = None,
        changed_files: list[str] | None = None,
        failing_tests: list[str] | None = None,
        permission_decisions: list[str] | None = None,
        rolling_summary: str | None = None,
    ) -> TranscriptState:
        """Upsert; only the fields explicitly passed (non-None) are changed."""
        current = await self.get(session_id)
        merged = current.model_copy(
            update={
                k: v
                for k, v in {
                    "unresolved_requirements": unresolved_requirements,
                    "current_plan": current_plan,
                    "changed_files": changed_files,
                    "failing_tests": failing_tests,
                    "permission_decisions": permission_decisions,
                    "rolling_summary": rolling_summary,
                }.items()
                if v is not None
            }
        )
        await self._db.execute(
            "INSERT INTO session_transcript_state (session_id, "
            "unresolved_requirements_json, current_plan, changed_files_json, "
            "failing_tests_json, permission_decisions_json, rolling_summary, "
            "updated_at) VALUES (:session_id, :unresolved_requirements_json, "
            ":current_plan, :changed_files_json, :failing_tests_json, "
            ":permission_decisions_json, :rolling_summary, datetime('now')) "
            "ON CONFLICT (session_id) DO UPDATE SET "
            "unresolved_requirements_json = :unresolved_requirements_json, "
            "current_plan = :current_plan, "
            "changed_files_json = :changed_files_json, "
            "failing_tests_json = :failing_tests_json, "
            "permission_decisions_json = :permission_decisions_json, "
            "rolling_summary = :rolling_summary, "
            "updated_at = datetime('now')",
            {
                "session_id": session_id,
                "unresolved_requirements_json": json.dumps(merged.unresolved_requirements),
                "current_plan": merged.current_plan,
                "changed_files_json": json.dumps(merged.changed_files),
                "failing_tests_json": json.dumps(merged.failing_tests),
                "permission_decisions_json": json.dumps(merged.permission_decisions),
                "rolling_summary": merged.rolling_summary,
            },
        )
        return await self.get(session_id)


def _transcript_state(row: Any) -> TranscriptState:
    return TranscriptState(
        session_id=row["session_id"],
        unresolved_requirements=json.loads(row["unresolved_requirements_json"]),
        current_plan=row["current_plan"],
        changed_files=json.loads(row["changed_files_json"]),
        failing_tests=json.loads(row["failing_tests_json"]),
        permission_decisions=json.loads(row["permission_decisions_json"]),
        rolling_summary=row["rolling_summary"],
        updated_at=row["updated_at"],
    )
