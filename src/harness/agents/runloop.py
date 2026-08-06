"""Run loop: message -> mention routing -> per-contact run -> compile -> stream -> persist.

Implements SPEC/ARCHITECTURE.md's event-driven rule: every state transition (run.started,
run.binding_snapshot, context.compiled, inference.*, run.failed) is published before the
API layer touches the database directly, keeping the WebUI/TUI as pure event/REST clients.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from harness.agents.binding import resolve_binding
from harness.agents.mentions import parse_mentions
from harness.core.app import Application
from harness.core.domain import Contact, MessageRole, Run, RunMetrics
from harness.core.ids import new_id
from harness.events.model import Event, EventResource
from harness.providers.language.base import ChatMessage, ChatRequest


@dataclass
class RunOutcome:
    run_id: str
    contact_handle: str
    content: str
    status: str


async def route_targets(app: Application, session_id: str, text: str) -> list[Contact]:
    """Resolve mentioned handles/@team/@everyone to Contacts for this session."""
    mentions = parse_mentions(text)
    targets: dict[str, Contact] = {}

    if mentions.everyone:
        session = await app.sessions.get(session_id)
        for contact_id in session.contact_ids:
            contact = await app.contacts.get(contact_id)
            targets[contact.id] = contact
    else:
        for handle in mentions.handles:
            mentioned = await app.contacts.get_by_handle(handle)
            if mentioned is not None:
                targets[mentioned.id] = mentioned
                continue
            team = await app.teams.get_by_handle(handle)
            if team is not None:
                for contact_id in team.member_ids:
                    member = await app.contacts.get(contact_id)
                    targets[member.id] = member

    if not targets:
        # No explicit mention: route to every contact already in the session
        # (SPEC/CONTACTS_ROLES_PERSONAS.md — explicit mention bypasses the orchestrator;
        # its absence falls back to the session's standing members).
        session = await app.sessions.get(session_id)
        for contact_id in session.contact_ids:
            contact = await app.contacts.get(contact_id)
            targets[contact.id] = contact

    return list(targets.values())


async def handle_user_message(
    app: Application, session_id: str, text: str, *, correlation_id: str | None = None
) -> list[RunOutcome]:
    correlation_id = correlation_id or new_id("run")
    await app.messages.create(session_id, "user", text)

    targets = await route_targets(app, session_id, text)
    outcomes = []
    for contact in targets:
        outcome = await _run_contact(app, session_id, contact, correlation_id)
        outcomes.append(outcome)
    return outcomes


async def _run_contact(
    app: Application, session_id: str, contact: Contact, correlation_id: str
) -> RunOutcome:
    run = await app.runs.create(
        Run(
            id=new_id("run"),
            session_id=session_id,
            contact_id=contact.id,
            correlation_id=correlation_id,
        )
    )
    resource = EventResource(type="run", id=run.id)
    context = {"session_id": session_id}

    await app.publish(
        Event(
            type="run.started",
            correlation_id=correlation_id,
            resource=resource,
            context=context,
            payload={"contact_id": contact.id, "handle": contact.handle},
        )
    )

    try:
        role = await app.roles.get(contact.role_id) if contact.role_id else None
        personas = [await app.personas.get(pid) for pid in contact.persona_ids]

        session_override = await app.sessions.get_member_override(session_id, contact.id)
        # Roles (DECISIONS.md D-011) contribute a system prompt only, not binding fields;
        # the role precedence level is a no-op until a role-level binding is introduced.
        resolved = resolve_binding(
            system=app.system_binding,
            role=None,
            contact=contact.binding,
            session=session_override,
            turn=None,
        )
        snapshot_id = await app.runs.save_snapshot(resolved)
        await app.runs.set_status(run.id, "running", snapshot_id=snapshot_id)
        await app.publish(
            Event(
                type="run.binding_snapshot",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload=resolved.model_dump(),
            )
        )

        history = await app.messages.list_for_session(session_id)
        compiled = app.compiler.compile(
            contact=contact, role=role, personas=personas, history=history
        )
        await app.publish(
            Event(
                type="context.compiled",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload=compiled.budget.model_dump(),
            )
        )

        provider = app.providers.get(resolved.provider)
        request = ChatRequest(
            model=resolved.model,
            messages=[
                ChatMessage(role=cast(MessageRole, m["role"]), content=m["content"])
                for m in compiled.messages
            ],
            settings=resolved.settings,
        )

        await app.publish(
            Event(
                type="inference.started",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload={"provider": resolved.provider, "model": resolved.model},
            )
        )

        started = time.monotonic()
        first_token_at: float | None = None
        chunks: list[str] = []
        usage_in = usage_out = None
        finish_reason = "stop"

        async for item in provider.chat_stream(request):
            if item.delta:
                if first_token_at is None:
                    first_token_at = time.monotonic()
                    await app.publish(
                        Event(
                            type="inference.first_token",
                            correlation_id=correlation_id,
                            resource=resource,
                            context=context,
                            payload={"elapsed_ms": (first_token_at - started) * 1000},
                        )
                    )
                chunks.append(item.delta)
                await app.publish(
                    Event(
                        type="inference.token",
                        correlation_id=correlation_id,
                        resource=resource,
                        context=context,
                        payload={"delta": item.delta},
                    )
                )
            if item.done:
                finish_reason = item.finish_reason or finish_reason
                if item.usage:
                    usage_in = item.usage.input_tokens
                    usage_out = item.usage.output_tokens

        duration_ms = (time.monotonic() - started) * 1000
        ttft_ms = (first_token_at - started) * 1000 if first_token_at else None
        content = "".join(chunks)

        await app.messages.create(
            session_id, "assistant", content, contact_id=contact.id, run_id=run.id
        )

        tokens_per_second = None
        if usage_out and duration_ms > 0:
            tokens_per_second = usage_out / (duration_ms / 1000)

        await app.runs.save_metrics(
            RunMetrics(
                run_id=run.id,
                input_tokens=usage_in,
                output_tokens=usage_out,
                context_tokens=compiled.budget.used,
                ttft_ms=ttft_ms,
                tokens_per_second=tokens_per_second,
                duration_ms=duration_ms,
                finish_reason=finish_reason,
                outcome="succeeded",
                budget=compiled.budget.model_dump(),
            )
        )
        await app.publish(
            Event(
                type="inference.completed",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload={"finish_reason": finish_reason, "duration_ms": duration_ms},
            )
        )
        await app.runs.set_status(run.id, "succeeded")
        await app.publish(
            Event(
                type="agent.completed",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload={"contact_id": contact.id},
            )
        )
        return RunOutcome(
            run_id=run.id, contact_handle=contact.handle, content=content, status="succeeded"
        )

    except Exception as exc:
        await app.runs.set_status(run.id, "failed", error=str(exc))
        await app.publish(
            Event(
                type="run.failed",
                correlation_id=correlation_id,
                resource=resource,
                context=context,
                payload={"error": str(exc)},
            )
        )
        return RunOutcome(run_id=run.id, contact_handle=contact.handle, content="", status="failed")
