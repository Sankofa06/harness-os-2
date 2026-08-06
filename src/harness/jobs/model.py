"""Job domain model: cancelable async units of work (SPEC/PRODUCT.md, API_CONTRACT.md)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]


class Job(BaseModel):
    id: str
    type: str
    status: JobStatus = "queued"
    progress: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    correlation_id: str | None = None
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
