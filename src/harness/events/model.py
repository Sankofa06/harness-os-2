"""Event envelope per SPEC/API_CONTRACT.md."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from harness.core.ids import new_id


class EventResource(BaseModel):
    type: str
    id: str


class Event(BaseModel):
    """Append-only event. ``seq`` is the installation-local replay cursor (D-007).

    ``context`` carries routing keys (session_id, run_id, job_id, host_id, …) used by
    subscription filters without payload introspection.
    """

    event_id: str = Field(default_factory=lambda: new_id("evt"))
    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    resource: EventResource | None = None
    context: dict[str, str] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_version: int = 1
    seq: int | None = None


class EventFilter(BaseModel):
    """Subscription filter: empty fields match everything (SPEC/API_CONTRACT.md)."""

    event_types: list[str] = Field(default_factory=list)
    session_ids: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    host_ids: list[str] = Field(default_factory=list)

    def matches(self, event: Event) -> bool:
        if self.event_types and not any(_type_match(p, event.type) for p in self.event_types):
            return False
        if self.session_ids and event.context.get("session_id") not in self.session_ids:
            return False
        if self.job_ids and event.context.get("job_id") not in self.job_ids:
            return False
        return not (self.host_ids and event.context.get("host_id") not in self.host_ids)


def _type_match(pattern: str, event_type: str) -> bool:
    """Exact match, or prefix wildcard like ``inference.*``."""
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-1])
    return pattern == event_type
