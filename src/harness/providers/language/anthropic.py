"""Native Anthropic adapter (SPEC/PROVIDER_MATRIX.md: L1/L4).

Anthropic's Messages API is not OpenAI-shaped: a top-level ``system`` field instead
of a system-role message, a required ``max_tokens``, and a multi-event SSE stream
(message_start/content_block_delta/message_delta/message_stop) rather than one
``choices[0].delta`` shape per line.
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

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(LanguageProvider):
    provider_id = "anthropic"
    display_name = "Anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"anthropic-version": ANTHROPIC_VERSION}
        if api_key:
            headers["x-api-key"] = api_key
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
            raise ProviderError(f"anthropic: model discovery failed: {exc}") from exc
        return [
            ModelInfo(id=m["id"], name=m.get("display_name", m["id"]), provider=self.provider_id)
            for m in resp.json().get("data", [])
        ]

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        common = request.settings.get("common", {})
        system_parts = [m.content for m in request.messages if m.role == "system"]
        # Anthropic's "tool" role doesn't exist on this path yet (no tool-calling
        # wired up in the run loop); treat it as user content rather than drop it.
        turn_messages = [
            {"role": "assistant" if m.role == "assistant" else "user", "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": turn_messages,
            "max_tokens": common.get("max_output_tokens", DEFAULT_MAX_TOKENS),
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if "temperature" in common:
            payload["temperature"] = common["temperature"]

        input_tokens: int | None = None
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/messages", json=payload
            ) as resp:
                resp.raise_for_status()
                event_type = None
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line.removeprefix("event:").strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = json.loads(line.removeprefix("data:").strip())

                    if event_type == "message_start":
                        input_tokens = data.get("message", {}).get("usage", {}).get("input_tokens")
                    elif event_type == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield ChatStreamItem(delta=delta.get("text", ""))
                    elif event_type == "message_delta":
                        stop_reason = data.get("delta", {}).get("stop_reason")
                        output_tokens = data.get("usage", {}).get("output_tokens")
                        yield ChatStreamItem(
                            done=True,
                            finish_reason=stop_reason,
                            usage=ChatUsage(input_tokens=input_tokens, output_tokens=output_tokens),
                        )
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic: chat failed: {exc}") from exc

    def settings_schema(self) -> SettingsSchema:
        return SettingsSchema(
            common={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 1},
                    "max_output_tokens": {"type": "integer", "minimum": 1},
                },
            }
        )
