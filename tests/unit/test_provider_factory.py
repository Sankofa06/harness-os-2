import pytest

from harness.core.domain import ProviderConfig
from harness.core.errors import UnsupportedCapabilityError
from harness.core.ids import new_id
from harness.providers.language.anthropic import AnthropicProvider
from harness.providers.language.factory import build_provider
from harness.providers.language.gemini import GeminiProvider
from harness.providers.language.lmstudio import LMStudioProvider
from harness.providers.language.ollama import OllamaProvider
from harness.providers.language.openai import OpenAIProvider
from harness.providers.language.openai_compat import OpenAICompatibleProvider
from harness.providers.language.openrouter import OpenRouterProvider


def _config(provider_type: str, **overrides) -> ProviderConfig:
    return ProviderConfig(
        id=new_id("prov"), type=provider_type, display_name=f"{provider_type}-config", **overrides
    )


def test_provider_id_is_overridden_to_config_id_not_adapter_default() -> None:
    config = _config("anthropic")
    provider = build_provider(config, secret_value="sk-test")
    assert provider.provider_id == config.id
    assert isinstance(provider, AnthropicProvider)


def test_each_provider_type_maps_to_the_right_adapter_class() -> None:
    cases = [
        ("lmstudio", LMStudioProvider),
        ("ollama", OllamaProvider),
        ("openrouter", OpenRouterProvider),
        ("openai", OpenAIProvider),
        ("anthropic", AnthropicProvider),
        ("gemini", GeminiProvider),
    ]
    for provider_type, expected_class in cases:
        provider = build_provider(_config(provider_type), secret_value=None)
        assert isinstance(provider, expected_class), provider_type


def test_openai_compatible_requires_base_url() -> None:
    with pytest.raises(UnsupportedCapabilityError):
        build_provider(_config("openai_compatible"), secret_value=None)


def test_openai_compatible_with_base_url_builds() -> None:
    config = _config("openai_compatible", base_url="http://127.0.0.1:8080/v1")
    provider = build_provider(config, secret_value=None)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_id == config.id


def test_unknown_provider_type_rejected() -> None:
    with pytest.raises(UnsupportedCapabilityError):
        build_provider(_config("not-a-real-provider"), secret_value=None)
