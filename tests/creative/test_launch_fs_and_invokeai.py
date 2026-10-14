"""CRE-005: generic launch_fs reachability check + InvokeAI native-API
detection, against a real local fixture server (not mocks).
"""

from __future__ import annotations

import asyncio

import pytest
import uvicorn
from fastapi import FastAPI

from harness.core.errors import ProviderError
from harness.providers.creative.invokeai.detect import detect_invokeai
from harness.providers.creative.launch_fs import check_reachable


async def _start(app: FastAPI) -> tuple[uvicorn.Server, asyncio.Task[None], int]:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn.Server exposes no startup event
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, port


async def _stop(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await task


@pytest.mark.asyncio
async def test_check_reachable_true_for_a_real_server() -> None:
    app = FastAPI()

    @app.get("/")
    async def root() -> dict:
        return {}

    server, task, port = await _start(app)
    try:
        assert await check_reachable(f"http://127.0.0.1:{port}") is True
    finally:
        await _stop(server, task)


@pytest.mark.asyncio
async def test_check_reachable_false_for_nothing_listening() -> None:
    assert await check_reachable("http://127.0.0.1:1") is False


@pytest.mark.asyncio
async def test_check_reachable_true_even_for_a_404_gradio_style_root() -> None:
    """Fooocus/SDFX/etc. often return a non-2xx root page — any response at
    all still means "reachable" (CRE-005's generic health semantics).
    """
    app = FastAPI()
    server, task, port = await _start(app)  # no routes registered at all -> 404
    try:
        assert await check_reachable(f"http://127.0.0.1:{port}") is True
    finally:
        await _stop(server, task)


@pytest.mark.asyncio
async def test_detect_invokeai_true_for_a_real_invokeai_shaped_server() -> None:
    app = FastAPI()

    @app.get("/api/v1/app/version")
    async def version() -> dict:
        return {"version": "5.6.0"}

    server, task, port = await _start(app)
    try:
        version_str = await detect_invokeai(f"http://127.0.0.1:{port}")
        assert version_str == "5.6.0"
    finally:
        await _stop(server, task)


@pytest.mark.asyncio
async def test_detect_invokeai_none_for_a_server_without_that_endpoint() -> None:
    """Reachable (e.g. it's actually ComfyUI or a Fooocus Gradio app) but
    not InvokeAI — detection must say so distinctly from "unreachable".
    """
    app = FastAPI()

    @app.get("/")
    async def root() -> dict:
        return {}

    server, task, port = await _start(app)
    try:
        assert await detect_invokeai(f"http://127.0.0.1:{port}") is None
    finally:
        await _stop(server, task)


@pytest.mark.asyncio
async def test_detect_invokeai_none_for_malformed_version_response() -> None:
    app = FastAPI()

    @app.get("/api/v1/app/version")
    async def version() -> dict:
        return {"not_version": "oops"}

    server, task, port = await _start(app)
    try:
        assert await detect_invokeai(f"http://127.0.0.1:{port}") is None
    finally:
        await _stop(server, task)


@pytest.mark.asyncio
async def test_detect_invokeai_raises_on_unreachable_server() -> None:
    with pytest.raises(ProviderError):
        await detect_invokeai("http://127.0.0.1:1")
