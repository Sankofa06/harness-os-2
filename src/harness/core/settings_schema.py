"""Settings-schema system (SPEC/PROVIDER_MATRIX.md "Cloud-provider schema rule", ADR 0003).

Settings are namespaced: shared fields under ``common``, provider/engine-specific
fields under ``provider.<name>``. Each namespace is described by a JSON Schema object,
so the same descriptor drives both server-side validation and a UI-rendered form.
Unknown top-level settings keys are rejected unless the schema explicitly allows
passthrough — adapters that support arbitrary native options set that flag.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from harness.core.errors import ValidationFailedError

_TOP_LEVEL_KEYS = {"common", "provider"}


class SettingsSchema:
    """A JSON-Schema-based descriptor for one resource's settings.

    ``common`` is a JSON Schema object for the ``common`` namespace. ``provider`` maps
    namespace name (e.g. an adapter's ``provider_id``) to its own JSON Schema object.
    """

    def __init__(
        self,
        common: dict[str, Any] | None = None,
        provider: dict[str, dict[str, Any]] | None = None,
        *,
        allow_passthrough: bool = False,
    ) -> None:
        self.common = common or {"type": "object", "properties": {}}
        self.provider = provider or {}
        self.allow_passthrough = allow_passthrough

    def to_dict(self) -> dict[str, Any]:
        return {
            "common": self.common,
            "provider": self.provider,
            "allow_passthrough": self.allow_passthrough,
        }


def validate_settings(schema: SettingsSchema, settings: dict[str, Any]) -> dict[str, Any]:
    """Validate a namespaced settings payload against ``schema``. Returns it unchanged."""
    unknown_top_level = set(settings) - _TOP_LEVEL_KEYS
    if unknown_top_level:
        raise ValidationFailedError(f"unknown top-level settings keys: {sorted(unknown_top_level)}")

    common_value = settings.get("common", {})
    try:
        jsonschema.validate(common_value, schema.common)
    except jsonschema.ValidationError as exc:
        raise ValidationFailedError(f"invalid 'common' settings: {exc.message}") from exc

    provider_value = settings.get("provider", {})
    for namespace, value in provider_value.items():
        if namespace not in schema.provider:
            if schema.allow_passthrough:
                continue
            raise ValidationFailedError(f"unknown settings namespace: {namespace}")
        try:
            jsonschema.validate(value, schema.provider[namespace])
        except jsonschema.ValidationError as exc:
            raise ValidationFailedError(
                f"invalid 'provider.{namespace}' settings: {exc.message}"
            ) from exc

    return settings
