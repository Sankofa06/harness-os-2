"""Context Compiler — assembles prompts within an explicit token budget.

Implements the layer order of SPEC/CONTEXT_COMPILER.md. Only the layers a turn
actually needs contribute tokens; tools/skills/MCP schemas join the compile only
after explicit activation (lazy capability mechanism). The always-visible surface
is the tiny meta-tool list below.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from harness.context.tokens import TokenEstimator
from harness.core.config import ContextConfig
from harness.core.domain import Contact, Message, Persona, Role

# Immutable minimal Harness protocol (layer 1). Deliberately terse: context is budgeted.
BASE_PROTOCOL = """\
You are a Harness OS Contact: a named agent with a stable identity, collaborating in a \
shared session. Address the user's request directly. Mentions like @handle refer to other \
Contacts. Capabilities are lazy: request what you need instead of assuming tools exist.
Meta-capabilities available on request: capabilities.search, skills.activate, \
tools.describe, artifacts.get, agents.delegate. Reference artifacts as artifact://<id> \
instead of inlining large content."""


class BudgetReport(BaseModel):
    max: int
    used: int
    estimator: str
    sections: dict[str, int] = Field(default_factory=dict)


class CompiledContext(BaseModel):
    system_prompt: str
    messages: list[dict[str, str]]
    budget: BudgetReport


class ContextCompiler:
    def __init__(self, estimator: TokenEstimator, config: ContextConfig) -> None:
        self._estimator = estimator
        self._config = config

    def compile(
        self,
        *,
        contact: Contact,
        role: Role | None,
        personas: list[Persona],
        history: list[Message],
        session_state: str = "",
        activated_skills: list[tuple[str, str]] | None = None,
        active_tool_schemas: list[tuple[str, str]] | None = None,
    ) -> CompiledContext:
        est = self._estimator.estimate
        budget_max = self._config.default_budget_tokens
        sections: dict[str, int] = {}

        # Layer 1 — immutable protocol.
        system_parts = [BASE_PROTOCOL, f"You are @{contact.handle} ({contact.display_name})."]
        sections["base"] = sum(est(p) for p in system_parts)

        # Layer 2 — active role.
        if role is not None and role.system_prompt:
            role_text = f"Role: {role.name}. {role.system_prompt}"
            system_parts.append(role_text)
            sections["role"] = est(role_text)
        else:
            sections["role"] = 0

        # Layer 3 — persona modifiers, deterministic precedence order (lower wins conflicts,
        # applied last so it overrides earlier statements).
        persona_texts = [
            p.prompt for p in sorted(personas, key=lambda p: (-p.precedence, p.name)) if p.prompt
        ]
        system_parts.extend(persona_texts)
        sections["personas"] = sum(est(t) for t in persona_texts)

        # Layer 4 — session objective/state summary.
        if session_state:
            state_text = f"Session state: {session_state}"
            system_parts.append(state_text)
            sections["session_state"] = est(state_text)
        else:
            sections["session_state"] = 0

        # Layers 7-9 - activated skills and tool/MCP schemas (lazy; empty by default).
        skills = activated_skills or []
        skill_texts = [f"Skill {name}:\n{body}" for name, body in skills]
        system_parts.extend(skill_texts)
        sections["skills"] = sum(est(t) for t in skill_texts)

        tools = active_tool_schemas or []
        tool_texts = [f"Tool {name}: {schema}" for name, schema in tools]
        system_parts.extend(tool_texts)
        sections["tools"] = sum(est(t) for t in tool_texts)

        # Layers 6/10/11 (workspace facts, artifact excerpts, task memory) join the
        # compile when those subsystems provide content; they cost zero until then.
        sections["workspace"] = 0
        sections["artifacts"] = 0

        system_prompt = "\n\n".join(system_parts)

        # Layer 5 — recent conversation within the history budget.
        overhead = sum(sections.values())
        history_budget = min(
            int(budget_max * self._config.history_fraction),
            max(0, budget_max - overhead),
        )
        included: list[Message] = []
        history_used = 0
        for message in reversed(history):
            cost = est(message.content) + 4  # small per-message envelope overhead
            if history_used + cost > history_budget and included:
                break
            if history_used + cost > history_budget:
                break
            included.append(message)
            history_used += cost
        included.reverse()
        sections["history"] = history_used

        messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in included
        ]

        return CompiledContext(
            system_prompt=system_prompt,
            messages=messages,
            budget=BudgetReport(
                max=budget_max,
                used=overhead + history_used,
                estimator=self._estimator.name,
                sections=sections,
            ),
        )
