"""Submit txt2img/img2img -> poll progress -> capture output, run as a Job
(JOB-001) (CRE-004, SPEC/CREATIVE_COMPUTE.md A1111-compatible section).

Unlike ComfyUI's push-based WebSocket progress, A1111's `/sdapi/v1/progress`
is poll-only (verified via source) — there is no event to await, so progress
is reported by polling concurrently with the generation call, not by
simulating a push mechanism the protocol doesn't have. Canceling the
Harness Job (JOB-001's cooperative `asyncio.Task.cancel()`) also calls the
engine's own `/sdapi/v1/interrupt` before re-raising, so stopping the job
actually stops the remote generation too, not just Harness's wait on it.

Every output Artifact also carries a full CRE-009 provenance record
(`harness.providers.creative.provenance`) built from this request's own
`params`/the server's response -- see that module's docstring for the
AUTOMATIC1111-vs-ComfyUI scope boundary.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from typing import Any, Literal

from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.errors import UnsupportedCapabilityError
from harness.events.model import Event, EventResource
from harness.jobs.manager import JobHandle
from harness.providers.creative.a1111.client import A1111Client
from harness.providers.creative.provenance import (
    GenerationProvenance,
    extract_loras_from_prompt,
    now_iso,
    resolve_checkpoint_hash,
    strip_lora_tags,
)

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
    profile_id: str | None = None,
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

        generation_started = time.monotonic()
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
        duration_ms = (time.monotonic() - generation_started) * 1000

        await app.publish(
            Event(
                type="creative.a1111.generated",
                resource=resource,
                context={"job_id": handle.job_id},
                payload={"operation": operation, "image_count": len(result.get("images", []))},
            )
        )

        provenance = await _build_provenance(
            app,
            engine_id=engine_id,
            base_url=base_url,
            params=params,
            result=result,
            duration_ms=duration_ms,
            profile_id=profile_id,
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
                    **provenance.to_metadata(),
                },
            )
            output_artifact_ids.append(artifact.id)

        return {"operation": operation, "output_artifact_ids": output_artifact_ids}
    finally:
        await client.aclose()


async def _build_provenance(
    app: Application,
    *,
    engine_id: str,
    base_url: str,
    params: dict[str, Any],
    result: dict[str, Any],
    duration_ms: float,
    profile_id: str | None,
) -> GenerationProvenance:
    """CRE-009: every field here comes from a flat, source-verified A1111
    request/response field (`params`, built by `a1111.profiles.
    merge_profile_params`, or `result`'s ``info`` string) -- nothing is
    inferred beyond what the request actually carried or the server
    actually reported.
    """
    override_settings = params.get("override_settings") or {}
    checkpoint = override_settings.get("sd_model_checkpoint")
    raw_prompt = params.get("prompt", "")

    seed = params.get("seed")
    try:
        reported_seed = json.loads(result.get("info", "{}")).get("seed")
    except (TypeError, ValueError):
        reported_seed = None
    if reported_seed is not None:
        seed = reported_seed  # the authoritative value when the request's own seed was -1/random

    return GenerationProvenance(
        engine_id=engine_id,
        host=base_url,
        timestamp=now_iso(),
        duration_ms=duration_ms,
        profile_id=profile_id,
        checkpoint=checkpoint,
        checkpoint_hash=await resolve_checkpoint_hash(app, checkpoint),
        vae=override_settings.get("sd_vae"),
        loras=extract_loras_from_prompt(raw_prompt),
        prompt=strip_lora_tags(raw_prompt),
        negative_prompt=params.get("negative_prompt"),
        seed=seed,
        sampler=params.get("sampler_name"),
        scheduler=params.get("scheduler"),
        width=params.get("width"),
        height=params.get("height"),
        steps=params.get("steps"),
        cfg_scale=params.get("cfg_scale"),
    )
