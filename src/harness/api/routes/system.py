"""System endpoints: /health, /system/info, /capabilities (SPEC/API_CONTRACT.md)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from harness import __version__
from harness.core.app import Application
from harness.core.control_plane import ControlPlaneDescriptor

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/info")
async def system_info(request: Request) -> dict[str, Any]:
    app: Application = request.app.state.harness
    return {
        "version": __version__,
        "demo_mode": app.config.ui.demo_mode,
        "context_budget": app.config.context.model_dump(),
    }


@router.get("/capabilities")
async def capabilities(request: Request) -> dict[str, list[ControlPlaneDescriptor]]:
    """Uniform control-plane descriptors for every registered subsystem resource."""
    app: Application = request.app.state.harness
    return {
        "language_providers": [p.describe() for p in app.providers.list()],
    }
