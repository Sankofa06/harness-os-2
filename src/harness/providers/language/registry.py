"""Runtime registry of configured language providers."""

from __future__ import annotations

from harness.core.errors import NotFoundError
from harness.providers.language.base import LanguageProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LanguageProvider] = {}

    def register(self, provider: LanguageProvider) -> None:
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> LanguageProvider:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise NotFoundError(f"language provider not configured: {provider_id}") from None

    def list(self) -> list[LanguageProvider]:
        return list(self._providers.values())
