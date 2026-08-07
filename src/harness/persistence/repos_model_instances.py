"""Repository for persisted model-load lifecycle records (LP-009)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import InstanceStatus, ModelInstanceRecord
from harness.core.errors import NotFoundError
from harness.persistence.db import Database


class ModelInstanceRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, instance: ModelInstanceRecord) -> ModelInstanceRecord:
        await self._db.execute(
            "INSERT INTO model_instances (id, provider_config_id, model_id, "
            "native_instance_id, status, settings_json) VALUES (:id, "
            ":provider_config_id, :model_id, :native_instance_id, :status, "
            ":settings_json)",
            {
                "id": instance.id,
                "provider_config_id": instance.provider_config_id,
                "model_id": instance.model_id,
                "native_instance_id": instance.native_instance_id,
                "status": instance.status,
                "settings_json": json.dumps(instance.settings),
            },
        )
        return instance

    async def get(self, instance_id: str) -> ModelInstanceRecord:
        row = await self._db.fetch_one(
            "SELECT * FROM model_instances WHERE id = :id", {"id": instance_id}
        )
        if row is None:
            raise NotFoundError(f"model instance not found: {instance_id}")
        return _instance(row)

    async def list(self) -> list[ModelInstanceRecord]:
        rows = await self._db.fetch_all("SELECT * FROM model_instances ORDER BY created_at DESC")
        return [_instance(r) for r in rows]

    async def set_status(
        self,
        instance_id: str,
        status: InstanceStatus,
        *,
        native_instance_id: str | None = None,
        error: str | None = None,
    ) -> None:
        updates = ["status = :status", "updated_at = datetime('now')"]
        params: dict[str, Any] = {"status": status, "id": instance_id}
        if native_instance_id is not None:
            updates.append("native_instance_id = :native")
            params["native"] = native_instance_id
        if error is not None:
            updates.append("error = :error")
            params["error"] = error
        await self._db.execute(
            f"UPDATE model_instances SET {', '.join(updates)} WHERE id = :id",
            params,
        )

    async def set_settings(self, instance_id: str, settings: dict[str, Any]) -> ModelInstanceRecord:
        await self.get(instance_id)
        await self._db.execute(
            "UPDATE model_instances SET settings_json = :s, updated_at = datetime('now') "
            "WHERE id = :id",
            {"s": json.dumps(settings), "id": instance_id},
        )
        return await self.get(instance_id)

    async def delete(self, instance_id: str) -> None:
        await self.get(instance_id)
        await self._db.execute("DELETE FROM model_instances WHERE id = :id", {"id": instance_id})


def _instance(row: Any) -> ModelInstanceRecord:
    return ModelInstanceRecord(
        id=row["id"],
        provider_config_id=row["provider_config_id"],
        model_id=row["model_id"],
        native_instance_id=row["native_instance_id"],
        status=row["status"],
        settings=json.loads(row["settings_json"]),
        error=row["error"],
    )
