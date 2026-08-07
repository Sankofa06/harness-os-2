"""Permission resolution hook for the tool lifecycle (TOOL-001, implemented by
PERM-001's `harness.tools.permission_engine.PermissionEngine`).

`resolve()` returns a policy-driven decision; when it returns `"ask"`,
`ToolExecutor` calls `await_decision()` next and blocks until a human resolves it
(PERM-001's engine does this with an `asyncio.Future` per pending tool run, backed
by the approval API). `AllowAllResolver` is a deliberately narrow placeholder —
not a fake permission system, just an explicit stand-in whose `resolve()` always
returns `"allow"` — so callers that want to bypass permissioning entirely (tests,
or a future trusted-caller path) have a real, honest implementation to use instead
of `None`-checks scattered through the lifecycle. Its `await_decision()` is never
reachable through normal use, since its `resolve()` never returns `"ask"`.
"""

from __future__ import annotations

from typing import Literal, Protocol

from harness.core.domain import PermissionClass

PermissionDecision = Literal["allow", "ask", "deny"]


class PermissionResolver(Protocol):
    async def resolve(
        self, permission_class: PermissionClass, *, run_id: str
    ) -> PermissionDecision: ...

    async def await_decision(self, run_id: str) -> Literal["allow", "deny"]: ...


class AllowAllResolver:
    async def resolve(
        self, permission_class: PermissionClass, *, run_id: str
    ) -> PermissionDecision:
        return "allow"

    async def await_decision(self, run_id: str) -> Literal["allow", "deny"]:
        raise NotImplementedError("AllowAllResolver.resolve() never returns 'ask'")
