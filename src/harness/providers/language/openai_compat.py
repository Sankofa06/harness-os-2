"""Generic OpenAI-compatible adapter (SPEC/PROVIDER_MATRIX.md, required L1).

Works against any server exposing the OpenAI Chat Completions + Models shape: a
self-hosted OpenAI-compatible endpoint, and the fallback path other adapters
(LM Studio, OpenRouter) use when their native API is unavailable.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from harness.core.capabilities import AdapterLevel
from harness.core.errors import ProviderError
from harness.providers.language.base import (
    ChatRequest,
    ChatStreamItem,
    ChatUsage,
    LanguageProvider,
    ModelInfo,
)


class OpenAICompatibleProvider(LanguageProvider):
    def __init__(
        self,
        provider_id: str,
        display_name: str,
        base_url: str,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.display_name = display_name
        self._base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = http_client or httpx.AsyncClient(headers=headers, timeout=60.0)
        self._owns_client = http_client is None
        # Subclasses (e.g. OpenRouter) that need provider-specific request fields on
        # every chat call inject them here rather than duplicating chat_stream.
        self._extra_payload = extra_payload or {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset(
            {
                AdapterLevel.L0_CHAT,
                AdapterLevel.L1_TOOLS,
                AdapterLevel.L2_RUNTIME,
                AdapterLevel.L4_TELEMETRY,
            }
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(f"{self._base_url}/models")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.provider_id}: model discovery failed: {exc}") from exc
        return [
            ModelInfo(id=m["id"], name=m.get("id", m["id"]), provider=self.provider_id)
            for m in resp.json().get("data", [])
        ]

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        common = request.settings.get("common", {})
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            **self._extra_payload,
            **common,
        }
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/chat/completions", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    yield _parse_chunk(chunk)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.provider_id}: chat completion failed: {exc}") from exc


def _parse_chunk(chunk: dict[str, Any]) -> ChatStreamItem:
    usage_data = chunk.get("usage")
    usage = (
        ChatUsage(
            input_tokens=usage_data.get("prompt_tokens"),
            output_tokens=usage_data.get("completion_tokens"),
            cost=usage_data.get("cost"),
        )
        if usage_data
        else None
    )
    choices = chunk.get("choices") or []
    if not choices:
        return ChatStreamItem(done=usage is not None, usage=usage)
    choice = choices[0]
    delta = choice.get("delta", {}).get("content") or ""
    finish_reason = choice.get("finish_reason")
    return ChatStreamItem(
        delta=delta,
        done=finish_reason is not None,
        finish_reason=finish_reason,
        usage=usage,
    )
