"""Language-provider configuration endpoints (CP-003, SPEC/API_CONTRACT.md)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import ProviderConfig
from harness.core.ids import new_id

router = APIRouter(dependencies=[Depends(require_auth)], tags=["providers"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class ProviderConfigCreate(BaseModel):
    type: str
    display_name: str
    base_url: str | None = None
    secret_ref_id: str | None = None
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


@router.get("/language/providers")
async def list_providers(request: Request) -> list[ProviderConfig]:
    return await _app(request).provider_configs.list()


@router.post("/language/providers", status_code=201)
async def create_provider(request: Request, body: ProviderConfigCreate) -> ProviderConfig:
    config = ProviderConfig(id=new_id("prov"), **body.model_dump())
    return await _app(request).provider_configs.create(config)


@router.get("/language/providers/{provider_id}")
async def get_provider(request: Request, provider_id: str) -> ProviderConfig:
    return await _app(request).provider_configs.get(provider_id)


@router.delete("/language/providers/{provider_id}", status_code=204)
async def delete_provider(request: Request, provider_id: str) -> None:
    await _app(request).provider_configs.delete(provider_id)
