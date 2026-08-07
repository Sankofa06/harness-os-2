"""A minimal always-registered tool (TOOL-001), mirroring `FakeProvider`'s role for
language providers: the server has at least one real, safe tool to exercise the
lifecycle against with zero external configuration. Real file/shell/git tools
(TOOL-002) are workspace-scoped and depend on PERM-001; this one is neither.
"""

from __future__ import annotations

from typing import Any

from harness.tools.base import ToolDefinition

ECHO_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


async def _echo(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"text": arguments["text"]}


def echo_tool() -> ToolDefinition:
    return ToolDefinition(
        name="echo",
        description="Return the given text unchanged. Used to exercise the tool "
        "lifecycle without touching any external system.",
        parameters_schema=ECHO_PARAMETERS_SCHEMA,
        permission_class="read",
        handler=_echo,
    )
