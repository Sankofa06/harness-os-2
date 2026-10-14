"""Submit txt2img/img2img -> poll progress -> capture output, run as a Job
(JOB-001) (CRE-004, SPEC/CREATIVE_COMPUTE.md A1111-compatible section).

Unlike ComfyUI's push-based WebSocket progress, A1111's `/sdapi/v1/progress`
is poll-only (verified via source) — there is no event to await, so progress
is reported by polling concurrently with the generation call, not by
simulating a push mechanism the protocol doesn't have. Canceling the
Harness Job (JOB-001's cooperative `asyncio.Task.cancel()`) also calls the
engine's own `/sdapi/v1/interrupt` before re-raising, so stopping the job
actually stops the remote generation too, not just Harness's wait on it.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
from typing import Any, Literal

from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.errors import UnsupportedCapabilityError
from harness.events.model import Event, EventResource
from harness.jobs.manager import JobHandle
from harness.providers.creative.a1111.client import A1111Client

_POLL_INTERVAL_SECONDS = 0.5


async def _poll_progress(
    app: Application, client: A1111Client, handle: JobHandle, resource: EventResource
) -> None:
    try:
        while True:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            status = await client.progress(skip_current_image=True)
            await handle.set_progress(float(status.get("progress", 0.0)))
            await app.publish(
                Event(
                    type="creative.a1111.progress",
                    resource=resource,
                    context={"job_id": handle.job_id},
                    payload=status,
                )
            )
    except asyncio.CancelledError:
        pass


async def run_a1111_generation(
    app: Application,
    handle: JobHandle,
    *,
    base_url: str,
    engine_id: str,
    operation: Literal["txt2img", "img2img"],
    params: dict[str, Any],
    session_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    client = A1111Client(base_url)
    try:
        capabilities = await client.discover_capabilities()
        if operation not in capabilities:
            raise UnsupportedCapabilityError(
                f"{engine_id} at {base_url} does not support {operation}"
            )

        resource = EventResource(type="job", id=handle.job_id)
        poll_task: asyncio.Task[None] | None = None
        if "progress" in capabilities:
            poll_task = asyncio.create_task(_poll_progress(app, client, handle, resource))

        try:
            call = client.txt2img if operation == "txt2img" else client.img2img
            try:
                result = await call(**params)
            except asyncio.CancelledError:
                if "interrupt" in capabilities:
                    with contextlib.suppress(Exception):
                        await client.interrupt()
                raise
        finally:
            if poll_task is not None:
                poll_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await poll_task

        await app.publish(
            Event(
                type="creative.a1111.generated",
                resource=resource,
                context={"job_id": handle.job_id},
                payload={"operation": operation, "image_count": len(result.get("images", []))},
            )
        )

        output_artifact_ids: list[str] = []
        for index, b64_image in enumerate(result.get("images", [])):
            content = base64.b64decode(b64_image)
            artifact = await store_and_record_artifact(
                app,
                type="image",
                display_name=f"{engine_id}-{operation}-{index}.png",
                content=content,
                mime_type="image/png",
                session_id=session_id,
                workspace_id=workspace_id,
                metadata={
                    "engine_id": engine_id,
                    "base_url": base_url,
                    "operation": operation,
                    "info": result.get("info", ""),
                },
            )
            output_artifact_ids.append(artifact.id)

        return {"operation": operation, "output_artifact_ids": output_artifact_ids}
    finally:
        await client.aclose()
