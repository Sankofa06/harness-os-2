import pytest

from harness.context.compiler import ContextCompiler
from harness.context.tokens import HeuristicEstimator
from harness.core.config import ContextConfig
from harness.core.domain import Contact, Message, Persona, Role


def _compiler(**overrides) -> ContextCompiler:
    return ContextCompiler(HeuristicEstimator(), ContextConfig(**overrides))


def _contact() -> Contact:
    return Contact(id="con_1", handle="builder", display_name="Builder")


@pytest.mark.parametrize("history_len", [0, 5])
def test_bootstrap_budget_under_4k(history_len: int) -> None:
    compiler = _compiler()
    history = [
        Message(id=f"msg_{i}", session_id="ses_1", role="user", content="hello")
        for i in range(history_len)
    ]
    result = compiler.compile(contact=_contact(), role=None, personas=[], history=history)
    assert result.budget.used <= 4096


def test_no_tools_or_skills_means_zero_cost_sections() -> None:
    compiler = _compiler()
    result = compiler.compile(contact=_contact(), role=None, personas=[], history=[])
    assert result.budget.sections["tools"] == 0
    assert result.budget.sections["skills"] == 0
    assert result.budget.sections["workspace"] == 0
    assert result.budget.sections["artifacts"] == 0


def test_activated_skill_adds_cost_only_when_activated() -> None:
    compiler = _compiler()
    baseline = compiler.compile(contact=_contact(), role=None, personas=[], history=[])
    with_skill = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=[],
        activated_skills=[("swift-development", "Build, debug and test Swift projects.")],
    )
    assert with_skill.budget.sections["skills"] > baseline.budget.sections["skills"]
    assert with_skill.budget.used > baseline.budget.used


def test_persona_and_role_contribute_to_system_prompt() -> None:
    compiler = _compiler()
    role = Role(id="role_1", name="coder", system_prompt="Implement changes precisely.")
    persona = Persona(id="per_1", name="concise", prompt="Be concise.", precedence=50)
    result = compiler.compile(contact=_contact(), role=role, personas=[persona], history=[])
    assert "coder" in result.system_prompt
    assert "Be concise." in result.system_prompt
    assert result.budget.sections["role"] > 0
    assert result.budget.sections["personas"] > 0


def test_history_is_trimmed_to_budget() -> None:
    compiler = _compiler(default_budget_tokens=200, history_fraction=0.5)
    history = [
        Message(id=f"msg_{i}", session_id="ses_1", role="user", content="word " * 40)
        for i in range(20)
    ]
    result = compiler.compile(contact=_contact(), role=None, personas=[], history=history)
    assert len(result.messages) - 1 < len(history)
    assert result.budget.used <= 200


def test_full_expansion_soft_limit() -> None:
    compiler = _compiler(default_budget_tokens=16384)
    tools = [(f"tool_{i}", "x" * 200) for i in range(10)]
    skills = [(f"skill_{i}", "x" * 200) for i in range(5)]
    result = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=[],
        activated_skills=skills,
        active_tool_schemas=tools,
    )
    assert result.budget.used <= 16384
