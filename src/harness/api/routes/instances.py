"""Model discovery + instance lifecycle endpoints (LP-009, SPEC/API_CONTRACT.md).

Long-running operations (load/unload) run as Jobs (SPEC/API_CONTRACT.md "long actions
create Jobs") rather than blocking the request.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import ModelInstanceRecord
from harness.core.errors import ProviderError
from harness.core.ids import new_id
from harness.core.settings_schema import validate_settings
from harness.events.model import Event, EventResource
from harness.jobs.manager import JobHandle
from harness.jobs.model import Job
from harness.providers.language.base import ModelInfo

router = APIRouter(dependencies=[Depends(require_auth)], tags=["language"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


@router.get("/language/models")
async def list_models(
    request: Request, provider_config_id: str | None = Query(default=None)
) -> list[ModelInfo]:
    """Aggregate model discovery across enabled providers (or one, if specified).

    A single provider failing does not fail the whole request (SPEC/ARCHITECTURE.md
    failure-isolation rule) — its models are simply omitted.
    """
    app = _app(request)
    configs = (
        [await app.provider_configs.get(provider_config_id)]
        if provider_config_id
        else [c for c in await app.provider_configs.list() if c.enabled]
    )
    models: list[ModelInfo] = []
    for config in configs:
        try:
            provider = await app.get_or_build_provider(config.id)
            models.extend(await provider.list_models())
        except ProviderError:
            continue
    return models


@router.get("/language/instances")
async def list_instances(request: Request) -> list[ModelInstanceRecord]:
    return await _app(request).model_instances.list()


@router.get("/language/instances/{instance_id}")
async def get_instance(request: Request, instance_id: str) -> ModelInstanceRecord:
    return await _app(request).model_instances.get(instance_id)


class LoadRequest(BaseModel):
    provider_config_id: str
    model_id: str
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/language/instances/load", status_code=202)
async def load_instance(request: Request, body: LoadRequest) -> Job:
    app = _app(request)
    await app.provider_configs.get(body.provider_config_id)  # 404s if unknown
    instance = await app.model_instances.create(
        ModelInstanceRecord(
            id=new_id("inst"),
            provider_config_id=body.provider_config_id,
            model_id=body.model_id,
            status="loading",
        )
    )
    resource = EventResource(type="model_instance", id=instance.id)
    await app.publish(
        Event(
            type="model.load.requested",
            resource=resource,
            payload={"provider_config_id": body.provider_config_id, "model_id": body.model_id},
        )
    )

    async def work(handle: JobHandle) -> dict[str, Any]:
        provider = await app.get_or_build_provider(body.provider_config_id)
        result = await provider.load_model(body.model_id, **body.options)
        await app.model_instances.set_status(
            instance.id, "loaded", native_instance_id=result.instance_id
        )
        await app.publish(
            Event(
                type="model.loaded",
                resource=resource,
                payload={"model_id": body.model_id, "native_instance_id": result.instance_id},
            )
        )
        return {"instance_id": instance.id, "native_instance_id": result.instance_id}

    return await app.job_manager.submit(
        "language.instance.load",
        work,
        detail={"instance_id": instance.id, "model_id": body.model_id},
    )


@router.post("/language/instances/{instance_id}/unload", status_code=202)
async def unload_instance(request: Request, instance_id: str) -> Job:
    app = _app(request)
    record = await app.model_instances.get(instance_id)

    async def work(handle: JobHandle) -> None:
        provider = await app.get_or_build_provider(record.provider_config_id)
        await provider.unload_model(record.native_instance_id or record.model_id)
        await app.model_instances.set_status(instance_id, "unloaded")
        await app.publish(
            Event(
                type="model.unloaded",
                resource=EventResource(type="model_instance", id=instance_id),
                payload={"model_id": record.model_id},
            )
        )

    return await app.job_manager.submit(
        "language.instance.unload", work, detail={"instance_id": instance_id}
    )


@router.get("/language/instances/{instance_id}/settings-schema")
async def get_instance_settings_schema(request: Request, instance_id: str) -> dict[str, Any]:
    app = _app(request)
    record = await app.model_instances.get(instance_id)
    provider = await app.get_or_build_provider(record.provider_config_id)
    return provider.settings_schema().to_dict()


class SettingsUpdate(BaseModel):
    settings: dict[str, Any]


@router.patch("/language/instances/{instance_id}/settings")
async def update_instance_settings(
    request: Request, instance_id: str, body: SettingsUpdate
) -> ModelInstanceRecord:
    app = _app(request)
    record = await app.model_instances.get(instance_id)
    provider = await app.get_or_build_provider(record.provider_config_id)
    validate_settings(provider.settings_schema(), body.settings)
    return await app.model_instances.set_settings(instance_id, body.settings)
