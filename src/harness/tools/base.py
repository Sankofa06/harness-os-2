"""Native tool contracts (TOOL-001, SPEC/MCP_SKILLS_TOOLS.md).

A Tool is a capability a running agent can invoke: a typed JSON-Schema parameter
contract plus a handler. Every tool declares a `PermissionClass` (PERM-001) up
front, so the lifecycle can resolve a policy before ever calling the handler.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from harness.core.domain import PermissionClass

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    permission_class: PermissionClass
    handler: ToolHandler
    workspace_scoped: bool = False
