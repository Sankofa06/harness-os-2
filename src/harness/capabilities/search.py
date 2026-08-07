"""`capabilities.search`: discover native-tool and MCP-tool capabilities by
keyword (MCP-002, SPEC/MCP_SKILLS_TOOLS.md) without ever loading a full JSON
Schema — only the same compact shape MCP-001's tool index already keeps (name,
one-line description, estimated schema tokens, trust class). Full schemas are
fetched separately via `tools.describe` (`harness.capabilities.activation`),
which is also what "activates" a candidate for that session's context.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from harness.context.tokens import HeuristicEstimator
from harness.core.domain import PermissionClass
from harness.persistence.repos_mcp import McpIndexRepo
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry

_estimator = HeuristicEstimator()

# Meta-tools are already always advertised via the compiler's BASE_PROTOCOL;
# surfacing them as search results for themselves would be circular.
_EXCLUDED_NATIVE_TOOLS = frozenset({"capabilities.search", "tools.describe"})

CAPABILITIES_SEARCH_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
    "additionalProperties": False,
}


class CapabilityCandidate(BaseModel):
    kind: Literal["native_tool", "mcp_tool"]
    ref: str
    name: str
    description: str
    estimated_schema_tokens: int
    trust_class: PermissionClass


def _matches(query_terms: list[str], *fields: str) -> bool:
    haystack = " ".join(fields).lower()
    return all(term in haystack for term in query_terms)


async def search_capabilities(
    query: str, tools: ToolRegistry, mcp_index: McpIndexRepo
) -> list[CapabilityCandidate]:
    """Plain case-insensitive substring matching against name + description —
    no ranking model, consistent with the rest of this codebase's rule of
    declaring exactly the capability that's real rather than approximating a
    fancier one. An empty query matches everything (browse-all).
    """
    terms = [t for t in query.lower().split() if t]
    candidates: list[CapabilityCandidate] = []

    for tool in tools.list():
        if tool.name in _EXCLUDED_NATIVE_TOOLS:
            continue
        if terms and not _matches(terms, tool.name, tool.description):
            continue
        candidates.append(
            CapabilityCandidate(
                kind="native_tool",
                ref=tool.name,
                name=tool.name,
                description=tool.description,
                estimated_schema_tokens=_estimator.estimate(str(tool.parameters_schema)),
                trust_class=tool.permission_class,
            )
        )

    for entry in await mcp_index.list():
        if terms and not _matches(terms, entry.tool_name, entry.description):
            continue
        candidates.append(
            CapabilityCandidate(
                kind="mcp_tool",
                ref=entry.id,
                name=entry.tool_name,
                description=entry.description,
                estimated_schema_tokens=entry.estimated_schema_tokens,
                trust_class=entry.trust_class,
            )
        )

    return candidates


def register_capabilities_search_tool(registry: ToolRegistry, mcp_index: McpIndexRepo) -> None:
    async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        candidates = await search_capabilities(str(arguments["query"]), registry, mcp_index)
        return {"candidates": [c.model_dump() for c in candidates]}

    registry.register(
        ToolDefinition(
            name="capabilities.search",
            description="Search available tool and MCP capabilities by keyword; returns "
            "compact candidates (name, description, estimated schema tokens, trust class) "
            "without loading full schemas. Follow up with tools.describe to activate one.",
            parameters_schema=CAPABILITIES_SEARCH_PARAMETERS_SCHEMA,
            permission_class="read",
            handler=handler,
        )
    )
