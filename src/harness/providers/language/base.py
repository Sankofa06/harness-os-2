"""Language-provider adapter contract (SPEC/PROVIDER_MATRIX.md levels L0-L5).

Adapters normalize common behavior and declare capabilities explicitly; asking an
adapter for an undeclared capability raises ``UnsupportedCapabilityError`` rather
than faking parity (ADR 0003).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.core.capabilities import AdapterLevel
from harness.core.control_plane import ControlPlaneDescriptor, ResourceHealth
from harness.core.errors import UnsupportedCapabilityError
from harness.core.settings_schema import SettingsSchema


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    # Namespaced settings: {"common": {...}, "provider": {"<name>": {...}}}
    # (SPEC/PROVIDER_MATRIX.md)
    settings: dict[str, Any] = Field(default_factory=dict)


class ChatUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    # Authoritative USD cost, when a provider reports real spend (SPEC/ANALYTICS_
    # BENCHMARKS.md "estimated/actual cloud cost when provider supplies pricing/usage").
    cost: float | None = None


class ChatStreamItem(BaseModel):
    """One streamed item; the final item has ``done=True`` and carries usage."""

    delta: str = ""
    done: bool = False
    usage: ChatUsage | None = None
    finish_reason: str | None = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    context_length: int | None = None
    loaded: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelInstance(BaseModel):
    """A running load of a model, returned by lifecycle operations (L3)."""

    instance_id: str
    model_id: str
    status: str
    load_time_seconds: float | None = None


class LanguageProvider(ABC):
    """Base adapter. Subclasses set ``provider_id``/``display_name`` and capabilities."""

    provider_id: str
    display_name: str

    @abstractmethod
    def capabilities(self) -> frozenset[AdapterLevel]:
        """Declared capability levels; absence means explicitly unsupported."""

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        """Stream a chat completion (L0). Must yield a final ``done`` item."""

    async def list_models(self) -> list[ModelInfo]:
        """Model discovery (L2)."""
        raise UnsupportedCapabilityError(
            f"provider {self.provider_id} does not support model discovery"
        )

    async def load_model(self, model_id: str, **options: Any) -> ModelInstance:
        """Load a model into memory (L3)."""
        raise UnsupportedCapabilityError(
            f"provider {self.provider_id} does not support model lifecycle control"
        )

    async def unload_model(self, instance_id: str) -> None:
        """Unload a running model instance (L3)."""
        raise UnsupportedCapabilityError(
            f"provider {self.provider_id} does not support model lifecycle control"
        )

    def settings_schema(self) -> SettingsSchema:
        """Namespaced settings schema (CP-002). Base: no adapter-specific fields."""
        return SettingsSchema(
            common={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_output_tokens": {"type": "integer", "minimum": 1},
                },
            }
        )

    def require(self, level: AdapterLevel) -> None:
        if level not in self.capabilities():
            raise UnsupportedCapabilityError(
                f"provider {self.provider_id} does not support {level.name}"
            )

    def describe(self) -> ControlPlaneDescriptor:
        """Control-plane descriptor (SPEC/ARCHITECTURE.md vocabulary)."""
        return ControlPlaneDescriptor(
            id=self.provider_id,
            type="language_provider",
            display_name=self.display_name,
            capabilities=sorted(level.name for level in self.capabilities()),
            state="available",
            settings_schema=self.settings_schema().to_dict(),
            health=ResourceHealth.OK,
            events=["inference.started", "inference.token", "inference.completed"],
        )
