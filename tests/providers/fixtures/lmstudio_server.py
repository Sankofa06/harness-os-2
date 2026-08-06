"""Deterministic fake LM Studio server: native /api/v1/models* plus the
OpenAI-compatible /v1/chat/completions surface used for actual chat.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

FAKE_MODELS = [
    {
        "id": "qwen2.5-7b-instruct",
        "object": "model",
        "type": "llm",
        "publisher": "lmstudio-community",
        "arch": "qwen2",
        "compatibility_type": "gguf",
        "quantization": "Q4_K_M",
        "state": "not-loaded",
        "max_context_length": 32768,
    },
    {
        "id": "llama-3.1-8b-instruct",
        "object": "model",
        "type": "llm",
        "publisher": "lmstudio-community",
        "arch": "llama",
        "compatibility_type": "gguf",
        "quantization": "Q4_K_M",
        "state": "loaded",
        "max_context_length": 131072,
    },
]


def create_lmstudio_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/models")
    async def list_models() -> dict[str, Any]:
        return {"object": "list", "data": FAKE_MODELS}

    @app.post("/api/v1/models/load")
    async def load_model(payload: dict[str, Any]) -> dict[str, Any]:
        response: dict[str, Any] = {
            "type": "llm",
            "instance_id": f"{payload['model']}:1",
            "load_time_seconds": 1.23,
            "status": "loaded",
        }
        if payload.get("echo_load_config"):
            response["load_config"] = {k: v for k, v in payload.items() if k != "model"}
        return response

    @app.post("/api/v1/models/unload")
    async def unload_model(payload: dict[str, Any]) -> dict[str, Any]:
        return {"instance_id": payload["instance_id"]}

    @app.post("/v1/chat/completions")
    async def chat_completions(payload: dict[str, Any]) -> StreamingResponse:
        model = payload["model"]
        last_user = next(
            (m["content"] for m in reversed(payload["messages"]) if m["role"] == "user"), ""
        )
        reply = f"lmstudio fixture reply from {model}: {last_user}"

        async def stream() -> Any:
            for word in reply.split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            yield (
                "data: "
                + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
