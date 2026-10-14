"""Repository for creative generation presets (CRE-007)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import CreativeProfile
from harness.core.errors import ConflictError, NotFoundError
from harness.persistence.db import Database


class CreativeProfileRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, profile: CreativeProfile) -> CreativeProfile:
        if await self._db.fetch_one(
            "SELECT id FROM creative_profiles WHERE name = :name", {"name": profile.name}
        ):
            raise ConflictError(f"creative profile name already exists: {profile.name}")
        await self._db.execute(
            "INSERT INTO creative_profiles (id, name, engine_selector, workflow_artifact_id, "
            "checkpoint, vae, loras, sampler, scheduler, settings, prefer_loaded_asset) "
            "VALUES (:id, :name, :engine_selector, :workflow_artifact_id, :checkpoint, :vae, "
            ":loras, :sampler, :scheduler, :settings, :prefer_loaded_asset)",
            {
                "id": profile.id,
                "name": profile.name,
                "engine_selector": profile.engine_selector,
                "workflow_artifact_id": profile.workflow_artifact_id,
                "checkpoint": profile.checkpoint,
                "vae": profile.vae,
                "loras": json.dumps(profile.loras),
                "sampler": profile.sampler,
                "scheduler": profile.scheduler,
                "settings": json.dumps(profile.settings),
                "prefer_loaded_asset": int(profile.prefer_loaded_asset),
            },
        )
        return await self.get(profile.id)

    async def get(self, profile_id: str) -> CreativeProfile:
        row = await self._db.fetch_one(
            "SELECT * FROM creative_profiles WHERE id = :id", {"id": profile_id}
        )
        if row is None:
            raise NotFoundError(f"creative profile not found: {profile_id}")
        return _profile(row)

    async def list(self) -> list[CreativeProfile]:
        rows = await self._db.fetch_all("SELECT * FROM creative_profiles ORDER BY name, id")
        return [_profile(r) for r in rows]


def _profile(row: Any) -> CreativeProfile:
    return CreativeProfile(
        id=row["id"],
        name=row["name"],
        engine_selector=row["engine_selector"],
        workflow_artifact_id=row["workflow_artifact_id"],
        checkpoint=row["checkpoint"],
        vae=row["vae"],
        loras=json.loads(row["loras"]),
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        settings=json.loads(row["settings"]),
        prefer_loaded_asset=bool(row["prefer_loaded_asset"]),
        created_at=row["created_at"],
    )
