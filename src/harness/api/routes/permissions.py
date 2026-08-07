"""Permission policy + approval endpoints (PERM-001, SPEC/SECURITY_PRIVACY.md).

Policies are class x allow/ask/deny, resolved by `PermissionEngine` inside the tool
lifecycle (TOOL-001). This router exposes the operator-facing surface: view/edit
policies, see the decision audit log, and approve/reject a run currently blocked on
an "ask" policy.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import (
    PermissionClass,
    PermissionDecisionLog,
    PermissionPolicy,
    PermissionPolicyRecord,
)

router = APIRouter(dependencies=[Depends(require_auth)], tags=["permissions"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


@router.get("/permissions/policies")
async def list_policies(request: Request) -> list[PermissionPolicyRecord]:
    return await _app(request).permission_policies.list_effective()


class PolicyUpdate(BaseModel):
    policy: PermissionPolicy


@router.put("/permissions/policies/{permission_class}")
async def set_policy(
    request: Request, permission_class: PermissionClass, body: PolicyUpdate
) -> PermissionPolicyRecord:
    return await _app(request).permission_policies.set(permission_class, body.policy)


@router.get("/permissions/decisions")
async def list_decisions(
    request: Request, tool_run_id: str | None = Query(default=None)
) -> list[PermissionDecisionLog]:
    return await _app(request).permission_decisions.list(tool_run_id=tool_run_id)


@router.get("/permissions/pending")
async def list_pending(request: Request) -> list[str]:
    """Tool run IDs currently blocked on an "ask" policy, awaiting a decision."""
    return _app(request).permission_engine.pending_run_ids()


class DecisionRequest(BaseModel):
    decided_by: str | None = None


@router.post("/permissions/decisions/{run_id}/approve")
async def approve(request: Request, run_id: str, body: DecisionRequest) -> None:
    app = _app(request)
    run = await app.tool_runs.get(run_id)
    await app.permission_engine.decide(
        run_id, "allow", permission_class=run.permission_class, decided_by=body.decided_by
    )


@router.post("/permissions/decisions/{run_id}/reject")
async def reject(request: Request, run_id: str, body: DecisionRequest) -> None:
    app = _app(request)
    run = await app.tool_runs.get(run_id)
    await app.permission_engine.decide(
        run_id, "deny", permission_class=run.permission_class, decided_by=body.decided_by
    )
