"""Native Google Gemini adapter (SPEC/PROVIDER_MATRIX.md: L1/L4).

Uses the classic `generateContent`/`streamGenerateContent` API rather than the newer
stateful Interactions API (GA June 2026): Google's own guidance keeps `generateContent`
as the recommended path for "simple, stateless, low-latency model calls", which is
exactly Harness's contract — the Context Compiler already owns conversation state
(same reasoning as LM Studio/D-015, Ollama/D-016). `?alt=sse` requests SSE framing so
this can share the same line-parsing shape as the other streaming adapters.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from harness.core.capabilities import AdapterLevel
from harness.core.errors import ProviderError
from harness.core.settings_schema import SettingsSchema
from harness.providers.language.base import (
    ChatRequest,
    ChatStreamItem,
    ChatUsage,
    LanguageProvider,
    ModelInfo,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LanguageProvider):
    provider_id = "gemini"
    display_name = "Google Gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"x-goog-api-key": api_key} if api_key else {}
        self._client = http_client or httpx.AsyncClient(headers=headers, timeout=60.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset({AdapterLevel.L0_CHAT, AdapterLevel.L1_TOOLS, AdapterLevel.L4_TELEMETRY})

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(f"{self._base_url}/models")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"gemini: model discovery failed: {exc}") from exc
        return [
            ModelInfo(
                id=m["name"].removeprefix("models/"),
                name=m.get("displayName", m["name"]),
                provider=self.provider_id,
                context_length=m.get("inputTokenLimit"),
            )
            for m in resp.json().get("models", [])
        ]

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        common = request.settings.get("common", {})
        system_parts = [m.content for m in request.messages if m.role == "system"]
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in request.messages
            if m.role != "system"
        ]
        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        generation_config = {}
        if "temperature" in common:
            generation_config["temperature"] = common["temperature"]
        if "max_output_tokens" in common:
            generation_config["maxOutputTokens"] = common["max_output_tokens"]
        if generation_config:
            payload["generationConfig"] = generation_config

        url = f"{self._base_url}/models/{request.model}:streamGenerateContent?alt=sse"
        try:
            async with self._client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = json.loads(line.removeprefix("data:").strip())
                    yield _parse_chunk(chunk)
        except httpx.HTTPError as exc:
            raise ProviderError(f"gemini: chat failed: {exc}") from exc

    def settings_schema(self) -> SettingsSchema:
        return SettingsSchema(
            common={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_output_tokens": {"type": "integer", "minimum": 1},
                },
            }
        )


def _parse_chunk(chunk: dict[str, Any]) -> ChatStreamItem:
    candidates = chunk.get("candidates") or []
    delta = ""
    finish_reason = None
    if candidates:
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        delta = "".join(p.get("text", "") for p in parts)
        finish_reason = candidate.get("finishReason")

    usage_meta = chunk.get("usageMetadata")
    usage = (
        ChatUsage(
            input_tokens=usage_meta.get("promptTokenCount"),
            output_tokens=usage_meta.get("candidatesTokenCount"),
        )
        if usage_meta
        else None
    )
    return ChatStreamItem(
        delta=delta,
        done=finish_reason is not None,
        finish_reason=finish_reason,
        usage=usage if finish_reason is not None else None,
    )
