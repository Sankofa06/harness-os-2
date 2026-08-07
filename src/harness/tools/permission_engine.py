"""Real permission resolution (PERM-001), implementing
`harness.tools.permissions.PermissionResolver`.

Every resolution is logged — automatic allow/deny immediately, an "ask" flow's
final outcome once a human decides (SPEC/SECURITY_PRIVACY.md "resolution is
explicit and logged"). "ask" blocks the caller on an `asyncio.Future` keyed by the
tool run's ID until `decide()` is called by the approval API; since tool execution
already runs inside a `JobManager` background task (D-029), this is an ordinary
async wait, not a request-thread block.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from harness.core.domain import PermissionClass
from harness.core.errors import NotFoundError
from harness.persistence.repos_permissions import PermissionDecisionRepo, PermissionPolicyRepo
from harness.tools.permissions import PermissionDecision


class PermissionEngine:
    def __init__(self, policies: PermissionPolicyRepo, decisions: PermissionDecisionRepo) -> None:
        self._policies = policies
        self._decisions = decisions
        self._pending: dict[str, asyncio.Future[Literal["allow", "deny"]]] = {}

    async def resolve(
        self, permission_class: PermissionClass, *, run_id: str
    ) -> PermissionDecision:
        policy = await self._policies.get_effective(permission_class)
        if policy in ("allow", "deny"):
            await self._decisions.create(
                tool_run_id=run_id,
                permission_class=permission_class,
                policy=policy,
                outcome=policy,
                decided_by=None,
            )
        return policy

    async def await_decision(self, run_id: str) -> Literal["allow", "deny"]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Literal["allow", "deny"]] = loop.create_future()
        self._pending[run_id] = future
        try:
            return await future
        finally:
            self._pending.pop(run_id, None)

    async def decide(
        self,
        run_id: str,
        outcome: Literal["allow", "deny"],
        *,
        permission_class: PermissionClass,
        decided_by: str | None,
    ) -> None:
        """Resolve a pending "ask" for `run_id`. Raises NotFoundError if nothing is
        currently waiting on it (already decided, never asked, or the tool run
        finished/was canceled before a human responded).
        """
        future = self._pending.get(run_id)
        if future is None or future.done():
            raise NotFoundError(f"no pending approval for tool run: {run_id}")
        await self._decisions.create(
            tool_run_id=run_id,
            permission_class=permission_class,
            policy="ask",
            outcome=outcome,
            decided_by=decided_by,
        )
        future.set_result(outcome)

    def pending_run_ids(self) -> list[str]:
        return sorted(run_id for run_id, future in self._pending.items() if not future.done())
