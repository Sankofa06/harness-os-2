"""Skill package registry + activation endpoints (SKL-001,
SPEC/CONTEXT_COMPILER.md "Skill format", SPEC/API_CONTRACT.md).

`GET /skills` never returns a skill's body (the expensive SKILL.md content) —
only what's needed to decide whether to activate it (name, one-line
description, activation hints, estimated token cost, required capabilities).
The body is fetched, and the skill activated for the calling session, only via
`POST /skills/{id}/activate` — matching MCP-001/MCP-002's "index cheap, body/
schema lazy" split.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.context.tokens import HeuristicEstimator
from harness.core.app import Application
from harness.core.domain import Skill, SkillIndexEntry
from harness.core.ids import new_id
from harness.skills.activation import activate_skill

router = APIRouter(dependencies=[Depends(require_auth)], tags=["skills"])
_estimator = HeuristicEstimator()


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    activation_hints: list[str] = Field(default_factory=list)
    estimated_tokens: int | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    reference_docs: list[str] = Field(default_factory=list)
    body: str = ""


@router.post("/skills", status_code=201)
async def create_skill(request: Request, body: SkillCreate) -> Skill:
    app = _app(request)
    estimated_tokens = body.estimated_tokens
    if estimated_tokens is None:
        estimated_tokens = _estimator.estimate(body.body)
    skill = Skill(
        id=new_id("skill"),
        name=body.name,
        description=body.description,
        activation_hints=body.activation_hints,
        estimated_tokens=estimated_tokens,
        required_capabilities=body.required_capabilities,
        scripts=body.scripts,
        reference_docs=body.reference_docs,
        body=body.body,
    )
    return await app.skills.create(skill)


@router.get("/skills")
async def list_skills(request: Request) -> list[SkillIndexEntry]:
    return await _app(request).skills.list()


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(request: Request, skill_id: str) -> None:
    await _app(request).skills.delete(skill_id)


class SkillActivateRequest(BaseModel):
    session_id: str


class SkillActivateResponse(BaseModel):
    name: str
    description: str
    body: str


@router.post("/skills/{skill_id}/activate")
async def activate_skill_route(
    request: Request, skill_id: str, body: SkillActivateRequest
) -> SkillActivateResponse:
    app = _app(request)
    skill = await activate_skill(body.session_id, skill_id, app.skills, app.skill_activations)
    return SkillActivateResponse(name=skill.name, description=skill.description, body=skill.body)
