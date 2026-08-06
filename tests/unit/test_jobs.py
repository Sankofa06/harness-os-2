import asyncio

import pytest

from harness.events.bus import EventBus
from harness.events.model import EventFilter
from harness.jobs.manager import JobManager
from harness.persistence.repos_jobs import JobRepo


@pytest.fixture
async def manager(db):
    return JobManager(repo=JobRepo(db), bus=EventBus())


@pytest.mark.asyncio
async def test_job_succeeds_and_persists_result(manager: JobManager) -> None:
    async def work(handle):
        await handle.set_progress(0.5)
        return {"answer": 42}

    job = await manager.submit("demo", work)
    for _ in range(50):
        current = await manager.repo.get(job.id)
        if current.status in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.01)

    assert current.status == "succeeded"
    assert current.progress == 0.5


@pytest.mark.asyncio
async def test_job_failure_is_captured_not_raised(manager: JobManager) -> None:
    async def work(handle):
        raise ValueError("boom")

    job = await manager.submit("demo", work)
    for _ in range(50):
        current = await manager.repo.get(job.id)
        if current.status in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.01)

    assert current.status == "failed"
    assert "boom" in (current.error or "")


@pytest.mark.asyncio
async def test_job_cancel_stops_work(manager: JobManager) -> None:
    started = asyncio.Event()

    async def work(handle):
        started.set()
        await asyncio.sleep(10)

    job = await manager.submit("demo", work)
    await asyncio.wait_for(started.wait(), timeout=1)
    await manager.cancel(job.id)

    for _ in range(50):
        current = await manager.repo.get(job.id)
        if current.status == "canceled":
            break
        await asyncio.sleep(0.01)

    assert current.status == "canceled"


@pytest.mark.asyncio
async def test_job_events_emitted(manager: JobManager) -> None:
    sub = manager.bus.subscribe(EventFilter(event_types=["job.started", "job.completed"]))

    async def work(handle):
        return None

    await manager.submit("demo", work)
    first = await asyncio.wait_for(sub.queue.get(), timeout=1)
    second = await asyncio.wait_for(sub.queue.get(), timeout=1)
    assert {first.type, second.type} == {"job.started", "job.completed"}
