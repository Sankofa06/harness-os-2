"""Repository for superpower bundle toggle state (SKL-002).

Bundle membership itself is fixed declarative data (`harness.skills.
superpowers.BUNDLES`); this repo only persists which bundle ids are
currently toggled on. Absence of a row means disabled — the default.
"""

from __future__ import annotations

from harness.persistence.db import Database


class SuperpowerRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def enabled_ids(self) -> set[str]:
        rows = await self._db.fetch_all(
            "SELECT bundle_id FROM superpower_toggles WHERE enabled = 1"
        )
        return {r["bundle_id"] for r in rows}

    async def is_enabled(self, bundle_id: str) -> bool:
        row = await self._db.fetch_one(
            "SELECT enabled FROM superpower_toggles WHERE bundle_id = :id", {"id": bundle_id}
        )
        return bool(row is not None and row["enabled"])

    async def set_enabled(self, bundle_id: str, enabled: bool) -> None:
        existing = await self._db.fetch_one(
            "SELECT bundle_id FROM superpower_toggles WHERE bundle_id = :id", {"id": bundle_id}
        )
        if existing is None:
            await self._db.execute(
                "INSERT INTO superpower_toggles (bundle_id, enabled) VALUES (:id, :enabled)",
                {"id": bundle_id, "enabled": int(enabled)},
            )
        else:
            await self._db.execute(
                "UPDATE superpower_toggles SET enabled = :enabled, "
                "updated_at = datetime('now') WHERE bundle_id = :id",
                {"id": bundle_id, "enabled": int(enabled)},
            )
