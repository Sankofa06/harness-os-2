"""Native OpenAI adapter (SPEC/PROVIDER_MATRIX.md: L1/L4).

OpenAI's own API *is* the OpenAI-compatible shape (it's the reference
implementation) — this is a thin identity around OpenAICompatibleProvider with the
real endpoint and a fixed provider_id, so cost/settings namespacing is unambiguous
in the UI even though the wire protocol is identical.
"""

from __future__ import annotations

import httpx

from harness.providers.language.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            provider_id="openai",
            display_name="OpenAI",
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
        )
