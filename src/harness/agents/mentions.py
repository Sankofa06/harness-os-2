"""Mention parsing per SPEC/CONTACTS_ROLES_PERSONAS.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_MENTION = re.compile(r"(?<![\w@])@([a-zA-Z0-9][a-zA-Z0-9_-]*)")


@dataclass
class MentionResult:
    """Handles in order of first mention, de-duplicated. ``everyone`` flags ``@everyone``."""

    handles: list[str] = field(default_factory=list)
    everyone: bool = False


def parse_mentions(text: str) -> MentionResult:
    result = MentionResult()
    seen: set[str] = set()
    for match in _MENTION.finditer(text):
        handle = match.group(1).lower()
        if handle == "everyone":
            result.everyone = True
            continue
        if handle not in seen:
            seen.add(handle)
            result.handles.append(handle)
    return result
