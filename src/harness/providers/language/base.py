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
from harness.core.errors import UnsupportedCapabilityError


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

    def require(self, level: AdapterLevel) -> None:
        if level not in self.capabilities():
            raise UnsupportedCapabilityError(
                f"provider {self.provider_id} does not support {level.name}"
            )
