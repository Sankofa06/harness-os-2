"""Job endpoints (SPEC/API_CONTRACT.md)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.jobs.model import Job

router = APIRouter(dependencies=[Depends(require_auth)], tags=["jobs"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


@router.get("/jobs")
async def list_jobs(request: Request) -> list[Job]:
    return await _app(request).jobs.list()


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str) -> Job:
    return await _app(request).jobs.get(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str) -> Job:
    return await _app(request).job_manager.cancel(job_id)
