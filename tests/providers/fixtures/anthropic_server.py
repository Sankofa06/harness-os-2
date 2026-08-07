"""Deterministic fake Anthropic Messages API server."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_anthropic_app() -> FastAPI:
    app = FastAPI()

    @app.post("/messages")
    async def messages(payload: dict[str, Any]) -> StreamingResponse:
        model = payload["model"]
        last_user = next(
            (m["content"] for m in reversed(payload["messages"]) if m["role"] == "user"), ""
        )
        reply = f"anthropic fixture reply from {model}: {last_user}"
        words = reply.split(" ")

        async def stream() -> Any:
            yield _sse(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_fixture",
                        "role": "assistant",
                        "model": model,
                        "usage": {"input_tokens": 11, "output_tokens": 0},
                    },
                },
            )
            yield _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            )
            for word in words:
                yield _sse(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": word + " "},
                    },
                )
            yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
            yield _sse(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": len(words)},
                },
            )
            yield _sse("message_stop", {"type": "message_stop"})

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
