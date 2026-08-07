import asyncio

import pytest

from harness.agents.registry import RunRegistry


async def _never_finishes() -> None:
    await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_cancel_run_cancels_a_registered_task() -> None:
    registry = RunRegistry()
    task = asyncio.create_task(_never_finishes())
    registry.register("run_1", "ses_1", task)

    assert registry.cancel_run("run_1") is True
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_cancel_run_for_unknown_run_id_returns_false() -> None:
    registry = RunRegistry()
    assert registry.cancel_run("run_nonexistent") is False


@pytest.mark.asyncio
async def test_cancel_run_for_already_finished_task_returns_false() -> None:
    registry = RunRegistry()

    async def _finishes_immediately() -> None:
        return None

    task = asyncio.create_task(_finishes_immediately())
    registry.register("run_1", "ses_1", task)
    await task

    assert registry.cancel_run("run_1") is False


@pytest.mark.asyncio
async def test_cancel_session_cancels_all_its_runs_but_not_others() -> None:
    registry = RunRegistry()
    task_a1 = asyncio.create_task(_never_finishes())
    task_a2 = asyncio.create_task(_never_finishes())
    task_b1 = asyncio.create_task(_never_finishes())
    registry.register("run_a1", "ses_a", task_a1)
    registry.register("run_a2", "ses_a", task_a2)
    registry.register("run_b1", "ses_b", task_b1)

    canceled = registry.cancel_session("ses_a")

    assert set(canceled) == {"run_a1", "run_a2"}
    assert task_a1.cancelled() or task_a1.cancelling()
    assert task_a2.cancelled() or task_a2.cancelling()
    assert not task_b1.cancelling()

    task_b1.cancel()
    for task in (task_a1, task_a2, task_b1):
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_unregister_removes_bookkeeping() -> None:
    registry = RunRegistry()
    task = asyncio.create_task(_never_finishes())
    registry.register("run_1", "ses_1", task)
    registry.unregister("run_1", "ses_1")

    assert registry.cancel_run("run_1") is False
    assert registry.cancel_session("ses_1") == []

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
