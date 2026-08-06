"""Deterministic fake OpenAI-compatible server (TESTING/TEST_STRATEGY.md).

A minimal FastAPI app implementing just enough of the OpenAI Chat Completions +
Models shape to exercise OpenAICompatibleProvider: streaming SSE chat completions
(with a trailing usage-only chunk) and a static models list.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

FAKE_MODELS = ["local-model-a", "local-model-b"]


def create_openai_compat_app() -> FastAPI:
    app = FastAPI()

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        return {"data": [{"id": m, "object": "model"} for m in FAKE_MODELS]}

    @app.post("/chat/completions")
    async def chat_completions(payload: dict[str, Any]) -> StreamingResponse:
        model = payload["model"]
        last_user = next(
            (m["content"] for m in reversed(payload["messages"]) if m["role"] == "user"), ""
        )
        reply = f"fixture reply from {model}: {last_user}"

        async def stream() -> Any:
            for word in reply.split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            yield (
                "data: "
                + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
                + "\n\n"
            )
            usage_chunk = {
                "choices": [],
                "usage": {
                    "prompt_tokens": len(json.dumps(payload["messages"])) // 4,
                    "completion_tokens": len(reply.split(" ")),
                },
            }
            yield f"data: {json.dumps(usage_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
