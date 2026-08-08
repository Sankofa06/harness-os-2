"""A real local ComfyUI-compatible fixture server (FastAPI + WebSocket, run
via `uvicorn.Server` for a genuinely bound port — same pattern as
`tests/mcp/fixtures.py`) for testing `harness.providers.creative.comfyui`
against actual HTTP + WebSocket protocol exchanges rather than mocks.
Endpoint paths, request/response shapes, and WS message types match
ComfyUI's real server (verified via source inspection for CRE-003).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

# Not a real PNG — Harness never decodes image bytes itself, only stores and
# serves them by reference, so arbitrary bytes are an honest stand-in.
FAKE_OUTPUT_BYTES = b"fake-comfyui-output-image-bytes"


class _PromptRecord:
    def __init__(self, prompt_id: str, prompt: dict[str, Any], client_id: str) -> None:
        self.prompt_id = prompt_id
        self.prompt = prompt
        self.client_id = client_id
        self.status = "pending"
        self.outputs: dict[str, Any] = {}


def create_fake_comfyui_app(*, fail_node: str | None = None) -> FastAPI:
    """``fail_node``, when set, makes execution of that node id emit
    `execution_error` instead of completing — used to test CRE-003's failure
    path against a real (if scripted) protocol exchange.
    """
    app = FastAPI()
    connections: dict[str, WebSocket] = {}
    prompts: dict[str, _PromptRecord] = {}
    background_tasks: set[asyncio.Task[None]] = set()

    async def _send(client_id: str, msg_type: str, data: dict[str, Any]) -> None:
        ws = connections.get(client_id)
        if ws is not None:
            await ws.send_json({"type": msg_type, "data": data})

    async def _simulate_execution(record: _PromptRecord) -> None:
        await asyncio.sleep(0.01)
        await _send(record.client_id, "execution_start", {"prompt_id": record.prompt_id})
        node_ids = list(record.prompt.keys()) or ["1"]
        for node_id in node_ids:
            await _send(
                record.client_id, "executing", {"node": node_id, "prompt_id": record.prompt_id}
            )
            await _send(
                record.client_id,
                "progress",
                {"value": 1, "max": 1, "node": node_id, "prompt_id": record.prompt_id},
            )
            if fail_node is not None and node_id == fail_node:
                record.status = "error"
                await _send(
                    record.client_id,
                    "execution_error",
                    {
                        "prompt_id": record.prompt_id,
                        "node_id": node_id,
                        "node_type": "FakeNode",
                        "exception_message": "simulated failure",
                        "exception_type": "RuntimeError",
                    },
                )
                return
            image = {
                "filename": f"ComfyUI_{record.prompt_id[:8]}_{node_id}.png",
                "subfolder": "",
                "type": "output",
            }
            record.outputs[node_id] = {"images": [image]}
            await _send(
                record.client_id,
                "executed",
                {
                    "node": node_id,
                    "prompt_id": record.prompt_id,
                    "output": {"images": [image]},
                },
            )
        record.status = "success"
        await _send(record.client_id, "execution_success", {"prompt_id": record.prompt_id})

    @app.get("/system_stats")
    async def system_stats() -> dict[str, Any]:
        return {
            "system": {"comfyui_version": "0.3.7", "os": "posix"},
            "devices": [{"name": "cpu", "type": "cpu", "vram_total": 0, "vram_free": 0}],
        }

    @app.get("/object_info")
    async def object_info() -> dict[str, Any]:
        return {
            "KSampler": {
                "input": {"required": {}},
                "output": ["LATENT"],
                "name": "KSampler",
                "category": "sampling",
            }
        }

    @app.get("/object_info/{node_class}")
    async def object_info_one(node_class: str) -> dict[str, Any]:
        full = await object_info()
        if node_class in full:
            return {node_class: full[node_class]}
        return {}

    @app.post("/prompt")
    async def submit_prompt(request: Request) -> dict[str, Any]:
        body = await request.json()
        prompt = body.get("prompt", {})
        client_id = body.get("client_id", "")
        if not prompt:
            return JSONResponse(  # type: ignore[return-value]
                status_code=400, content={"error": "empty prompt", "node_errors": {}}
            )
        prompt_id = str(uuid.uuid4())
        record = _PromptRecord(prompt_id, prompt, client_id)
        prompts[prompt_id] = record
        task = asyncio.create_task(_simulate_execution(record))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return {"prompt_id": prompt_id, "number": len(prompts), "node_errors": {}}

    @app.get("/queue")
    async def queue() -> dict[str, Any]:
        return {"queue_running": [], "queue_pending": []}

    @app.get("/prompt")
    async def queue_depth() -> dict[str, Any]:
        pending = sum(1 for p in prompts.values() if p.status == "pending")
        return {"exec_info": {"queue_remaining": pending}}

    @app.post("/interrupt")
    async def interrupt(request: Request) -> dict[str, Any]:
        return {}

    @app.post("/queue")
    async def queue_clear(request: Request) -> dict[str, Any]:
        return {}

    @app.get("/history/{prompt_id}")
    async def history_one(prompt_id: str) -> dict[str, Any]:
        record = prompts.get(prompt_id)
        if record is None:
            return {}
        return {
            prompt_id: {
                "prompt": [0, prompt_id, record.prompt, {}, []],
                "outputs": record.outputs,
                "status": {
                    "status_str": "success" if record.status == "success" else record.status,
                    "completed": record.status == "success",
                    "messages": [],
                },
            }
        }

    @app.get("/history")
    async def history_all() -> dict[str, Any]:
        result = {}
        for prompt_id in prompts:
            result.update(await history_one(prompt_id))
        return result

    @app.post("/upload/image")
    async def upload_image(request: Request) -> dict[str, Any]:
        form = await request.form()
        upload = form.get("image")
        filename = getattr(upload, "filename", None) or "uploaded.png"
        subfolder = form.get("subfolder", "")
        image_type = form.get("type", "input")
        return {"name": filename, "subfolder": subfolder, "type": image_type}

    @app.get("/view")
    async def view(filename: str, subfolder: str = "", type: str = "output") -> Response:
        return Response(content=FAKE_OUTPUT_BYTES, media_type="image/png")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        client_id = websocket.query_params.get("clientId") or str(uuid.uuid4())
        connections[client_id] = websocket
        await websocket.send_json(
            {"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 0}}}}
        )
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            connections.pop(client_id, None)

    return app


@dataclass
class RunningComfyUIServer:
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


async def start_fake_comfyui_server(
    *, fail_node: str | None = None
) -> tuple[uvicorn.Server, asyncio.Task[None], RunningComfyUIServer]:
    config = uvicorn.Config(
        create_fake_comfyui_app(fail_node=fail_node),
        host="127.0.0.1",
        port=0,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn.Server exposes no startup event
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, RunningComfyUIServer(port=port)


async def stop_fake_comfyui_server(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await task
