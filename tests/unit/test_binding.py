import pytest

from harness.agents.binding import resolve_binding
from harness.core.domain import Binding


def test_system_default_used_when_nothing_else_set() -> None:
    resolved = resolve_binding(system=Binding(provider="fake", model="fake-mini"))
    assert resolved.provider == "fake"
    assert resolved.model == "fake-mini"
    assert resolved.sources["provider"] == "system"


def test_contact_overrides_system() -> None:
    resolved = resolve_binding(
        system=Binding(provider="fake", model="fake-mini"),
        contact=Binding(model="fake-large"),
    )
    assert resolved.model == "fake-large"
    assert resolved.provider == "fake"
    assert resolved.sources["model"] == "contact"
    assert resolved.sources["provider"] == "system"


def test_turn_overrides_everything() -> None:
    resolved = resolve_binding(
        system=Binding(provider="fake", model="fake-mini"),
        contact=Binding(model="fake-large"),
        session=Binding(model="session-model"),
        turn=Binding(model="turn-model"),
    )
    assert resolved.model == "turn-model"
    assert resolved.sources["model"] == "turn"


def test_session_overrides_contact() -> None:
    resolved = resolve_binding(
        system=Binding(provider="fake", model="fake-mini"),
        contact=Binding(model="fake-large"),
        session=Binding(model="session-model"),
    )
    assert resolved.model == "session-model"


def test_settings_deep_merge_across_levels() -> None:
    resolved = resolve_binding(
        system=Binding(
            provider="fake",
            model="fake-mini",
            settings={"common": {"temperature": 0.2}, "provider": {"fake": {"a": 1}}},
        ),
        turn=Binding(settings={"common": {"temperature": 0.9}}),
    )
    assert resolved.settings["common"]["temperature"] == 0.9
    assert resolved.settings["provider"]["fake"]["a"] == 1


def test_missing_system_default_raises() -> None:
    with pytest.raises(ValueError):
        resolve_binding(system=Binding(model="fake-mini"))
