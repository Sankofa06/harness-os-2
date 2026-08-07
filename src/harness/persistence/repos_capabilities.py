"""Repository for per-session activated capabilities (MCP-002)."""

from __future__ import annotations

from typing import Any

from harness.core.domain import CapabilityKind, SessionActivatedCapability
from harness.core.ids import new_id
from harness.persistence.db import Database


class SessionCapabilityRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def activate(
        self, session_id: str, kind: CapabilityKind, ref: str
    ) -> SessionActivatedCapability:
        """Idempotent: activating an already-activated capability is a no-op,
        not a duplicate row (`tools.describe` may be called on the same tool
        more than once in a session).
        """
        existing = await self._db.fetch_one(
            "SELECT * FROM session_activated_capabilities WHERE session_id = :session_id "
            "AND kind = :kind AND ref = :ref",
            {"session_id": session_id, "kind": kind, "ref": ref},
        )
        if existing is not None:
            return _capability(existing)

        row_id = new_id("actcap")
        await self._db.execute(
            "INSERT INTO session_activated_capabilities (id, session_id, kind, ref) "
            "VALUES (:id, :session_id, :kind, :ref)",
            {"id": row_id, "session_id": session_id, "kind": kind, "ref": ref},
        )
        row = await self._db.fetch_one(
            "SELECT * FROM session_activated_capabilities WHERE id = :id", {"id": row_id}
        )
        assert row is not None
        return _capability(row)

    async def list_for_session(self, session_id: str) -> list[SessionActivatedCapability]:
        rows = await self._db.fetch_all(
            "SELECT * FROM session_activated_capabilities WHERE session_id = :session_id "
            "ORDER BY created_at",
            {"session_id": session_id},
        )
        return [_capability(r) for r in rows]


def _capability(row: Any) -> SessionActivatedCapability:
    return SessionActivatedCapability(
        id=row["id"],
        session_id=row["session_id"],
        kind=row["kind"],
        ref=row["ref"],
        created_at=row["created_at"],
    )
