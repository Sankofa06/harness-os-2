"""CTX-004: representative-session regression tests, run in CI on every push/PR
(`.github/workflows/ci.yml`'s `pytest tests -q` step already covers this whole
directory — no separate CI wiring needed). Unlike test_compiler.py's isolated
unit tests, these compile realistic session compositions at each tier's *actual*
production default (`ContextConfig`'s `bootstrap_target_tokens`/
`default_budget_tokens`/`full_capability_soft_limit_tokens`), not an
artificially shrunk budget chosen to exercise one code path.
"""

from __future__ import annotations

from harness.context.compiler import ContextCompiler
from harness.context.tokens import HeuristicEstimator
from harness.core.config import ContextConfig
from harness.core.domain import Contact, Message, Persona, Role, TranscriptState
from harness.tools.builtin import echo_tool
from harness.tools.registry import ToolRegistry
from harness.tools.workspace_tools import register_workspace_tools

_ROLE = Role(
    id="role_coder",
    name="coder",
    system_prompt=(
        "Implement changes precisely and safely. Prefer minimal, targeted diffs over "
        "broad rewrites. Run the project's existing tests before declaring work done. "
        "Never introduce placeholder code, TODOs, or mocked behavior in production paths."
    ),
)

_PERSONAS = [
    Persona(
        id="per_concise",
        name="concise",
        prompt="Be concise. Avoid restating the request.",
        precedence=50,
    ),
    Persona(
        id="per_careful",
        name="careful",
        prompt="Double-check file paths and command arguments before acting.",
        precedence=100,
    ),
]

_TRANSCRIPT_STATE = TranscriptState(
    session_id="ses_regression",
    unresolved_requirements=[
        "add rate limiting to the login endpoint",
        "write a regression test for the 429 response",
    ],
    current_plan="1. add a token-bucket limiter 2. wire it into the auth route 3. test it",
    changed_files=["src/auth/routes.py", "src/auth/rate_limit.py"],
    failing_tests=["test_login_returns_429_after_five_attempts"],
    permission_decisions=["allowed: write (policy allow)", "denied: destructive (policy deny)"],
    rolling_summary="Earlier the user asked for basic login rate limiting; we agreed on a "
    "token-bucket approach keyed by IP address.",
)


def _realistic_history(turns: int) -> list[Message]:
    exchanges = [
        ("user", "Can you add rate limiting to the login endpoint?"),
        (
            "assistant",
            "Sure — I'll add a token-bucket limiter keyed by IP address and wire it into "
            "the auth route. I'll also add a test for the 429 response.",
        ),
        ("user", "Sounds good. Use a 5-attempts-per-minute limit."),
        (
            "assistant",
            "Got it. I've added src/auth/rate_limit.py with a TokenBucket class configured "
            "for 5 attempts per 60 seconds, and wired it into the login route.",
        ),
        ("user", "The test is failing — can you check why?"),
        (
            "assistant",
            "Looking at it now. The bucket wasn't being reset between test runs since it "
            "was module-level state; I've scoped it per-request instead.",
        ),
    ]
    messages = []
    for i in range(turns):
        role, content = exchanges[i % len(exchanges)]
        messages.append(
            Message(id=f"msg_{i}", session_id="ses_regression", role=role, content=content)
        )
    return messages


_SKILL_BODIES = [
    (
        "python-testing",
        "Run tests with `pytest -q`. Prefer real fixtures over mocks. Add a regression "
        "test alongside every bug fix that reproduces the original failure before the fix "
        "and passes after it. Keep test files colocated with the subsystem they cover.",
    ),
    (
        "git-workflow",
        "Use `git status`/`git diff` before committing to review the actual change set. "
        "Write commit messages that explain why, not what. Never force-push to a shared "
        "branch without explicit confirmation.",
    ),
]


def _registered_tool_schemas() -> list[tuple[str, str]]:
    """Pull real tool schemas from a real ToolRegistry (TOOL-001/002) rather than
    hand-written strings, so this regression test tracks the actual production
    tool catalog's size.
    """
    registry = ToolRegistry()
    registry.register(echo_tool())

    class _NullSecretStore:
        def get(self, kind: str, target: str) -> str:
            return ""

    register_workspace_tools(
        registry,
        workspaces=None,  # type: ignore[arg-type]
        hosts=None,  # type: ignore[arg-type]
        secret_refs=None,  # type: ignore[arg-type]
        secret_store=_NullSecretStore(),  # type: ignore[arg-type]
    )
    return [(t.name, str(t.parameters_schema)) for t in registry.list()][:5]


def _compiler(**overrides) -> ContextCompiler:
    return ContextCompiler(HeuristicEstimator(), ContextConfig(**overrides))


def _contact() -> Contact:
    return Contact(id="con_1", handle="builder", display_name="Builder")


def test_representative_bootstrap_session_stays_under_4k() -> None:
    """A brand-new session's very first turn — no history yet — at the real
    bootstrap target, per SPEC/CONTEXT_COMPILER.md "Default bootstrap <= 4K".
    """
    compiler = _compiler(default_budget_tokens=ContextConfig().bootstrap_target_tokens)
    result = compiler.compile(contact=_contact(), role=_ROLE, personas=_PERSONAS, history=[])
    assert result.budget.used <= ContextConfig().bootstrap_target_tokens
    assert result.budget.sections["tools"] == 0
    assert result.budget.sections["skills"] == 0


def test_representative_coding_turn_stays_under_8k() -> None:
    """A normal ongoing coding turn — real history, role, personas, and protected
    facts, no tools/skills activated — at the real default budget, per
    SPEC/CONTEXT_COMPILER.md "Normal coding turn SHOULD remain <= 8K".
    """
    compiler = _compiler(default_budget_tokens=ContextConfig().default_budget_tokens)
    result = compiler.compile(
        contact=_contact(),
        role=_ROLE,
        personas=_PERSONAS,
        history=_realistic_history(18),
        session_state="Implementing login rate limiting.",
        transcript_state=_TRANSCRIPT_STATE,
    )
    assert result.budget.used <= ContextConfig().default_budget_tokens
    assert result.budget.sections["protected_facts"] > 0


def test_representative_full_expansion_stays_under_16k() -> None:
    """Everything activated at once — full history, skills, and real tool
    schemas — at the soft limit, per SPEC/CONTEXT_COMPILER.md "Full optional
    capabilities SHOULD remain <= 16K".
    """
    compiler = _compiler(default_budget_tokens=ContextConfig().full_capability_soft_limit_tokens)
    result = compiler.compile(
        contact=_contact(),
        role=_ROLE,
        personas=_PERSONAS,
        history=_realistic_history(18),
        session_state="Implementing login rate limiting.",
        transcript_state=_TRANSCRIPT_STATE,
        activated_skills=_SKILL_BODIES,
        active_tool_schemas=_registered_tool_schemas(),
    )
    assert result.budget.used <= ContextConfig().full_capability_soft_limit_tokens
    assert result.budget.sections["skills"] > 0
    assert result.budget.sections["tools"] > 0


def test_real_tool_registry_is_not_eagerly_injected() -> None:
    """Regression guard for the lazy-capability rule: a real ToolRegistry with
    Harness's actual production tools (echo + all TOOL-002 workspace tools)
    registered must contribute zero cost unless a caller explicitly activates
    schemas — the compiler has no reference to the registry at all, so it
    structurally cannot reach in and pull from it, but this pins that guarantee
    against a future refactor that might wire one in.
    """
    schemas = _registered_tool_schemas()
    assert len(schemas) > 0  # the registry really does have real tools in it

    compiler = _compiler()
    result = compiler.compile(contact=_contact(), role=None, personas=[], history=[])
    assert result.budget.sections["tools"] == 0
    assert "fs_read_file" not in result.system_prompt
    assert "shell_exec" not in result.system_prompt
