"""FastAPI application factory — the product boundary (SPEC/ARCHITECTURE.md).

WebUI and TUI are both plain clients of this API; neither may reach into the database
or runtime directly (AGENTS.md).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from harness.api.routes import agents, events, secrets, sessions, system
from harness.core.app import Application, create_application
from harness.core.config import HarnessConfig, SecurityConfig
from harness.core.errors import HarnessError

API_PREFIX = "/api/v1"


def create_app(
    config: HarnessConfig | None = None, *, application: Application | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_application = application is None
        harness_app = application or await create_application(config)
        app.state.harness = harness_app
        try:
            yield
        finally:
            if owns_application:
                await harness_app.close()

    app = FastAPI(
        title="Harness OS API",
        version="1",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    if config:
        security = config.security
    elif application:
        security = application.config.security
    else:
        security = SecurityConfig()
    if security.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=security.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(HarnessError)
    async def harness_error_handler(request: Request, exc: HarnessError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "correlation_id": request.headers.get("x-correlation-id"),
            },
        )

    app.include_router(system.router, prefix=API_PREFIX)
    app.include_router(agents.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(events.router, prefix=API_PREFIX)
    app.include_router(secrets.router, prefix=API_PREFIX)

    return app
