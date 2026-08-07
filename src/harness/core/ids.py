"""Opaque, prefixed, time-sortable IDs (ULID-style) per SPEC/DATA_MODEL.md."""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Known entity prefixes. Adapters and new subsystems register additions here.
PREFIXES: frozenset[str] = frozenset(
    {
        "host",
        "prov",
        "model",
        "inst",
        "role",
        "per",
        "con",
        "team",
        "ses",
        "msg",
        "run",
        "bnd",
        "tool",
        "trun",
        "mcp",
        "skill",
        "ws",
        "job",
        "art",
        "cre",
        "asset",
        "prof",
        "bench",
        "evt",
        "sec",
        "node",
        "perm",
    }
)


def _encode_base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_id(prefix: str, *, timestamp_ms: int | None = None) -> str:
    """Return a new opaque ID like ``run_01JD3G...`` (26-char ULID body).

    IDs sort lexicographically by creation time within a prefix.
    """
    if prefix not in PREFIXES:
        raise ValueError(f"unknown ID prefix: {prefix!r}")
    ts = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if ts < 0 or ts >= 1 << 48:
        raise ValueError("timestamp out of ULID range")
    rand = int.from_bytes(os.urandom(10))
    return f"{prefix}_{_encode_base32(ts, 10)}{_encode_base32(rand, 16)}"


def is_valid_id(value: str, prefix: str | None = None) -> bool:
    """Check structural validity of an opaque ID, optionally pinning the prefix."""
    head, sep, body = value.partition("_")
    if not sep or len(body) != 26:
        return False
    if prefix is not None and head != prefix:
        return False
    return head in PREFIXES and all(c in _CROCKFORD for c in body)
