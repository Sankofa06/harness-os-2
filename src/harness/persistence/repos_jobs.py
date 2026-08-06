"""Job repository. Kept in its own module to avoid growing `repos.py` further."""

from __future__ import annotations

import json
from typing import Any

from harness.core.errors import NotFoundError
from harness.jobs.model import Job, JobStatus
from harness.persistence.db import Database


class JobRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, job: Job) -> Job:
        await self._db.execute(
            "INSERT INTO jobs (id, type, status, progress, detail_json, correlation_id) "
            "VALUES (:id, :type, :status, :progress, :detail_json, :correlation_id)",
            {
                "id": job.id,
                "type": job.type,
                "status": job.status,
                "progress": job.progress,
                "detail_json": json.dumps(job.detail),
                "correlation_id": job.correlation_id,
            },
        )
        return job

    async def get(self, job_id: str) -> Job:
        row = await self._db.fetch_one("SELECT * FROM jobs WHERE id = :id", {"id": job_id})
        if row is None:
            raise NotFoundError(f"job not found: {job_id}")
        return _job(row)

    async def list(self) -> list[Job]:
        rows = await self._db.fetch_all("SELECT * FROM jobs ORDER BY created_at DESC")
        return [_job(r) for r in rows]

    async def set_status(self, job_id: str, status: JobStatus, *, error: str | None = None) -> None:
        updates = ["status = :status"]
        params: dict[str, Any] = {"status": status, "id": job_id}
        if status == "running":
            updates.append("started_at = datetime('now')")
        if status in ("succeeded", "failed", "canceled"):
            updates.append("finished_at = datetime('now')")
        if error is not None:
            updates.append("error = :error")
            params["error"] = error
        await self._db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = :id",
            params,
        )

    async def set_progress(self, job_id: str, progress: float) -> None:
        await self._db.execute(
            "UPDATE jobs SET progress = :p WHERE id = :id", {"p": progress, "id": job_id}
        )


def _job(row: Any) -> Job:
    return Job(
        id=row["id"],
        type=row["type"],
        status=row["status"],
        progress=row["progress"],
        detail=json.loads(row["detail_json"]),
        error=row["error"],
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
