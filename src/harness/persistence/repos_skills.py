"""Repositories for skill packages + per-session skill activations (SKL-001)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import Skill, SkillActivation, SkillIndexEntry
from harness.core.errors import ConflictError, NotFoundError
from harness.core.ids import new_id
from harness.persistence.db import Database


class SkillRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, skill: Skill) -> Skill:
        existing = await self._db.fetch_one(
            "SELECT id FROM skills WHERE name = :name", {"name": skill.name}
        )
        if existing is not None:
            raise ConflictError(f"skill name already registered: {skill.name}")
        await self._db.execute(
            "INSERT INTO skills (id, name, description, activation_hints, estimated_tokens, "
            "required_capabilities, scripts, reference_docs, body) VALUES "
            "(:id, :name, :description, :activation_hints, :estimated_tokens, "
            ":required_capabilities, :scripts, :reference_docs, :body)",
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "activation_hints": json.dumps(skill.activation_hints),
                "estimated_tokens": skill.estimated_tokens,
                "required_capabilities": json.dumps(skill.required_capabilities),
                "scripts": json.dumps(skill.scripts),
                "reference_docs": json.dumps(skill.reference_docs),
                "body": skill.body,
            },
        )
        return await self.get(skill.id)

    async def get(self, skill_id: str) -> Skill:
        row = await self._db.fetch_one("SELECT * FROM skills WHERE id = :id", {"id": skill_id})
        if row is None:
            raise NotFoundError(f"skill not found: {skill_id}")
        return _skill(row)

    async def list(self) -> list[SkillIndexEntry]:
        rows = await self._db.fetch_all("SELECT * FROM skills ORDER BY name")
        return [_index_entry(r) for r in rows]

    async def delete(self, skill_id: str) -> None:
        await self.get(skill_id)
        await self._db.execute("DELETE FROM skills WHERE id = :id", {"id": skill_id})


class SkillActivationRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def activate(self, session_id: str, skill_id: str) -> SkillActivation:
        """Idempotent: re-activating an already-activated skill is a no-op, not
        a duplicate row.
        """
        existing = await self._db.fetch_one(
            "SELECT * FROM skill_activations WHERE session_id = :session_id "
            "AND skill_id = :skill_id",
            {"session_id": session_id, "skill_id": skill_id},
        )
        if existing is not None:
            return _activation(existing)

        row_id = new_id("skact")
        await self._db.execute(
            "INSERT INTO skill_activations (id, session_id, skill_id) "
            "VALUES (:id, :session_id, :skill_id)",
            {"id": row_id, "session_id": session_id, "skill_id": skill_id},
        )
        row = await self._db.fetch_one(
            "SELECT * FROM skill_activations WHERE id = :id", {"id": row_id}
        )
        assert row is not None
        return _activation(row)

    async def list_for_session(self, session_id: str) -> list[SkillActivation]:
        rows = await self._db.fetch_all(
            "SELECT * FROM skill_activations WHERE session_id = :session_id ORDER BY created_at",
            {"session_id": session_id},
        )
        return [_activation(r) for r in rows]


def _skill(row: Any) -> Skill:
    return Skill(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        activation_hints=json.loads(row["activation_hints"]),
        estimated_tokens=row["estimated_tokens"],
        required_capabilities=json.loads(row["required_capabilities"]),
        scripts=json.loads(row["scripts"]),
        reference_docs=json.loads(row["reference_docs"]),
        body=row["body"],
        created_at=row["created_at"],
    )


def _index_entry(row: Any) -> SkillIndexEntry:
    return SkillIndexEntry(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        activation_hints=json.loads(row["activation_hints"]),
        estimated_tokens=row["estimated_tokens"],
        required_capabilities=json.loads(row["required_capabilities"]),
    )


def _activation(row: Any) -> SkillActivation:
    return SkillActivation(
        id=row["id"],
        session_id=row["session_id"],
        skill_id=row["skill_id"],
        created_at=row["created_at"],
    )
