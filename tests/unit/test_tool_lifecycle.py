from typing import Any, Literal

import pytest

from harness.events.bus import EventBus
from harness.persistence.repos_tools import ToolRunRepo
from harness.tools.base import ToolDefinition
from harness.tools.lifecycle import ToolExecutor
from harness.tools.permissions import AllowAllResolver, PermissionDecision
from harness.tools.registry import ToolRegistry


class _FixedResolver:
    """A resolver whose `resolve()` never returns "ask" — used for the immediate
    allow/deny branches, which never call `await_decision()`.
    """

    def __init__(self, decision: Literal["allow", "deny"]) -> None:
        self._decision: PermissionDecision = decision

    async def resolve(self, permission_class: str, *, run_id: str) -> PermissionDecision:
        return self._decision

    async def await_decision(self, run_id: str) -> Literal["allow", "deny"]:
        raise AssertionError("should not be called when resolve() doesn't return 'ask'")


class _AskThenDecideResolver:
    """Always asks, then resolves to a fixed final outcome — proves the ask flow
    actually blocks on `await_decision()` and resumes correctly either way.
    """

    def __init__(self, final_decision: Literal["allow", "deny"]) -> None:
        self._final_decision = final_decision
        self.awaited_run_ids: list[str] = []

    async def resolve(self, permission_class: str, *, run_id: str) -> PermissionDecision:
        return "ask"

    async def await_decision(self, run_id: str) -> Literal["allow", "deny"]:
        self.awaited_run_ids.append(run_id)
        return self._final_decision


async def _add_one(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"result": arguments["value"] + 1}


def _add_one_tool() -> ToolDefinition:
    return ToolDefinition(
        name="add_one",
        description="add one to a number",
        parameters_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
        permission_class="write",
        handler=_add_one,
    )


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(_add_one_tool())
    return reg


@pytest.mark.asyncio
async def test_allowed_tool_executes_and_persists_result(db, registry: ToolRegistry) -> None:
    executor = ToolExecutor(registry, ToolRunRepo(db), EventBus(), AllowAllResolver())
    run = await executor.execute("add_one", {"value": 41})
    assert run.status == "succeeded"
    assert run.result == {"result": 42}
    assert run.finished_at is not None


@pytest.mark.asyncio
async def test_denied_permission_skips_execution_and_emits_tool_denied(
    db, registry: ToolRegistry
) -> None:
    import asyncio

    bus = EventBus()
    received: list[str] = []
    subscription = bus.subscribe(None)
    drain_task = asyncio.create_task(_drain(subscription, received))

    executor = ToolExecutor(registry, ToolRunRepo(db), bus, _FixedResolver("deny"))
    run = await executor.execute("add_one", {"value": 41})
    await asyncio.sleep(0.05)
    drain_task.cancel()
    subscription.close()

    assert run.status == "denied"
    assert run.result is None
    assert received == ["tool.requested", "tool.denied"]


@pytest.mark.asyncio
async def test_ask_then_approved_executes_the_tool(db, registry: ToolRegistry) -> None:
    import asyncio

    bus = EventBus()
    received: list[str] = []
    subscription = bus.subscribe(None)
    drain_task = asyncio.create_task(_drain(subscription, received))

    resolver = _AskThenDecideResolver("allow")
    executor = ToolExecutor(registry, ToolRunRepo(db), bus, resolver)
    run = await executor.execute("add_one", {"value": 41})
    await asyncio.sleep(0.05)
    drain_task.cancel()
    subscription.close()

    assert run.status == "succeeded"
    assert run.result == {"result": 42}
    assert resolver.awaited_run_ids == [run.id]
    assert received == [
        "tool.requested",
        "tool.approval_required",
        "tool.started",
        "tool.completed",
    ]


@pytest.mark.asyncio
async def test_ask_then_rejected_denies_the_run_without_executing(
    db, registry: ToolRegistry
) -> None:
    import asyncio

    bus = EventBus()
    received: list[str] = []
    subscription = bus.subscribe(None)
    drain_task = asyncio.create_task(_drain(subscription, received))

    resolver = _AskThenDecideResolver("deny")
    executor = ToolExecutor(registry, ToolRunRepo(db), bus, resolver)
    run = await executor.execute("add_one", {"value": 41})
    await asyncio.sleep(0.05)
    drain_task.cancel()
    subscription.close()

    assert run.status == "denied"
    assert run.result is None
    assert resolver.awaited_run_ids == [run.id]
    assert received == ["tool.requested", "tool.approval_required", "tool.denied"]


@pytest.mark.asyncio
async def test_handler_exception_is_captured_as_failed_run(db, registry: ToolRegistry) -> None:
    async def _boom(arguments: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("handler exploded")

    registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
            parameters_schema={"type": "object", "properties": {}},
            permission_class="write",
            handler=_boom,
        )
    )
    executor = ToolExecutor(registry, ToolRunRepo(db), EventBus(), AllowAllResolver())
    run = await executor.execute("boom", {})
    assert run.status == "failed"
    assert run.error is not None and "handler exploded" in run.error


@pytest.mark.asyncio
async def test_invalid_arguments_raise_before_any_run_is_persisted(
    db, registry: ToolRegistry
) -> None:
    from harness.core.errors import ValidationFailedError

    executor = ToolExecutor(registry, ToolRunRepo(db), EventBus(), AllowAllResolver())
    with pytest.raises(ValidationFailedError):
        await executor.execute("add_one", {"value": "not a number"})
    assert await ToolRunRepo(db).list(tool_name="add_one") == []


@pytest.mark.asyncio
async def test_events_emitted_match_lifecycle_outcome(db, registry: ToolRegistry) -> None:
    import asyncio

    bus = EventBus()
    received: list[str] = []
    subscription = bus.subscribe(None)
    drain_task = asyncio.create_task(_drain(subscription, received))

    executor = ToolExecutor(registry, ToolRunRepo(db), bus, AllowAllResolver())
    await executor.execute("add_one", {"value": 1})
    await asyncio.sleep(0.05)

    drain_task.cancel()
    subscription.close()
    assert received == ["tool.requested", "tool.started", "tool.completed"]


async def _drain(subscription: Any, out: list[str]) -> None:
    async for event in subscription:
        out.append(event.type)
