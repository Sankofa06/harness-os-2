"""WebSocket event stream: /api/v1/events (SPEC/API_CONTRACT.md).

Client sends a JSON subscribe message with optional filters and an optional
``since_seq`` replay cursor. Unauthenticated non-loopback connections are closed
immediately (DECISIONS.md D-005).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from harness.api.auth import check_token
from harness.core.app import Application
from harness.core.errors import AuthRequiredError
from harness.events.model import EventFilter

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    app: Application = websocket.app.state.harness
    client_host = websocket.client.host if websocket.client else None
    auth_header = websocket.headers.get("authorization")
    token_param = websocket.query_params.get("token")
    if token_param and not auth_header:
        auth_header = f"Bearer {token_param}"

    try:
        check_token(app, client_host, auth_header)
    except AuthRequiredError:
        await websocket.close(code=4401, reason="auth_required")
        return

    await websocket.accept()

    try:
        raw = await websocket.receive_text()
        subscribe = json.loads(raw) if raw else {}
    except (WebSocketDisconnect, json.JSONDecodeError):
        subscribe = {}

    filter_ = EventFilter(
        event_types=subscribe.get("event_types", []),
        session_ids=subscribe.get("session_ids", []),
        job_ids=subscribe.get("job_ids", []),
        host_ids=subscribe.get("host_ids", []),
    )
    # Presence of the key (not its truthiness) signals replay intent, so reconnecting
    # from the very first event (since_seq=0) is distinguishable from a fresh subscribe
    # that only wants events going forward.
    since_seq_raw = subscribe.get("since_seq")

    subscription = app.bus.subscribe(filter_)
    try:
        if since_seq_raw is not None:
            for event in await app.events.replay(int(since_seq_raw)):
                if filter_.matches(event):
                    await websocket.send_text(event.model_dump_json())
        async for event in subscription:
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        subscription.close()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
