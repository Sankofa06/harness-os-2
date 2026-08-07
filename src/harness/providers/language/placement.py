"""Placement policy resolution (SPEC/PROVIDER_MATRIX.md "Placement policy").

A pure function over caller-supplied candidates/telemetry so it's testable without
real host monitoring; ANA-002 (host telemetry) will be the eventual signal source.
Policies that need a signal Harness doesn't have yet fail loudly (ValidationFailedError)
rather than silently degrading to an arbitrary choice — capability negotiation, not
fake parity (ADR 0003). "auto" is opt-in only per SPEC/PROVIDER_MATRIX.md and
SPEC/HOSTS_AND_NODE.md.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from harness.core.domain import Host, PlacementPolicy
from harness.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError


class HostSignal(BaseModel):
    host_id: str
    model_loaded: bool = False
    tokens_per_second: float | None = None
    pressure: float | None = None  # 0.0 (idle) .. 1.0 (saturated)
    cost_per_token: float | None = None


def resolve_placement(
    policy: PlacementPolicy,
    candidates: list[Host],
    *,
    automatic_placement_enabled: bool,
    signals: dict[str, HostSignal] | None = None,
) -> Host:
    if not candidates:
        raise NotFoundError("no candidate hosts available for placement")
    if policy == "auto" and not automatic_placement_enabled:
        raise PermissionDeniedError(
            "automatic placement is disabled; enable routing.automatic_placement or "
            "choose an explicit placement policy"
        )

    signals = signals or {}

    if policy == "manual":
        # The caller has already narrowed candidates to the chosen host(s); no
        # policy-driven ranking applies.
        return candidates[0]

    if policy in ("auto", "prefer-loaded"):
        # Full auto-scheduling is host-telemetry-driven work tracked separately
        # (ANA-002); until then "auto" uses the same loaded-host preference as the
        # explicit "prefer-loaded" policy rather than pretending to optimize further.
        loaded = _loaded_candidates(candidates, signals)
        return loaded[0] if loaded else candidates[0]

    if policy == "prefer-local":
        local = [h for h in candidates if h.kind == "local"]
        return local[0] if local else candidates[0]

    if policy == "prefer-fastest":
        return _best_by_signal(candidates, signals, "tokens_per_second", pick=max, policy=policy)

    if policy == "prefer-lowest-pressure":
        return _best_by_signal(candidates, signals, "pressure", pick=min, policy=policy)

    if policy == "prefer-lowest-cost":
        return _best_by_signal(candidates, signals, "cost_per_token", pick=min, policy=policy)

    raise ValueError(f"unknown placement policy: {policy}")


def _loaded_candidates(candidates: list[Host], signals: dict[str, HostSignal]) -> list[Host]:
    return [h for h in candidates if signals.get(h.id, HostSignal(host_id=h.id)).model_loaded]


def _best_by_signal(
    candidates: list[Host],
    signals: dict[str, HostSignal],
    attr: str,
    *,
    pick: Callable[..., tuple[float, Host]],
    policy: str,
) -> Host:
    scored = [
        (getattr(signals[h.id], attr), h)
        for h in candidates
        if h.id in signals and getattr(signals[h.id], attr) is not None
    ]
    if not scored:
        raise ValidationFailedError(f"{policy} placement requires host telemetry for a candidate")
    return pick(scored, key=lambda pair: pair[0])[1]
