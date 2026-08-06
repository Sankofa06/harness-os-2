"""In-process job manager: schedules cancelable async work with a persisted state
machine and event trail (SPEC/API_CONTRACT.md Jobs group; ARCHITECTURE.md event rule).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from harness.core.errors import ConflictError, NotFoundError
from harness.core.ids import new_id
from harness.events.bus import EventBus
from harness.events.model import Event, EventResource
from harness.jobs.model import Job
from harness.persistence.repos_jobs import JobRepo

logger = logging.getLogger(__name__)


@dataclass
class JobHandle:
    """Passed into job work functions so they can report progress cooperatively."""

    job_id: str
    _manager: JobManager

    async def set_progress(self, progress: float) -> None:
        await self._manager._report_progress(self.job_id, progress)


WorkFn = Callable[[JobHandle], Awaitable[dict[str, Any] | None]]


@dataclass
class JobManager:
    repo: JobRepo
    bus: EventBus
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    async def submit(
        self, job_type: str, work: WorkFn, *, detail: dict[str, Any] | None = None
    ) -> Job:
        job = Job(id=new_id("job"), type=job_type, detail=detail or {})
        await self.repo.create(job)
        await self._emit(job.id, "job.queued", {"type": job_type})
        task = asyncio.create_task(self._run(job.id, work))
        self._tasks[job.id] = task
        return job

    async def _run(self, job_id: str, work: WorkFn) -> None:
        await self.repo.set_status(job_id, "running")
        await self._emit(job_id, "job.started", {})
        try:
            handle = JobHandle(job_id=job_id, _manager=self)
            result = await work(handle)
            await self.repo.set_status(job_id, "succeeded")
            await self._emit(job_id, "job.completed", {"result": result or {}})
        except asyncio.CancelledError:
            await self.repo.set_status(job_id, "canceled")
            await self._emit(job_id, "job.canceled", {})
        except Exception as exc:
            logger.warning("job %s failed: %s", job_id, exc)
            await self.repo.set_status(job_id, "failed", error=str(exc))
            await self._emit(job_id, "job.failed", {"error": str(exc)})
        finally:
            self._tasks.pop(job_id, None)

    async def cancel(self, job_id: str) -> Job:
        job = await self.repo.get(job_id)
        if job.status in ("succeeded", "failed", "canceled"):
            raise ConflictError(f"job {job_id} already finished with status {job.status}")
        task = self._tasks.get(job_id)
        if task is None:
            raise NotFoundError(f"job {job_id} has no running task to cancel")
        task.cancel()
        return await self.repo.get(job_id)

    async def _report_progress(self, job_id: str, progress: float) -> None:
        await self.repo.set_progress(job_id, progress)
        await self._emit(job_id, "job.progress", {"progress": progress})

    async def _emit(self, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        await self.bus.publish(
            Event(
                type=event_type,
                resource=EventResource(type="job", id=job_id),
                context={"job_id": job_id},
                payload=payload,
            )
        )
