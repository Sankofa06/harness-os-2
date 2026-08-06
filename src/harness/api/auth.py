"""Bearer-token authentication (DECISIONS.md D-005).

Loopback requests are trusted when ``auth.local_trust`` is enabled (default); every
other request must present ``Authorization: Bearer <api_token>``. The same rule is
applied to both REST (dependency) and the WebSocket event stream (explicit check).
"""

from __future__ import annotations

from fastapi import Request

from harness.core.app import Application
from harness.core.errors import AuthRequiredError

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_loopback(client_host: str | None) -> bool:
    return client_host in _LOOPBACK_HOSTS


def check_token(app: Application, client_host: str | None, authorization: str | None) -> None:
    if app.config.auth.local_trust and is_loopback(client_host):
        return
    if authorization and authorization.removeprefix("Bearer ").strip() == app.api_token:
        return
    raise AuthRequiredError("valid bearer token required")


def require_auth(request: Request) -> None:
    app: Application = request.app.state.harness
    client_host = request.client.host if request.client else None
    check_token(app, client_host, request.headers.get("authorization"))
