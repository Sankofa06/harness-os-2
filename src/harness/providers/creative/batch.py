"""Batch checkpoint/profile comparison (CRE-008, SPEC/CREATIVE_COMPUTE.md
"Batch comparison") for the AUTOMATIC1111-compatible family -- the only
family whose checkpoint/VAE/sampler/scheduler override mechanism Harness
has verified from source (CRE-004/CRE-007). ComfyUI's per-node checkpoint-
widget mutation would require guessing a specific workflow's node layout,
which this project's "verified, not guessed" discipline rules out; this is
a real, declared scope limit, not a placeholder.

Runs as a single Job (JOB-001) wrapping every cell -- canceling the batch
Job cancels whichever cell(s) are currently in flight via the same
`asyncio.Task.cancel()` propagation `run_a1111_generation` already relies
on, so stopping a batch actually stops in-flight generations, not just
Harness's wait on them.

"Capacity-aware host placement" (SPEC) is real but deliberately scoped
to what Harness can honestly track: there is no cluster-wide GPU/VRAM
telemetry for an arbitrary engine ``base_url`` yet (that's ANA-002/
NODE-001's job), so placement here means "prefer whichever candidate
``base_url`` currently has the fewest cells from *this batch* in flight" --
a real least-loaded decision within the batch's own execution context,
not an overclaimed cluster-wide scheduler.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.errors import ValidationFailedError
from harness.events.model import Event, EventResource
from harness.jobs.manager import JobHandle
from harness.providers.creative.a1111.adapter import run_a1111_generation
from harness.providers.creative.a1111.profiles import merge_profile_params


@dataclass(frozen=True)
class BatchCellSpec:
    profile_id: str | None = None
    checkpoint: str | None = None
    seed: int | None = None


class _LoadTracker:
    """Picks the candidate ``base_url`` with the fewest cells from this
    batch currently in flight. Synchronous (no ``await`` between pick and
    start), so plain dict counters are safe under asyncio's single-
    threaded concurrency -- no lock needed.
    """

    def __init__(self, base_urls: list[str]) -> None:
        self._counts = {url: 0 for url in base_urls}

    def pick(self) -> str:
        return min(self._counts, key=lambda url: self._counts[url])

    def start(self, url: str) -> None:
        self._counts[url] += 1

    def finish(self, url: str) -> None:
        self._counts[url] -= 1


async def run_batch_comparison(
    app: Application,
    handle: JobHandle,
    *,
    engine_id: str,
    base_urls: list[str],
    operation: Literal["txt2img", "img2img"],
    prompt: str,
    seed: int,
    shared_params: dict[str, Any],
    cells: list[BatchCellSpec],
    scheduling: Literal["sequential", "parallel"],
    session_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    if not cells:
        raise ValidationFailedError("at least one cell is required")
    if not base_urls:
        raise ValidationFailedError("at least one base_url is required")

    tracker = _LoadTracker(base_urls)
    resource = EventResource(type="job", id=handle.job_id)
    batch_started = time.monotonic()
    results: list[dict[str, Any] | None] = [None] * len(cells)

    async def run_cell(index: int, cell: BatchCellSpec) -> None:
        queue_started = time.monotonic()
        base_url = tracker.pick()
        tracker.start(base_url)
        checkpoint = cell.checkpoint
        cell_seed = cell.seed if cell.seed is not None else seed
        # Covers asyncio.CancelledError too (a BaseException, not an
        # Exception -- it skips the `except Exception` below), so a
        # canceled batch Job still records this cell as canceled rather
        # than leaving `cell_result` unbound in `finally`.
        cell_result: dict[str, Any] = {
            "profile_id": cell.profile_id,
            "checkpoint": checkpoint,
            "seed": cell_seed,
            "base_url": base_url,
            "status": "canceled",
            "output_artifact_ids": [],
        }
        try:
            vae = sampler = scheduler = None
            loras: list[str] = []
            if cell.profile_id is not None:
                profile = await app.creative_profiles.get(cell.profile_id)  # 404s if unknown
                if profile.engine_selector != engine_id:
                    raise ValidationFailedError(
                        f"profile {profile.name!r} targets engine "
                        f"{profile.engine_selector!r}, not {engine_id!r}"
                    )
                checkpoint = profile.checkpoint
                vae, sampler, scheduler, loras = (
                    profile.vae,
                    profile.sampler,
                    profile.scheduler,
                    profile.loras,
                )

            params = merge_profile_params(
                {**shared_params, "prompt": prompt, "seed": cell_seed},
                checkpoint=checkpoint,
                vae=vae,
                sampler=sampler,
                scheduler=scheduler,
                loras=loras,
            )
            queue_time_ms = (time.monotonic() - queue_started) * 1000
            exec_started = time.monotonic()

            generation = await run_a1111_generation(
                app,
                handle,
                base_url=base_url,
                engine_id=engine_id,
                operation=operation,
                params=params,
                session_id=session_id,
                workspace_id=workspace_id,
                profile_id=cell.profile_id,
            )
            cell_result = {
                "profile_id": cell.profile_id,
                "checkpoint": checkpoint,
                "seed": cell_seed,
                "base_url": base_url,
                "status": "succeeded",
                "output_artifact_ids": generation["output_artifact_ids"],
                "queue_time_ms": queue_time_ms,
                "duration_ms": (time.monotonic() - exec_started) * 1000,
            }
        except Exception as exc:
            cell_result = {
                "profile_id": cell.profile_id,
                "checkpoint": checkpoint,
                "seed": cell_seed,
                "base_url": base_url,
                "status": "failed",
                "output_artifact_ids": [],
                "error": str(exc),
            }
        finally:
            results[index] = cell_result
            tracker.finish(base_url)
            completed = sum(1 for r in results if r is not None)
            await handle.set_progress(completed / len(cells))
            await app.publish(
                Event(
                    type="creative.batch.cell_completed",
                    resource=resource,
                    context={"job_id": handle.job_id},
                    payload=cell_result,
                )
            )

    if scheduling == "parallel":
        await asyncio.gather(*(run_cell(i, c) for i, c in enumerate(cells)))
    else:
        for i, c in enumerate(cells):
            await run_cell(i, c)

    manifest = {
        "engine_id": engine_id,
        "prompt": prompt,
        "seed": seed,
        "operation": operation,
        "scheduling": scheduling,
        "cells": results,
        "total_duration_ms": (time.monotonic() - batch_started) * 1000,
    }
    manifest_artifact = await store_and_record_artifact(
        app,
        type="document",
        display_name="creative-batch-comparison.json",
        content=json.dumps(manifest, indent=2).encode("utf-8"),
        mime_type="application/json",
        session_id=session_id,
        workspace_id=workspace_id,
        metadata={"engine_id": engine_id, "kind": "creative_batch_comparison"},
    )
    return {"cells": results, "manifest_artifact_id": manifest_artifact.id}
