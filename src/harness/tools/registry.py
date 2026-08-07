"""In-memory registry of native tools (TOOL-001).

Mirrors `providers.language.registry.ProviderRegistry`'s shape: a process-local
lookup the API and the agent runtime both read from, kept separate from any
persisted state (ToolRun history lives in `ToolRunRepo`).
"""

from __future__ import annotations

from harness.core.errors import ConflictError, NotFoundError
from harness.tools.base import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ConflictError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise NotFoundError(f"tool not found: {name}") from None

    def list(self) -> list[ToolDefinition]:
        return sorted(self._tools.values(), key=lambda t: t.name)
