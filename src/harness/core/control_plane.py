"""Control-plane vocabulary every manageable subsystem exposes (SPEC/ARCHITECTURE.md).

Hosts, language engines, creative engines, model instances, jobs, tools, artifacts,
and agents all describe themselves the same way: identity/capabilities/state/
settings-schema/settings/actions/telemetry/history/health/events. Adapters that don't
support a facet leave it empty/None rather than faking it (ADR 0003).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ResourceHealth(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class ControlPlaneDescriptor(BaseModel):
    id: str
    type: str
    display_name: str
    capabilities: list[str] = Field(default_factory=list)
    state: str = "unknown"
    settings_schema: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    actions: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] | None = None
    health: ResourceHealth = ResourceHealth.UNKNOWN
    events: list[str] = Field(default_factory=list)


@runtime_checkable
class ControlPlaneResource(Protocol):
    """Anything the control plane can list, whether or not it's persisted."""

    def describe(self) -> ControlPlaneDescriptor: ...
