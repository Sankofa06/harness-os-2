"""Pluggable token estimation (DECISIONS.md D-006)."""

from __future__ import annotations

from typing import Protocol


class TokenEstimator(Protocol):
    name: str

    def estimate(self, text: str) -> int:
        """Estimated token count for ``text``."""
        ...


class HeuristicEstimator:
    """~1 token per 4 characters, floored at the word count for short/spiky text.

    Calibrated for English prose and code; providers may supply exact tokenizers
    later through the same protocol. Budget regression tests keep headroom margin.
    """

    name = "heuristic-v1"

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        return max(len(text.split()), round(len(text) / 4))
