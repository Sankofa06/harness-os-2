from typing import Any

import pytest

from harness.events.bus import EventBus
from harness.persistence.repos_tools import ToolRunRepo
from harness.tools.base import ToolDefinition
from harness.tools.lifecycle import ToolExecutor
from harness.tools.permissions import AllowAllResolver, PermissionDecision
from harness.tools.registry import ToolRegistry


class _FixedResolver:
    def __init__(self, decision: PermissionDecision) -> None:
        self._decision = decision

    async def resolve(self, permission_class: str) -> PermissionDecision:
        return self._decision


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
async def test_denied_permission_skips_execution(db, registry: ToolRegistry) -> None:
    executor = ToolExecutor(registry, ToolRunRepo(db), EventBus(), _FixedResolver("deny"))
    run = await executor.execute("add_one", {"value": 41})
    assert run.status == "denied"
    assert run.result is None


@pytest.mark.asyncio
async def test_ask_permission_leaves_run_pending_approval(db, registry: ToolRegistry) -> None:
    executor = ToolExecutor(registry, ToolRunRepo(db), EventBus(), _FixedResolver("ask"))
    run = await executor.execute("add_one", {"value": 41})
    assert run.status == "pending_approval"
    assert run.result is None


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
    assert received == ["tool.requested", "tool.started", "tool.succeeded"]


async def _drain(subscription: Any, out: list[str]) -> None:
    async for event in subscription:
        out.append(event.type)
