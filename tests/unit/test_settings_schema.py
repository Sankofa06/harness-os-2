import pytest

from harness.core.errors import ValidationFailedError
from harness.core.settings_schema import SettingsSchema, validate_settings


def _schema() -> SettingsSchema:
    return SettingsSchema(
        common={
            "type": "object",
            "properties": {"temperature": {"type": "number", "minimum": 0, "maximum": 2}},
        },
        provider={
            "openrouter": {
                "type": "object",
                "properties": {"routing": {"type": "object"}},
            }
        },
    )


def test_valid_common_and_provider_settings_pass() -> None:
    settings = {
        "common": {"temperature": 0.5},
        "provider": {"openrouter": {"routing": {"prefer": "fastest"}}},
    }
    assert validate_settings(_schema(), settings) == settings


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        validate_settings(_schema(), {"common": {}, "bogus": {}})


def test_invalid_common_field_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        validate_settings(_schema(), {"common": {"temperature": 99}})


def test_unknown_provider_namespace_rejected_without_passthrough() -> None:
    with pytest.raises(ValidationFailedError):
        validate_settings(_schema(), {"provider": {"unknown-engine": {"x": 1}}})


def test_unknown_provider_namespace_allowed_with_passthrough() -> None:
    schema = SettingsSchema(allow_passthrough=True)
    settings = {"provider": {"unknown-engine": {"anything": "goes"}}}
    assert validate_settings(schema, settings) == settings


def test_empty_settings_are_valid() -> None:
    assert validate_settings(_schema(), {}) == {}
