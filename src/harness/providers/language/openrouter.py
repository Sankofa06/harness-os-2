"""OpenRouter adapter (SPEC/PROVIDER_MATRIX.md: L1/L4, cloud model catalog + pricing).

OpenRouter's chat/completions surface is OpenAI-compatible, so this reuses
OpenAICompatibleProvider entirely for chat and only adds model catalog + pricing
metadata, plus requesting authoritative per-request cost via ``usage: {"include":
true}`` (verified against OpenRouter's public API docs, August 2026).
"""

from __future__ import annotations

import httpx

from harness.core.capabilities import AdapterLevel
from harness.core.errors import ProviderError
from harness.providers.language.base import ModelInfo
from harness.providers.language.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            provider_id="openrouter",
            display_name="OpenRouter",
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
            extra_payload={"usage": {"include": True}},
        )

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
            raise ProviderError(f"openrouter: model discovery failed: {exc}") from exc
        models = []
        for m in resp.json().get("data", []):
            pricing = m.get("pricing", {})
            models.append(
                ModelInfo(
                    id=m["id"],
                    name=m.get("name", m["id"]),
                    provider=self.provider_id,
                    context_length=m.get("context_length"),
                    metadata={
                        "description": m.get("description"),
                        "pricing_prompt_usd_per_token": pricing.get("prompt"),
                        "pricing_completion_usd_per_token": pricing.get("completion"),
                    },
                )
            )
        return models
