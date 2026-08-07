"""Deterministic fake OpenRouter server: OpenAI-compatible chat + pricing catalog."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

FAKE_MODELS = [
    {
        "id": "anthropic/claude-fixture",
        "name": "Claude Fixture",
        "description": "Deterministic fixture model.",
        "context_length": 200000,
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    }
]


def create_openrouter_app() -> FastAPI:
    app = FastAPI()

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        return {"data": FAKE_MODELS}

    @app.post("/chat/completions")
    async def chat_completions(payload: dict[str, Any]) -> StreamingResponse:
        model = payload["model"]
        last_user = next(
            (m["content"] for m in reversed(payload["messages"]) if m["role"] == "user"), ""
        )
        reply = f"openrouter fixture reply from {model}: {last_user}"
        include_cost = payload.get("usage", {}).get("include", False)

        async def stream() -> Any:
            for word in reply.split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            yield (
                "data: "
                + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
                + "\n\n"
            )
            usage: dict[str, Any] = {
                "prompt_tokens": 12,
                "completion_tokens": len(reply.split(" ")),
            }
            if include_cost:
                usage["cost"] = 0.000123
            yield f"data: {json.dumps({'choices': [], 'usage': usage})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
