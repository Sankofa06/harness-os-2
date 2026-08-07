"""Repositories for permission policy overrides and the decision audit log
(PERM-001, SPEC/SECURITY_PRIVACY.md)."""

from __future__ import annotations

from typing import Any

from harness.core.domain import (
    PermissionClass,
    PermissionDecisionLog,
    PermissionOutcome,
    PermissionPolicy,
    PermissionPolicyRecord,
)
from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.core.permissions import ALL_PERMISSION_CLASSES, DEFAULT_POLICIES
from harness.persistence.db import Database


class PermissionPolicyRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_effective(self, permission_class: PermissionClass) -> PermissionPolicy:
        row = await self._db.fetch_one(
            "SELECT policy FROM permission_policies WHERE permission_class = :c",
            {"c": permission_class},
        )
        return row["policy"] if row is not None else DEFAULT_POLICIES[permission_class]

    async def set(
        self, permission_class: PermissionClass, policy: PermissionPolicy
    ) -> PermissionPolicyRecord:
        await self._db.execute(
            "INSERT INTO permission_policies (permission_class, policy) VALUES (:c, :p) "
            "ON CONFLICT (permission_class) DO UPDATE SET policy = :p, "
            "updated_at = datetime('now')",
            {"c": permission_class, "p": policy},
        )
        return PermissionPolicyRecord(permission_class=permission_class, policy=policy)

    async def list_effective(self) -> list[PermissionPolicyRecord]:
        overrides = {
            r["permission_class"]: r["policy"]
            for r in await self._db.fetch_all(
                "SELECT permission_class, policy FROM permission_policies"
            )
        }
        return [
            PermissionPolicyRecord(permission_class=c, policy=overrides.get(c, DEFAULT_POLICIES[c]))
            for c in ALL_PERMISSION_CLASSES
        ]


class PermissionDecisionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        tool_run_id: str,
        permission_class: PermissionClass,
        policy: PermissionPolicy,
        outcome: PermissionOutcome,
        decided_by: str | None,
    ) -> PermissionDecisionLog:
        decision_id = new_id("perm")
        await self._db.execute(
            "INSERT INTO permission_decisions (id, tool_run_id, permission_class, "
            "policy, outcome, decided_by) VALUES (:id, :tool_run_id, "
            ":permission_class, :policy, :outcome, :decided_by)",
            {
                "id": decision_id,
                "tool_run_id": tool_run_id,
                "permission_class": permission_class,
                "policy": policy,
                "outcome": outcome,
                "decided_by": decided_by,
            },
        )
        return await self.get(decision_id)

    async def get(self, decision_id: str) -> PermissionDecisionLog:
        row = await self._db.fetch_one(
            "SELECT * FROM permission_decisions WHERE id = :id", {"id": decision_id}
        )
        if row is None:
            raise NotFoundError(f"permission decision not found: {decision_id}")
        return _decision(row)

    async def list(self, *, tool_run_id: str | None = None) -> list[PermissionDecisionLog]:
        if tool_run_id is not None:
            rows = await self._db.fetch_all(
                "SELECT * FROM permission_decisions WHERE tool_run_id = :t "
                "ORDER BY created_at DESC",
                {"t": tool_run_id},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM permission_decisions ORDER BY created_at DESC"
            )
        return [_decision(r) for r in rows]


def _decision(row: Any) -> PermissionDecisionLog:
    return PermissionDecisionLog(
        id=row["id"],
        tool_run_id=row["tool_run_id"],
        permission_class=row["permission_class"],
        policy=row["policy"],
        outcome=row["outcome"],
        decided_by=row["decided_by"],
        created_at=row["created_at"],
    )
