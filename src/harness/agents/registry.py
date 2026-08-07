"""Tracks in-flight per-contact run Tasks so `POST /sessions/{id}/stop` can cancel
them cooperatively (AGT-007).

Every contact's run now executes as its own `asyncio.Task` (agents/runloop.py),
concurrently with any other contacts mentioned in the same message — this
registry is what lets a *different*, later HTTP request reach in and cancel a
task a still-in-flight `POST /sessions/{id}/messages` call created, since both
run on the same event loop.
"""

from __future__ import annotations

import asyncio


class RunRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[object]] = {}
        self._session_runs: dict[str, set[str]] = {}

    def register(self, run_id: str, session_id: str, task: asyncio.Task[object]) -> None:
        self._tasks[run_id] = task
        self._session_runs.setdefault(session_id, set()).add(run_id)

    def unregister(self, run_id: str, session_id: str) -> None:
        self._tasks.pop(run_id, None)
        members = self._session_runs.get(session_id)
        if members is not None:
            members.discard(run_id)
            if not members:
                del self._session_runs[session_id]

    def cancel_run(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def cancel_session(self, session_id: str) -> list[str]:
        """Cancel every currently in-flight run for `session_id`. Returns the run
        IDs actually canceled (already-finished runs are silently skipped).
        """
        run_ids = list(self._session_runs.get(session_id, ()))
        return [run_id for run_id in run_ids if self.cancel_run(run_id)]
