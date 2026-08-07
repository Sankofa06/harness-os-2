from harness.context.compiler import ContextCompiler
from harness.context.tokens import HeuristicEstimator
from harness.core.config import ContextConfig
from harness.core.domain import Contact, Message, TranscriptState


def _compiler(**overrides) -> ContextCompiler:
    return ContextCompiler(HeuristicEstimator(), ContextConfig(**overrides))


def _contact() -> Contact:
    return Contact(id="con_1", handle="builder", display_name="Builder")


def _long_history(n: int) -> list[Message]:
    return [
        Message(id=f"msg_{i}", session_id="ses_1", role="user", content="word " * 40)
        for i in range(n)
    ]


def test_protected_facts_survive_a_budget_too_small_for_any_history() -> None:
    # A budget this tiny would normally drop every history message; the protected
    # facts must still appear in the compiled system prompt regardless.
    compiler = _compiler(default_budget_tokens=50, history_fraction=0.1)
    state = TranscriptState(
        session_id="ses_1",
        unresolved_requirements=["ship the login page"],
        current_plan="1. wire auth 2. add tests",
        changed_files=["src/auth.py"],
        failing_tests=["test_login_redirects"],
        permission_decisions=["denied: destructive rm -rf tmp/"],
    )
    result = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=_long_history(30),
        transcript_state=state,
    )
    assert "ship the login page" in result.system_prompt
    assert "1. wire auth 2. add tests" in result.system_prompt
    assert "src/auth.py" in result.system_prompt
    assert "test_login_redirects" in result.system_prompt
    assert "denied: destructive rm -rf tmp/" in result.system_prompt
    assert result.budget.sections["protected_facts"] > 0


def test_no_transcript_state_costs_nothing_and_adds_no_text() -> None:
    compiler = _compiler()
    result = compiler.compile(
        contact=_contact(), role=None, personas=[], history=[], transcript_state=None
    )
    assert result.budget.sections["protected_facts"] == 0
    assert "Protected session facts" not in result.system_prompt


def test_empty_transcript_state_costs_nothing() -> None:
    compiler = _compiler()
    result = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=[],
        transcript_state=TranscriptState(session_id="ses_1"),
    )
    assert result.budget.sections["protected_facts"] == 0


def test_omitted_history_is_noted_rather_than_silently_dropped() -> None:
    compiler = _compiler(default_budget_tokens=200, history_fraction=0.5)
    result = compiler.compile(contact=_contact(), role=None, personas=[], history=_long_history(20))
    assert "omitted for budget" in result.system_prompt


def test_rolling_summary_is_included_verbatim_when_history_is_trimmed() -> None:
    compiler = _compiler(default_budget_tokens=200, history_fraction=0.5)
    state = TranscriptState(
        session_id="ses_1", rolling_summary="User asked for a login page; auth is half done."
    )
    result = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=_long_history(20),
        transcript_state=state,
    )
    assert "User asked for a login page; auth is half done." in result.system_prompt


def test_rolling_summary_omitted_when_nothing_was_trimmed() -> None:
    compiler = _compiler()
    state = TranscriptState(session_id="ses_1", rolling_summary="should not appear")
    result = compiler.compile(
        contact=_contact(),
        role=None,
        personas=[],
        history=[Message(id="msg_1", session_id="ses_1", role="user", content="hi")],
        transcript_state=state,
    )
    assert "should not appear" not in result.system_prompt
