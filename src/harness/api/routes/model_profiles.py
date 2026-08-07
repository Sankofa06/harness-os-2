"""Model profile endpoints (LP-008, SPEC/PROVIDER_MATRIX.md "Model profile")."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import LoadPolicy, ModelProfile, PlacementPolicy, ToolCapabilityPolicy
from harness.core.ids import new_id

router = APIRouter(dependencies=[Depends(require_auth)], tags=["language"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class ModelProfileCreate(BaseModel):
    name: str
    provider_config_id: str
    model_id: str
    settings: dict[str, Any] = Field(default_factory=dict)
    load_policy: LoadPolicy = "on_demand"
    placement_policy: PlacementPolicy = "manual"
    tool_capability_policy: ToolCapabilityPolicy = "inherit"


@router.get("/language/profiles")
async def list_profiles(request: Request) -> list[ModelProfile]:
    return await _app(request).model_profiles.list()


@router.post("/language/profiles", status_code=201)
async def create_profile(request: Request, body: ModelProfileCreate) -> ModelProfile:
    app = _app(request)
    await app.provider_configs.get(body.provider_config_id)  # 404s if unknown
    profile = ModelProfile(id=new_id("prof"), **body.model_dump())
    return await app.model_profiles.create(profile)


@router.get("/language/profiles/{profile_id}")
async def get_profile(request: Request, profile_id: str) -> ModelProfile:
    return await _app(request).model_profiles.get(profile_id)


@router.delete("/language/profiles/{profile_id}", status_code=204)
async def delete_profile(request: Request, profile_id: str) -> None:
    await _app(request).model_profiles.delete(profile_id)
