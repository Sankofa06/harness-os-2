"""Binding resolution with the 5-level precedence of SPEC/ARCHITECTURE.md.

turn override > session/contact override > contact default > role default > system default.
Every resolved field records which level supplied it, and the whole result is snapshot
into the run before inference (ADR 0005).
"""

from __future__ import annotations

from typing import Any

from harness.core.domain import Binding, ResolvedBinding

_LEVELS = ["system", "role", "contact", "session", "turn"]
_FIELDS = ["provider", "model", "inference_host", "execution_host", "personas"]


def resolve_binding(
    *,
    system: Binding,
    role: Binding | None = None,
    contact: Binding | None = None,
    session: Binding | None = None,
    turn: Binding | None = None,
) -> ResolvedBinding:
    layers: list[tuple[str, Binding]] = [("system", system)]
    for name, binding in (
        ("role", role),
        ("contact", contact),
        ("session", session),
        ("turn", turn),
    ):
        if binding is not None:
            layers.append((name, binding))

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    settings: dict[str, Any] = {}
    for level_name, binding in layers:
        for field in _FIELDS:
            value = getattr(binding, field)
            if value is not None:
                values[field] = value
                sources[field] = level_name
        if binding.settings:
            settings = _deep_merge(settings, binding.settings)
            sources["settings"] = level_name

    provider = values.get("provider")
    model = values.get("model")
    if provider is None or model is None:
        raise ValueError("system default binding must define provider and model")

    return ResolvedBinding(
        provider=provider,
        model=model,
        inference_host=values.get("inference_host", "local"),
        execution_host=values.get("execution_host", "local"),
        personas=values.get("personas", []),
        settings=settings,
        sources=sources,
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
