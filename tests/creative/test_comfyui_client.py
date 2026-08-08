"""CRE-003: `ComfyUIClient` against a real local fixture ComfyUI server
(`tests/creative/fixtures.py`, uvicorn-bound port + real WebSocket), not
mocks — exercising the actual HTTP + WS protocol exchange this client
implements.
"""

from __future__ import annotations

import uuid

import pytest

from harness.core.errors import ProviderError
from harness.providers.creative.comfyui.client import ComfyUIClient
from tests.creative.fixtures import start_fake_comfyui_server, stop_fake_comfyui_server


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_comfyui_server()
    try:
        yield info
    finally:
        await stop_fake_comfyui_server(server, task)


@pytest.fixture
async def failing_server():
    server, task, info = await start_fake_comfyui_server(fail_node="1")
    try:
        yield info
    finally:
        await stop_fake_comfyui_server(server, task)


async def _submit_and_collect(client: ComfyUIClient, workflow: dict) -> tuple[str, list[dict]]:
    client_id = uuid.uuid4().hex
    messages: list[dict] = []
    async with client.ws_connect(client_id) as ws:
        await ws.recv()  # initial status handshake
        submitted = await client.submit_prompt(workflow, client_id=client_id)
        prompt_id = submitted["prompt_id"]
        events = client.iter_ws_events(ws)
        try:
            async for message in events:
                messages.append(message)
                if message["type"] in ("execution_success", "execution_error"):
                    break
        finally:
            await events.aclose()
    return prompt_id, messages


@pytest.mark.asyncio
async def test_system_stats_returns_real_server_info(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        stats = await client.system_stats()
        assert stats["system"]["comfyui_version"] == "0.3.7"
        assert stats["devices"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_object_info_returns_node_metadata(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        full = await client.object_info()
        assert "KSampler" in full
        single = await client.object_info_for("KSampler")
        assert single == {"KSampler": full["KSampler"]}
        missing = await client.object_info_for("DoesNotExist")
        assert missing == {}
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_submit_and_stream_progress_to_success(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        prompt_id, messages = await _submit_and_collect(client, {"1": {"class_type": "KSampler"}})
        types = [m["type"] for m in messages]
        assert types == [
            "execution_start",
            "executing",
            "progress",
            "executed",
            "execution_success",
        ]
        assert all(m["data"]["prompt_id"] == prompt_id for m in messages)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_history_reflects_completed_prompt(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        prompt_id, _ = await _submit_and_collect(client, {"1": {"class_type": "KSampler"}})
        history = await client.history(prompt_id)
        record = history[prompt_id]
        assert record["status"]["completed"] is True
        assert record["status"]["status_str"] == "success"
        images = record["outputs"]["1"]["images"]
        assert images[0]["filename"].startswith("ComfyUI_")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_download_output_returns_real_bytes(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        prompt_id, _ = await _submit_and_collect(client, {"1": {"class_type": "KSampler"}})
        history = await client.history(prompt_id)
        image = history[prompt_id]["outputs"]["1"]["images"][0]
        content = await client.download_output(
            image["filename"], subfolder=image["subfolder"], type=image["type"]
        )
        assert len(content) > 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_execution_error_is_reported_over_ws(failing_server) -> None:
    client = ComfyUIClient(failing_server.base_url)
    try:
        prompt_id, messages = await _submit_and_collect(client, {"1": {"class_type": "KSampler"}})
        assert messages[-1]["type"] == "execution_error"
        assert messages[-1]["data"]["exception_message"] == "simulated failure"
        assert messages[-1]["data"]["prompt_id"] == prompt_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_submitting_empty_prompt_is_rejected(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        with pytest.raises(ProviderError):
            await client.submit_prompt({}, client_id=uuid.uuid4().hex)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_queue_and_interrupt_and_clear(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        queue = await client.queue()
        assert queue == {"queue_running": [], "queue_pending": []}
        depth = await client.queue_depth()
        assert isinstance(depth, int)
        await client.interrupt()
        await client.interrupt("some-prompt-id")
        await client.clear_queue(clear=True)
        await client.clear_queue(delete=["some-id"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_upload_image_returns_real_response(running_server) -> None:
    client = ComfyUIClient(running_server.base_url)
    try:
        result = await client.upload_image("input.png", b"fake-bytes", subfolder="masks")
        assert result["name"] == "input.png"
        assert result["subfolder"] == "masks"
        assert result["type"] == "input"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unreachable_server_raises_provider_error() -> None:
    client = ComfyUIClient("http://127.0.0.1:1")  # nothing listens on port 1
    try:
        with pytest.raises(ProviderError):
            await client.system_stats()
    finally:
        await client.aclose()
