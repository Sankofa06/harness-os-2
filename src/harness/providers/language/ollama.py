"""Ollama adapter (SPEC/PROVIDER_MATRIX.md: L4/L5 where exposed).

Verified against Ollama's public API reference (github.com/ollama/ollama/docs/api.md,
August 2026). Unlike LM Studio, Ollama has no separate "load" endpoint: sending a
request with no prompt/messages loads the model, and `keep_alive: 0` unloads it — both
folded into `/api/generate`. There is also no multi-instance concept; a model name is
its own instance identifier.
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
    ModelInstance,
)


class OllamaProvider(LanguageProvider):
    provider_id = "ollama"
    display_name = "Ollama"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset(
            {
                AdapterLevel.L0_CHAT,
                AdapterLevel.L1_TOOLS,
                AdapterLevel.L2_RUNTIME,
                AdapterLevel.L3_LIFECYCLE,
                AdapterLevel.L4_TELEMETRY,
                AdapterLevel.L5_NATIVE_EXTRAS,
            }
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama: model discovery failed: {exc}") from exc
        models = []
        for m in resp.json().get("models", []):
            details = m.get("details", {})
            models.append(
                ModelInfo(
                    id=m["model"],
                    name=m.get("name", m["model"]),
                    provider=self.provider_id,
                    metadata={
                        "digest": m.get("digest"),
                        "size": m.get("size"),
                        "family": details.get("family"),
                        "parameter_size": details.get("parameter_size"),
                        "quantization_level": details.get("quantization_level"),
                    },
                )
            )
        return models

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        common = request.settings.get("common", {})
        options = request.settings.get("provider", {}).get("ollama", {})
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        if common or options:
            payload["options"] = {**_translate_common(common), **options}
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    yield _parse_line(json.loads(line))
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama: chat failed: {exc}") from exc

    async def load_model(self, model_id: str, **options: Any) -> ModelInstance:
        # Ollama loads a model by sending a generate request with no prompt.
        payload: dict[str, Any] = {"model": model_id}
        if options:
            payload["options"] = options
        try:
            resp = await self._client.post(f"{self._base_url}/api/generate", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama: load failed for {model_id}: {exc}") from exc
        return ModelInstance(instance_id=model_id, model_id=model_id, status="loaded")

    async def unload_model(self, instance_id: str) -> None:
        # keep_alive: 0 with no prompt unloads immediately.
        try:
            resp = await self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": instance_id, "keep_alive": 0},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama: unload failed for {instance_id}: {exc}") from exc

    def settings_schema(self) -> SettingsSchema:
        return SettingsSchema(
            common={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_output_tokens": {"type": "integer", "minimum": 1},
                },
            },
            provider={
                "ollama": {
                    "type": "object",
                    "properties": {
                        "num_ctx": {"type": "integer", "minimum": 1},
                        "top_p": {"type": "number", "minimum": 0, "maximum": 1},
                        "top_k": {"type": "integer", "minimum": 0},
                        "repeat_penalty": {"type": "number"},
                        "seed": {"type": "integer"},
                        "keep_alive": {"type": ["string", "integer"]},
                    },
                }
            },
        )


def _translate_common(common: dict[str, Any]) -> dict[str, Any]:
    """Map the shared common settings vocabulary onto Ollama's `options` field names."""
    options: dict[str, Any] = {}
    if "temperature" in common:
        options["temperature"] = common["temperature"]
    if "max_output_tokens" in common:
        options["num_predict"] = common["max_output_tokens"]
    return options


def _parse_line(chunk: dict[str, Any]) -> ChatStreamItem:
    message = chunk.get("message", {})
    done = bool(chunk.get("done"))
    usage = None
    if done and "eval_count" in chunk:
        usage = ChatUsage(
            input_tokens=chunk.get("prompt_eval_count"),
            output_tokens=chunk.get("eval_count"),
        )
    return ChatStreamItem(
        delta=message.get("content", ""),
        done=done,
        finish_reason="stop" if done else None,
        usage=usage,
    )
