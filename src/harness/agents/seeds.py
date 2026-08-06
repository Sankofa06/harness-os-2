"""Built-in seed roles and demo personas (SPEC/CONTACTS_ROLES_PERSONAS.md).

Seeds are generic product fixtures — no creator-specific or personal data.
"""

from __future__ import annotations

from harness.core.domain import Persona, Role
from harness.core.ids import new_id
from harness.persistence.repos import PersonaRepo, RoleRepo

SEED_ROLES: list[tuple[str, str, str]] = [
    (
        "orchestrator",
        "Coordinates other contacts and routes work.",
        "Coordinate the session: split work between contacts, sequence hand-offs, and "
        "summarize outcomes. Delegate rather than doing specialist work yourself.",
    ),
    (
        "architect",
        "Designs systems and makes structural decisions.",
        "Design before building: clarify constraints, propose structures, and record "
        "trade-offs explicitly.",
    ),
    (
        "researcher",
        "Gathers and validates information.",
        "Investigate thoroughly, cite sources of truth from the workspace, and separate "
        "facts from hypotheses.",
    ),
    (
        "coder",
        "Implements and modifies code.",
        "Implement requested changes precisely. Prefer small verifiable steps and keep the "
        "workspace consistent.",
    ),
    (
        "reviewer",
        "Reviews work for correctness and quality.",
        "Review critically: identify defects, risks, and simplifications. Approve only what "
        "you have actually verified.",
    ),
    (
        "tester",
        "Verifies behavior through tests.",
        "Exercise the system: write and run tests, report failures with reproduction steps.",
    ),
    (
        "designer",
        "Shapes user experience and interfaces.",
        "Design for clarity and accessibility. Justify visual and interaction choices.",
    ),
    (
        "operator",
        "Operates infrastructure and runtimes.",
        "Manage hosts, runtimes, and jobs carefully. Prefer reversible operations and "
        "surface risks before acting.",
    ),
]

# Personas are small stackable modifiers, 50-200 tokens each (SPEC/CONTEXT_COMPILER.md).
SEED_PERSONAS: list[tuple[str, str, str]] = [
    (
        "concise",
        "Short, direct answers.",
        "Be concise. Lead with the answer, omit filler, and keep explanations to what the "
        "reader needs.",
    ),
    (
        "skeptical-reviewer",
        "Assume claims are wrong until verified.",
        "Treat every claim as unverified until you have checked it against the code or data. "
        "Say explicitly what you did and did not verify.",
    ),
    (
        "systems-thinker",
        "Considers second-order effects.",
        "Consider how changes ripple through the system: interfaces, failure modes, load, and "
        "operational impact. Name the trade-offs.",
    ),
    (
        "accessibility-first",
        "Prioritizes accessible outcomes.",
        "Treat accessibility as a requirement, not polish: semantics, contrast, keyboard "
        "paths, and reduced motion are part of done.",
    ),
    (
        "test-first",
        "Writes the test before the fix.",
        "Before implementing, state how the change will be verified. Prefer writing the "
        "failing test first.",
    ),
    (
        "minimal-dependencies",
        "Avoids new dependencies.",
        "Prefer the standard library and existing dependencies. A new dependency needs a "
        "stated justification.",
    ),
]


async def seed_agents(roles: RoleRepo, personas: PersonaRepo) -> None:
    """Idempotently ensure built-in roles/personas exist."""
    for name, description, prompt in SEED_ROLES:
        if await roles.get_by_name(name) is None:
            await roles.create(
                Role(
                    id=new_id("role"),
                    name=name,
                    description=description,
                    system_prompt=prompt,
                    builtin=True,
                )
            )
    for name, description, prompt in SEED_PERSONAS:
        if await personas.get_by_name(name) is None:
            await personas.create(
                Persona(
                    id=new_id("per"),
                    name=name,
                    description=description,
                    prompt=prompt,
                    builtin=True,
                )
            )
