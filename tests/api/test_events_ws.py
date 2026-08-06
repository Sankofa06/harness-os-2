import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from harness.api.app import create_app
from harness.core.app import create_application
from harness.core.config import HarnessConfig


def _build_app():
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = asyncio.run(create_application(config))
    return create_app(application=application)


def _loopback_client(app) -> TestClient:
    # TestClient's default synthetic client address isn't loopback; make it explicit
    # so these tests exercise the "authenticated local client" path (DECISIONS.md D-005).
    return TestClient(app, client=("127.0.0.1", 123))


def test_ws_receives_matching_event_and_ignores_others() -> None:
    app = _build_app()
    with _loopback_client(app) as client, client.websocket_connect("/api/v1/events") as ws:
        ws.send_text(json.dumps({"event_types": ["session.started"]}))
        resp = client.post("/api/v1/sessions", json={"title": "ws-demo", "contacts": []})
        assert resp.status_code == 201

        message = ws.receive_text()
        event = json.loads(message)
        assert event["type"] == "session.started"
        assert event["payload"]["title"] == "ws-demo"


def test_ws_replays_from_cursor() -> None:
    app = _build_app()
    with _loopback_client(app) as client:
        client.post("/api/v1/sessions", json={"title": "before-replay", "contacts": []})

        with client.websocket_connect("/api/v1/events") as ws:
            ws.send_text(json.dumps({"event_types": ["session.started"], "since_seq": 0}))
            message = ws.receive_text()
            event = json.loads(message)
            assert event["type"] == "session.started"
            assert event["payload"]["title"] == "before-replay"


def test_ws_accepts_non_loopback_client_with_valid_token() -> None:
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = asyncio.run(create_application(config))
    app = create_app(application=application)
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {application.api_token}"
        with client.websocket_connect(f"/api/v1/events?token={application.api_token}") as ws:
            ws.send_text(json.dumps({"event_types": ["session.started"]}))
            client.post("/api/v1/sessions", json={"title": "token-auth", "contacts": []})
            event = json.loads(ws.receive_text())
            assert event["payload"]["title"] == "token-auth"


def test_ws_rejects_unauthenticated_non_loopback() -> None:
    from starlette.websockets import WebSocketDisconnect

    app = _build_app()
    # TestClient's default synthetic client address is not loopback, so this exercises
    # the "remote client without a token" rejection path.
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/api/v1/events"),
    ):
        pass
    assert excinfo.value.code == 4401
