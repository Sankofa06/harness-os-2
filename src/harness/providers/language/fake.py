"""Deterministic in-process language provider.

A first-class adapter (DECISIONS.md D-010): drives CI, the adapter conformance suite,
and seeded demo mode. Output is a pure function of the request, so screenshots and
tests are reproducible. No network access.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from typing import Any

from harness.core.capabilities import AdapterLevel
from harness.core.errors import NotFoundError
from harness.providers.language.base import (
    ChatRequest,
    ChatStreamItem,
    ChatUsage,
    LanguageProvider,
    ModelInfo,
    ModelInstance,
)

_MODELS = [
    ModelInfo(
        id="fake-mini",
        name="Fake Mini (deterministic)",
        provider="fake",
        context_length=32768,
        loaded=True,
    ),
    ModelInfo(
        id="fake-large",
        name="Fake Large (deterministic)",
        provider="fake",
        context_length=131072,
        loaded=False,
    ),
]


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


class FakeProvider(LanguageProvider):
    provider_id = "fake"
    display_name = "Deterministic Fixture Provider"

    def __init__(self, *, inter_token_delay: float = 0.0) -> None:
        self._delay = inter_token_delay

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset(
            {
                AdapterLevel.L0_CHAT,
                AdapterLevel.L1_TOOLS,
                AdapterLevel.L2_RUNTIME,
                AdapterLevel.L3_LIFECYCLE,
                AdapterLevel.L4_TELEMETRY,
            }
        )

    async def list_models(self) -> list[ModelInfo]:
        return list(_MODELS)

    async def load_model(self, model_id: str, **options: Any) -> ModelInstance:
        if model_id not in {m.id for m in _MODELS}:
            raise NotFoundError(f"unknown fake model: {model_id}")
        return ModelInstance(
            instance_id=f"{model_id}:fake",
            model_id=model_id,
            status="loaded",
            load_time_seconds=0.0,
        )

    async def unload_model(self, instance_id: str) -> None:
        return None

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        digest = hashlib.sha256(
            "\n".join(f"{m.role}:{m.content}" for m in request.messages).encode()
        ).hexdigest()[:8]
        reply = (
            f"Acknowledged. Responding deterministically as {request.model} "
            f"(trace {digest}). You said: {last_user.strip()[:400]}"
        )
        input_tokens = sum(_estimate_tokens(m.content) for m in request.messages)
        words = reply.split(" ")
        for i, word in enumerate(words):
            if self._delay:
                await asyncio.sleep(self._delay)
            yield ChatStreamItem(delta=word if i == 0 else f" {word}")
        yield ChatStreamItem(
            done=True,
            finish_reason="stop",
            usage=ChatUsage(input_tokens=input_tokens, output_tokens=len(words)),
        )
