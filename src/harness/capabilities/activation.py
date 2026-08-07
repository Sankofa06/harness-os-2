"""`tools.describe`: fetch a capability's full JSON Schema and mark it activated
for the calling session's subsequent context compiles (MCP-002) — the
"activation" the DoD's "Schema loads only when activated" refers to. Distinct
from MCP-001's `GET /mcp/tools/{entry_id}/schema`, which is the same lazy-fetch
operation via plain REST rather than through the model-facing tool-call path.
"""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import CapabilityKind
from harness.core.errors import NotFoundError
from harness.persistence.repos_capabilities import SessionCapabilityRepo
from harness.persistence.repos_mcp import McpIndexRepo
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry

TOOLS_DESCRIBE_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "kind": {"type": "string", "enum": ["native_tool", "mcp_tool"]},
        "ref": {"type": "string"},
    },
    "required": ["session_id", "kind", "ref"],
    "additionalProperties": False,
}


def register_tools_describe_tool(
    registry: ToolRegistry,
    tools: ToolRegistry,
    mcp_index: McpIndexRepo,
    session_capabilities: SessionCapabilityRepo,
) -> None:
    async def describe(arguments: dict[str, Any]) -> dict[str, Any]:
        session_id = arguments["session_id"]
        kind: CapabilityKind = arguments["kind"]
        ref = arguments["ref"]

        if kind == "mcp_tool":
            entry = await mcp_index.get(ref)
            name = entry.tool_name
            description = entry.description
            schema = await mcp_index.get_schema(ref)
        else:
            tool = tools.get(ref)  # raises NotFoundError if unknown
            name = tool.name
            description = tool.description
            schema = tool.parameters_schema

        await session_capabilities.activate(session_id, kind, ref)
        return {"name": name, "description": description, "schema": schema}

    registry.register(
        ToolDefinition(
            name="tools.describe",
            description="Fetch a tool or MCP tool's full JSON Schema by the ref returned "
            "from capabilities.search, and activate it — its schema is included in this "
            "session's context from the next turn on.",
            parameters_schema=TOOLS_DESCRIBE_PARAMETERS_SCHEMA,
            permission_class="read",
            handler=describe,
        )
    )


async def resolve_active_tool_schemas(
    session_id: str,
    session_capabilities: SessionCapabilityRepo,
    tools: ToolRegistry,
    mcp_index: McpIndexRepo,
) -> list[tuple[str, str]]:
    """What MCP-002 hands the Context Compiler's `active_tool_schemas` for a
    session's next compile: one (name, schema) pair per capability that session
    has activated via `tools.describe`, resolved fresh from its current source
    — a tool removed, or an MCP server re-indexed, since activation is silently
    skipped rather than raising mid-compile.
    """
    resolved: list[tuple[str, str]] = []
    for capability in await session_capabilities.list_for_session(session_id):
        try:
            if capability.kind == "mcp_tool":
                entry = await mcp_index.get(capability.ref)
                schema = await mcp_index.get_schema(capability.ref)
                resolved.append((entry.tool_name, json.dumps(schema)))
            else:
                tool = tools.get(capability.ref)
                resolved.append((tool.name, json.dumps(tool.parameters_schema)))
        except NotFoundError:
            continue
    return resolved
