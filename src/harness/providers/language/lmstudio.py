"""LM Studio adapter: native v1 REST API for discovery/lifecycle (L5), OpenAI-
compatible endpoint for chat (SPEC/PROVIDER_MATRIX.md).

Verified against LM Studio's public docs (lmstudio.ai/docs/developer/rest/*,
August 2026): the native API is stateless-model-management only — chat itself is
served through the OpenAI-compatible surface, so this adapter delegates chat_stream
to OpenAICompatibleProvider and only adds the native discovery/lifecycle calls.
Only the request/response fields LM Studio documents are used; nothing is
hard-coded beyond what the API actually advertises (SPEC/PROVIDER_MATRIX.md).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from harness.core.capabilities import AdapterLevel
from harness.core.errors import ProviderError
from harness.core.settings_schema import SettingsSchema
from harness.providers.language.base import (
    ChatRequest,
    ChatStreamItem,
    LanguageProvider,
    ModelInfo,
    ModelInstance,
)
from harness.providers.language.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "http://127.0.0.1:1234"


class LMStudioProvider(LanguageProvider):
    provider_id = "lmstudio"
    display_name = "LM Studio"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = http_client or httpx.AsyncClient(headers=headers, timeout=60.0)
        self._owns_client = http_client is None
        self._chat = OpenAICompatibleProvider(
            provider_id=self.provider_id,
            display_name=self.display_name,
            base_url=f"{self._base_url}/v1",
            http_client=self._client,
        )

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

    def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        return self._chat.chat_stream(request)

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(f"{self._base_url}/api/v1/models")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"lmstudio: model discovery failed: {exc}") from exc
        models = []
        for m in resp.json().get("data", []):
            models.append(
                ModelInfo(
                    id=m["id"],
                    name=m["id"],
                    provider=self.provider_id,
                    context_length=m.get("max_context_length"),
                    loaded=m.get("state") == "loaded",
                    metadata={
                        k: v
                        for k, v in m.items()
                        if k
                        in (
                            "type",
                            "publisher",
                            "arch",
                            "compatibility_type",
                            "quantization",
                            "state",
                        )
                    },
                )
            )
        return models

    async def load_model(self, model_id: str, **options: Any) -> ModelInstance:
        payload: dict[str, Any] = {"model": model_id, **options}
        try:
            resp = await self._client.post(f"{self._base_url}/api/v1/models/load", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"lmstudio: load failed for {model_id}: {exc}") from exc
        body = resp.json()
        return ModelInstance(
            instance_id=body["instance_id"],
            model_id=model_id,
            status=body.get("status", "loaded"),
            load_time_seconds=body.get("load_time_seconds"),
        )

    async def unload_model(self, instance_id: str) -> None:
        try:
            resp = await self._client.post(
                f"{self._base_url}/api/v1/models/unload", json={"instance_id": instance_id}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"lmstudio: unload failed for {instance_id}: {exc}") from exc

    def settings_schema(self) -> SettingsSchema:
        # Load-time fields LM Studio's REST docs document for /api/v1/models/load.
        # Runtime discovery of a wider surface isn't exposed by the API today; this
        # adapter must not invent settings the installed version can't act on
        # (SPEC/PROVIDER_MATRIX.md).
        return SettingsSchema(
            common={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_output_tokens": {"type": "integer", "minimum": 1},
                },
            },
            provider={
                "lmstudio": {
                    "type": "object",
                    "properties": {
                        "context_length": {"type": "integer", "minimum": 1},
                        "eval_batch_size": {"type": "integer", "minimum": 1},
                        "flash_attention": {"type": "boolean"},
                        "offload_kv_to_gpu": {"type": "boolean"},
                    },
                }
            },
        )
