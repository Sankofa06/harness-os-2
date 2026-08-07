"""Superpower bundle toggle endpoints (SKL-002, SPEC/MCP_SKILLS_TOOLS.md
"Superpower bundles"). Bundle membership (`GET /superpowers`'s `tool_names`/
`skill_names`) is fixed declarative data (`harness.skills.superpowers`); only
each bundle's on/off state is persisted. Toggling never touches PERM-001's
permission policies — it only changes what `capabilities.search` surfaces
("permissions stay explicit").
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.errors import NotFoundError
from harness.skills.superpowers import BUNDLES, BUNDLES_BY_ID

router = APIRouter(dependencies=[Depends(require_auth)], tags=["skills"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class SuperpowerBundleInfo(BaseModel):
    id: str
    display_name: str
    description: str
    tool_names: list[str]
    skill_names: list[str]
    enabled: bool


@router.get("/superpowers")
async def list_superpowers(request: Request) -> list[SuperpowerBundleInfo]:
    enabled = await _app(request).superpowers.enabled_ids()
    return [
        SuperpowerBundleInfo(
            id=b.id,
            display_name=b.display_name,
            description=b.description,
            tool_names=list(b.tool_names),
            skill_names=list(b.skill_names),
            enabled=b.id in enabled,
        )
        for b in BUNDLES
    ]


class SuperpowerToggleRequest(BaseModel):
    enabled: bool


@router.put("/superpowers/{bundle_id}")
async def set_superpower(
    request: Request, bundle_id: str, body: SuperpowerToggleRequest
) -> SuperpowerBundleInfo:
    if bundle_id not in BUNDLES_BY_ID:
        raise NotFoundError(f"superpower bundle not found: {bundle_id}")
    app = _app(request)
    await app.superpowers.set_enabled(bundle_id, body.enabled)
    bundle = BUNDLES_BY_ID[bundle_id]
    return SuperpowerBundleInfo(
        id=bundle.id,
        display_name=bundle.display_name,
        description=bundle.description,
        tool_names=list(bundle.tool_names),
        skill_names=list(bundle.skill_names),
        enabled=body.enabled,
    )
