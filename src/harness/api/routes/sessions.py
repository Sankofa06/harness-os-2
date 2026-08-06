"""Sessions / messages endpoints (SPEC/API_CONTRACT.md)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from harness.agents.runloop import handle_user_message
from harness.api.auth import require_auth
from harness.api.schemas import (
    BindingOverride,
    MessageCreate,
    MessagesResponse,
    RunOutcomeResponse,
    SessionCreate,
)
from harness.core.app import Application
from harness.core.domain import Session
from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.events.model import Event, EventResource

router = APIRouter(dependencies=[Depends(require_auth)], tags=["sessions"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


@router.get("/sessions")
async def list_sessions(request: Request) -> list[Session]:
    return await _app(request).sessions.list()


@router.post("/sessions", status_code=201)
async def create_session(request: Request, body: SessionCreate) -> Session:
    app = _app(request)
    contact_ids = []
    for handle in body.contacts:
        contact = await app.contacts.get_by_handle(handle)
        if contact is None:
            raise NotFoundError(f"contact not found: {handle}")
        contact_ids.append(contact.id)
    session = await app.sessions.create(body.title, contact_ids)
    await app.publish(
        Event(
            type="session.started",
            resource=EventResource(type="session", id=session.id),
            context={"session_id": session.id},
            payload={"title": session.title},
        )
    )
    return session


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> Session:
    return await _app(request).sessions.get(session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(request: Request, session_id: str) -> None:
    await _app(request).sessions.delete(session_id)


@router.post("/sessions/{session_id}/messages")
async def post_message(request: Request, session_id: str, body: MessageCreate) -> MessagesResponse:
    app = _app(request)
    correlation_id = new_id("run")
    outcomes = await handle_user_message(
        app, session_id, body.content, correlation_id=correlation_id
    )
    return MessagesResponse(
        correlation_id=correlation_id,
        runs=[
            RunOutcomeResponse(
                run_id=o.run_id,
                contact_handle=o.contact_handle,
                content=o.content,
                status=o.status,
            )
            for o in outcomes
        ],
    )


@router.patch("/sessions/{session_id}/contacts/{contact_id}/binding")
async def set_contact_binding(
    request: Request, session_id: str, contact_id: str, body: BindingOverride
) -> dict[str, str]:
    app = _app(request)
    await app.sessions.get(session_id)
    await app.contacts.get(contact_id)
    await app.sessions.set_member_override(session_id, contact_id, body.binding)
    return {"status": "ok"}
