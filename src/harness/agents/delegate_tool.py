"""`agents.delegate` native tool (AGT-006, SPEC/CONTEXT_COMPILER.md meta-capabilities).

Lets one contact hand a sub-task to another contact already in the same session,
spawning a real Run for them through the same run loop a direct @mention uses —
same binding resolution, same context compilation, same event trail. Blocks until
the delegated run finishes and returns its reply. An orchestrator that wants
parallel plan->review->implement work delegates to multiple contacts via
concurrent `POST /tools/agents.delegate/run` calls; each runs as its own Job
(TOOL-001), so two concurrent delegate calls really do run in parallel — the same
concurrency AGT-007 already relies on for @mention fan-out.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry

if TYPE_CHECKING:
    # Only for the type checker: `core.app` imports this module to register the
    # tool, so importing `Application` back at module load time would cycle.
    # `from __future__ import annotations` already makes every annotation below
    # a string at runtime, so this import never actually executes there.
    from harness.core.app import Application

DELEGATE_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "target_handle": {"type": "string"},
        "message": {"type": "string"},
        "parent_run_id": {"type": "string"},
    },
    "required": ["session_id", "target_handle", "message", "parent_run_id"],
    "additionalProperties": False,
}


def register_delegation_tool(registry: ToolRegistry, app: Application) -> None:
    async def delegate(arguments: dict[str, Any]) -> dict[str, Any]:
        from harness.agents.runloop import run_contact  # avoids a module import cycle

        session_id = arguments["session_id"]
        target_handle = arguments["target_handle"]
        message = arguments["message"]
        parent_run_id = arguments["parent_run_id"]

        await app.sessions.get(session_id)
        parent_run = await app.runs.get(parent_run_id)
        delegator = await app.contacts.get(parent_run.contact_id)
        target = await app.contacts.get_by_handle(target_handle)
        if target is None:
            raise NotFoundError(f"contact not found: {target_handle}")

        # Visible in the shared session transcript, so the delegate's compiled
        # context (and everyone else's, going forward) includes the instruction.
        await app.messages.create(
            session_id, "user", f"[Delegated by @{delegator.handle}] {message}"
        )

        run_id = new_id("run")
        task = asyncio.create_task(
            run_contact(
                app,
                session_id,
                target,
                parent_run.correlation_id or run_id,
                run_id,
                parent_run_id=parent_run_id,
            )
        )
        app.run_registry.register(run_id, session_id, task)
        try:
            outcome = await task
        finally:
            app.run_registry.unregister(run_id, session_id)

        return {
            "run_id": outcome.run_id,
            "contact_handle": outcome.contact_handle,
            "content": outcome.content,
            "status": outcome.status,
        }

    registry.register(
        ToolDefinition(
            name="agents.delegate",
            description="Delegate a sub-task to another contact already in this "
            "session; blocks until they reply.",
            parameters_schema=DELEGATE_PARAMETERS_SCHEMA,
            permission_class="execute",
            handler=delegate,
            workspace_scoped=False,
        )
    )
