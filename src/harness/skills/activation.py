"""Skill activation (SKL-001, SPEC/CONTEXT_COMPILER.md "Skill format"):
recording that a session has activated a skill, and resolving a session's
activated skill bodies for the Context Compiler. Exposed two ways — a plain
REST route (`POST /skills/{id}/activate`, SPEC/API_CONTRACT.md) for
UI-driven activation, and the `skills.activate` native meta-tool
(`harness.capabilities`'s siblings `capabilities.search`/`tools.describe`)
for model-driven activation — both call `activate_skill` so there is exactly
one activation code path.
"""

from __future__ import annotations

from typing import Any

from harness.core.domain import Skill
from harness.core.errors import NotFoundError
from harness.persistence.repos_skills import SkillActivationRepo, SkillRepo
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry

SKILLS_ACTIVATE_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "skill_id": {"type": "string"},
    },
    "required": ["session_id", "skill_id"],
    "additionalProperties": False,
}


async def activate_skill(
    session_id: str, skill_id: str, skills: SkillRepo, activations: SkillActivationRepo
) -> Skill:
    skill = await skills.get(skill_id)  # raises NotFoundError if unknown
    await activations.activate(session_id, skill_id)
    return skill


async def resolve_activated_skill_bodies(
    session_id: str, activations: SkillActivationRepo, skills: SkillRepo
) -> list[tuple[str, str]]:
    """What SKL-001 hands the Context Compiler's `activated_skills` for a
    session's next compile: one (name, body) pair per skill that session has
    activated, resolved fresh from its current source — a since-deleted skill
    is silently skipped rather than raising mid-compile, matching MCP-002's
    `resolve_active_tool_schemas`.
    """
    resolved: list[tuple[str, str]] = []
    for activation in await activations.list_for_session(session_id):
        try:
            skill = await skills.get(activation.skill_id)
        except NotFoundError:
            continue
        resolved.append((skill.name, skill.body))
    return resolved


def register_skills_activate_tool(
    registry: ToolRegistry, skills: SkillRepo, activations: SkillActivationRepo
) -> None:
    async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        skill = await activate_skill(
            arguments["session_id"], arguments["skill_id"], skills, activations
        )
        return {"name": skill.name, "description": skill.description, "body": skill.body}

    registry.register(
        ToolDefinition(
            name="skills.activate",
            description="Activate a skill by the id returned from capabilities.search or "
            "GET /skills; its SKILL.md body is included in this session's context from "
            "the next turn on.",
            parameters_schema=SKILLS_ACTIVATE_PARAMETERS_SCHEMA,
            permission_class="read",
            handler=handler,
        )
    )
