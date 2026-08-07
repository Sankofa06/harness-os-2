"""Deterministic fake Gemini generateContent server."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

FAKE_MODELS = [
    {"name": "models/gemini-fixture", "displayName": "Gemini Fixture", "inputTokenLimit": 1000000}
]


def create_gemini_app() -> FastAPI:
    app = FastAPI()

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        return {"models": FAKE_MODELS}

    @app.post("/models/{model}:streamGenerateContent")
    async def stream_generate(model: str, payload: dict[str, Any]) -> StreamingResponse:
        last_user = ""
        for content in reversed(payload.get("contents", [])):
            if content["role"] == "user":
                last_user = content["parts"][0]["text"]
                break
        reply = f"gemini fixture reply from {model}: {last_user}"
        words = reply.split(" ")

        async def stream() -> Any:
            for word in words:
                chunk = {
                    "candidates": [{"content": {"parts": [{"text": word + " "}], "role": "model"}}]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            final = {
                "candidates": [
                    {
                        "content": {"parts": [{"text": ""}], "role": "model"},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 9,
                    "candidatesTokenCount": len(words),
                    "totalTokenCount": 9 + len(words),
                },
            }
            yield f"data: {json.dumps(final)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
