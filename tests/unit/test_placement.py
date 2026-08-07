import pytest

from harness.core.domain import Host
from harness.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from harness.providers.language.placement import HostSignal, resolve_placement


def _host(id_: str, kind: str = "ssh") -> Host:
    return Host(id=id_, display_name=id_, kind=kind)


def test_manual_returns_first_candidate() -> None:
    hosts = [_host("host_a")]
    assert resolve_placement("manual", hosts, automatic_placement_enabled=False).id == "host_a"


def test_no_candidates_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        resolve_placement("manual", [], automatic_placement_enabled=False)


def test_auto_rejected_when_disabled() -> None:
    with pytest.raises(PermissionDeniedError):
        resolve_placement("auto", [_host("host_a")], automatic_placement_enabled=False)


def test_auto_allowed_when_enabled() -> None:
    result = resolve_placement("auto", [_host("host_a")], automatic_placement_enabled=True)
    assert result.id == "host_a"


def test_prefer_loaded_picks_loaded_host() -> None:
    hosts = [_host("host_a"), _host("host_b")]
    signals = {"host_b": HostSignal(host_id="host_b", model_loaded=True)}
    result = resolve_placement(
        "prefer-loaded", hosts, automatic_placement_enabled=False, signals=signals
    )
    assert result.id == "host_b"


def test_prefer_loaded_falls_back_to_first_when_none_loaded() -> None:
    hosts = [_host("host_a"), _host("host_b")]
    result = resolve_placement("prefer-loaded", hosts, automatic_placement_enabled=False)
    assert result.id == "host_a"


def test_prefer_local_picks_local_kind() -> None:
    hosts = [_host("host_a", kind="ssh"), _host("host_b", kind="local")]
    result = resolve_placement("prefer-local", hosts, automatic_placement_enabled=False)
    assert result.id == "host_b"


def test_prefer_fastest_picks_highest_tokens_per_second() -> None:
    hosts = [_host("host_a"), _host("host_b")]
    signals = {
        "host_a": HostSignal(host_id="host_a", tokens_per_second=10),
        "host_b": HostSignal(host_id="host_b", tokens_per_second=42),
    }
    result = resolve_placement(
        "prefer-fastest", hosts, automatic_placement_enabled=False, signals=signals
    )
    assert result.id == "host_b"


def test_prefer_fastest_without_telemetry_raises() -> None:
    with pytest.raises(ValidationFailedError):
        resolve_placement("prefer-fastest", [_host("host_a")], automatic_placement_enabled=False)


def test_prefer_lowest_pressure_picks_least_loaded() -> None:
    hosts = [_host("host_a"), _host("host_b")]
    signals = {
        "host_a": HostSignal(host_id="host_a", pressure=0.9),
        "host_b": HostSignal(host_id="host_b", pressure=0.1),
    }
    result = resolve_placement(
        "prefer-lowest-pressure", hosts, automatic_placement_enabled=False, signals=signals
    )
    assert result.id == "host_b"


def test_prefer_lowest_cost_picks_cheapest() -> None:
    hosts = [_host("host_a"), _host("host_b")]
    signals = {
        "host_a": HostSignal(host_id="host_a", cost_per_token=0.002),
        "host_b": HostSignal(host_id="host_b", cost_per_token=0.0005),
    }
    result = resolve_placement(
        "prefer-lowest-cost", hosts, automatic_placement_enabled=False, signals=signals
    )
    assert result.id == "host_b"
