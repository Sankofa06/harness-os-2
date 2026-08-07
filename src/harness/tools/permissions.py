"""Permission resolution hook for the tool lifecycle (TOOL-001, referenced by
PERM-001).

`AllowAllResolver` is a deliberately narrow placeholder — not a fake permission
system, just an explicit stand-in whose only behavior is "always allow" — so the
lifecycle in `harness.tools.lifecycle` has a real interface to call today. PERM-001
replaces it with a resolver that checks a persisted class x policy table
(allow/ask/deny) and blocks on an approval API for "ask"; the lifecycle's control
flow (deny -> denied, ask -> pending_approval, allow -> execute) already handles
all three outcomes, so that swap requires no lifecycle changes.
"""

from __future__ import annotations

from typing import Literal, Protocol

PermissionDecision = Literal["allow", "ask", "deny"]


class PermissionResolver(Protocol):
    async def resolve(self, permission_class: str) -> PermissionDecision: ...


class AllowAllResolver:
    async def resolve(self, permission_class: str) -> PermissionDecision:
        return "allow"
