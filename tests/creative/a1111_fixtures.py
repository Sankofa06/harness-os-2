"""A real local A1111-compatible fixture server (FastAPI, run via
`uvicorn.Server` for a genuinely bound port — same pattern as
`tests/creative/fixtures.py`'s ComfyUI fixture) for testing
`harness.providers.creative.a1111` against actual HTTP exchanges rather than
mocks. Endpoint paths and response shapes match AUTOMATIC1111 WebUI's real
`/sdapi/v1/*` API (verified via source inspection for CRE-004).
"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Request

# Not real image bytes — Harness only stores/serves these by reference and
# never decodes them itself, so arbitrary (base64-safe) bytes are honest.
FAKE_IMAGE_BYTES = b"fake-a1111-output-image-bytes"
FAKE_IMAGE_B64 = base64.b64encode(FAKE_IMAGE_BYTES).decode("ascii")


def create_fake_a1111_app(
    *,
    omit_endpoints: frozenset[str] = frozenset(),
    progress_steps: int = 2,
    generation_delay_seconds: float = 0.05,
) -> FastAPI:
    """``omit_endpoints`` is a set of capability names (matching
    `A1111Client.discover_capabilities`'s vocabulary: "loras", "schedulers",
    "sd_vae", ...) whose routes this fixture simply doesn't register — the
    real-world condition CRE-004's capability negotiation exists for (SPEC:
    "works vs fake A1111 server exposing partial capabilities").
    """
    app = FastAPI()
    state = {"progress_calls": 0, "interrupted": False}

    if "options" not in omit_endpoints:

        @app.get("/sdapi/v1/options")
        async def get_options() -> dict[str, Any]:
            return {"sd_model_checkpoint": "fake-checkpoint.safetensors"}

        @app.post("/sdapi/v1/options")
        async def set_options(request: Request) -> dict[str, Any]:
            await request.json()
            return {}

    if "samplers" not in omit_endpoints:

        @app.get("/sdapi/v1/samplers")
        async def samplers() -> list[dict[str, Any]]:
            return [{"name": "Euler", "aliases": ["euler"], "options": {}}]

    if "schedulers" not in omit_endpoints:

        @app.get("/sdapi/v1/schedulers")
        async def schedulers() -> list[dict[str, Any]]:
            return [{"name": "Automatic", "label": "Automatic", "aliases": [], "default_rho": 1.0}]

    if "sd_models" not in omit_endpoints:

        @app.get("/sdapi/v1/sd-models")
        async def sd_models() -> list[dict[str, Any]]:
            return [{"title": "fake.safetensors", "model_name": "fake", "hash": "abc123"}]

    if "sd_vae" not in omit_endpoints:

        @app.get("/sdapi/v1/sd-vae")
        async def sd_vae() -> list[dict[str, Any]]:
            return [{"model_name": "fake-vae", "filename": "fake-vae.safetensors"}]

    if "loras" not in omit_endpoints:

        @app.get("/sdapi/v1/loras")
        async def loras() -> list[dict[str, Any]]:
            return [{"name": "fake-lora", "alias": "fake", "path": "/fake/lora.safetensors"}]

    if "progress" not in omit_endpoints:

        @app.get("/sdapi/v1/progress")
        async def progress() -> dict[str, Any]:
            state["progress_calls"] += 1
            done = state["progress_calls"] >= progress_steps
            return {
                "progress": 1.0 if done else 0.5,
                "eta_relative": 0.0 if done else 1.0,
                "state": {"job": "task", "sampling_step": 1, "sampling_steps": 2},
                "current_image": None,
                "textinfo": None,
            }

    if "interrupt" not in omit_endpoints:

        @app.post("/sdapi/v1/interrupt")
        async def interrupt() -> dict[str, Any]:
            state["interrupted"] = True
            return {}

    if "txt2img" not in omit_endpoints:

        @app.post("/sdapi/v1/txt2img")
        async def txt2img(request: Request) -> dict[str, Any]:
            body = await request.json()
            await asyncio.sleep(generation_delay_seconds)
            return {
                "images": [FAKE_IMAGE_B64],
                "parameters": body,
                "info": json.dumps({"seed": 42, "prompt": body.get("prompt", "")}),
            }

    if "img2img" not in omit_endpoints:

        @app.post("/sdapi/v1/img2img")
        async def img2img(request: Request) -> dict[str, Any]:
            body = await request.json()
            await asyncio.sleep(generation_delay_seconds)
            return {
                "images": [FAKE_IMAGE_B64, FAKE_IMAGE_B64],
                "parameters": {k: v for k, v in body.items() if k != "init_images"},
                "info": '{"seed": 7}',
            }

    if "extras" not in omit_endpoints:

        @app.post("/sdapi/v1/extra-single-image")
        async def extra_single_image(request: Request) -> dict[str, Any]:
            await request.json()
            return {"image": FAKE_IMAGE_B64, "html_info": ""}

    @app.get("/__state__")
    async def debug_state() -> dict[str, Any]:
        return state

    return app


@dataclass
class RunningA1111Server:
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


async def start_fake_a1111_server(
    *,
    omit_endpoints: frozenset[str] = frozenset(),
    progress_steps: int = 2,
    generation_delay_seconds: float = 0.05,
) -> tuple[uvicorn.Server, asyncio.Task[None], RunningA1111Server]:
    config = uvicorn.Config(
        create_fake_a1111_app(
            omit_endpoints=omit_endpoints,
            progress_steps=progress_steps,
            generation_delay_seconds=generation_delay_seconds,
        ),
        host="127.0.0.1",
        port=0,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn.Server exposes no startup event
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, RunningA1111Server(port=port)


async def stop_fake_a1111_server(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await task
