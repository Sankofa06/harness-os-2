"""Builds a live `LanguageProvider` adapter from a persisted `ProviderConfig` (LP-009).

The in-memory `ProviderRegistry` is keyed by `provider_id`; adapters constructed here
have their `provider_id` set to the `ProviderConfig.id` (not the adapter class's
default) so multiple configs of the same `type` — two OpenAI-compatible endpoints, two
OpenRouter accounts — coexist in the registry as distinct entries. `provider_id` is a
plain mutable attribute on every adapter (never a frozen class constant read
elsewhere), so this is a legitimate post-construction override, not a hack.
"""

from __future__ import annotations

from harness.core.domain import ProviderConfig
from harness.core.errors import UnsupportedCapabilityError
from harness.providers.language.anthropic import DEFAULT_BASE_URL as ANTHROPIC_DEFAULT_BASE_URL
from harness.providers.language.anthropic import AnthropicProvider
from harness.providers.language.base import LanguageProvider
from harness.providers.language.fake import FakeProvider
from harness.providers.language.gemini import DEFAULT_BASE_URL as GEMINI_DEFAULT_BASE_URL
from harness.providers.language.gemini import GeminiProvider
from harness.providers.language.lmstudio import DEFAULT_BASE_URL as LMSTUDIO_DEFAULT_BASE_URL
from harness.providers.language.lmstudio import LMStudioProvider
from harness.providers.language.ollama import DEFAULT_BASE_URL as OLLAMA_DEFAULT_BASE_URL
from harness.providers.language.ollama import OllamaProvider
from harness.providers.language.openai import DEFAULT_BASE_URL as OPENAI_DEFAULT_BASE_URL
from harness.providers.language.openai import OpenAIProvider
from harness.providers.language.openai_compat import OpenAICompatibleProvider
from harness.providers.language.openrouter import (
    DEFAULT_BASE_URL as OPENROUTER_DEFAULT_BASE_URL,
)
from harness.providers.language.openrouter import OpenRouterProvider


def build_provider(config: ProviderConfig, secret_value: str | None) -> LanguageProvider:
    """Construct the adapter for ``config.type``. Raises for an unknown type."""
    provider: LanguageProvider
    if config.type == "fake":
        provider = FakeProvider()
    elif config.type == "openai_compatible":
        if not config.base_url:
            raise UnsupportedCapabilityError("openai_compatible providers require base_url")
        provider = OpenAICompatibleProvider(
            provider_id=config.id,
            display_name=config.display_name,
            base_url=config.base_url,
            api_key=secret_value,
        )
    elif config.type == "lmstudio":
        provider = LMStudioProvider(
            base_url=config.base_url or LMSTUDIO_DEFAULT_BASE_URL, api_key=secret_value
        )
    elif config.type == "ollama":
        provider = OllamaProvider(base_url=config.base_url or OLLAMA_DEFAULT_BASE_URL)
    elif config.type == "openrouter":
        provider = OpenRouterProvider(
            api_key=secret_value, base_url=config.base_url or OPENROUTER_DEFAULT_BASE_URL
        )
    elif config.type == "openai":
        provider = OpenAIProvider(
            api_key=secret_value, base_url=config.base_url or OPENAI_DEFAULT_BASE_URL
        )
    elif config.type == "anthropic":
        provider = AnthropicProvider(
            api_key=secret_value, base_url=config.base_url or ANTHROPIC_DEFAULT_BASE_URL
        )
    elif config.type == "gemini":
        provider = GeminiProvider(
            api_key=secret_value, base_url=config.base_url or GEMINI_DEFAULT_BASE_URL
        )
    else:
        raise UnsupportedCapabilityError(f"unknown provider type: {config.type}")

    provider.provider_id = config.id
    provider.display_name = config.display_name
    return provider
