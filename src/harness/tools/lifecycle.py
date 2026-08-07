"""Tool execution lifecycle (TOOL-001, SPEC/MCP_SKILLS_TOOLS.md):

    validate -> permission -> approve -> execute -> capture -> artifact -> events
    -> compact result

Artifact creation (step 7) is a no-op hook until ART-001 lands — every other step
is real and persisted. "approve" (step 4) resolves through `PermissionResolver`;
until PERM-001 replaces the default `AllowAllResolver`, "ask" and "deny" are
reachable code paths with no built-in caller producing them yet.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from harness.core.domain import ToolRun
from harness.core.errors import ValidationFailedError
from harness.core.ids import new_id
from harness.events.bus import EventBus
from harness.events.model import Event, EventResource
from harness.persistence.repos_tools import ToolRunRepo
from harness.tools.permissions import PermissionResolver
from harness.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        runs: ToolRunRepo,
        bus: EventBus,
        permissions: PermissionResolver,
    ) -> None:
        self._registry = registry
        self._runs = runs
        self._bus = bus
        self._permissions = permissions

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        workspace_id: str | None = None,
        session_id: str | None = None,
    ) -> ToolRun:
        tool = self._registry.get(tool_name)  # raises NotFoundError if unregistered

        try:
            jsonschema.validate(arguments, tool.parameters_schema)
        except jsonschema.ValidationError as exc:
            raise ValidationFailedError(
                f"invalid arguments for tool {tool_name}: {exc.message}"
            ) from exc

        run = await self._runs.create(
            ToolRun(
                id=new_id("trun"),
                tool_name=tool_name,
                arguments=arguments,
                permission_class=tool.permission_class,
                workspace_id=workspace_id,
                session_id=session_id,
            )
        )
        await self._emit(run, "tool.requested", {"arguments": arguments})

        decision = await self._permissions.resolve(tool.permission_class)
        if decision == "deny":
            run = await self._runs.set_status(run.id, "denied")
            await self._emit(run, "tool.denied", {})
            return run
        if decision == "ask":
            run = await self._runs.set_status(run.id, "pending_approval")
            await self._emit(run, "tool.pending_approval", {})
            return run

        run = await self._runs.set_status(run.id, "running")
        await self._emit(run, "tool.started", {})
        try:
            result = await tool.handler(arguments)
        except Exception as exc:
            run = await self._runs.set_status(run.id, "failed", error=str(exc))
            await self._emit(run, "tool.failed", {"error": str(exc)})
            return run

        run = await self._runs.set_status(run.id, "succeeded", result=result)
        await self._emit(run, "tool.succeeded", {"result": result})
        return run

    async def _emit(self, run: ToolRun, event_type: str, payload: dict[str, Any]) -> None:
        await self._bus.publish(
            Event(
                type=event_type,
                resource=EventResource(type="tool_run", id=run.id),
                context={"tool_run_id": run.id, "tool_name": run.tool_name},
                payload=payload,
            )
        )
