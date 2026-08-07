"""Deterministic fake Ollama server (TESTING/TEST_STRATEGY.md)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

FAKE_MODELS = [
    {
        "name": "llama3.2:latest",
        "model": "llama3.2:latest",
        "modified_at": "2026-01-01T00:00:00Z",
        "size": 123456,
        "digest": "abc123",
        "details": {
            "family": "llama",
            "parameter_size": "3.2B",
            "quantization_level": "Q4_K_M",
        },
    }
]

# Tracks the last keep_alive seen per model, so tests can assert unload behavior.
last_keep_alive: dict[str, Any] = {}


def create_ollama_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/tags")
    async def tags() -> dict[str, Any]:
        return {"models": FAKE_MODELS}

    @app.post("/api/generate")
    async def generate(payload: dict[str, Any]) -> dict[str, Any]:
        last_keep_alive[payload["model"]] = payload.get("keep_alive", "5m")
        return {"model": payload["model"], "done": True, "response": ""}

    @app.post("/api/chat")
    async def chat(payload: dict[str, Any]) -> StreamingResponse:
        model = payload["model"]
        last_user = next(
            (m["content"] for m in reversed(payload["messages"]) if m["role"] == "user"), ""
        )
        reply = f"ollama fixture reply from {model}: {last_user}"

        async def stream() -> Any:
            for word in reply.split(" "):
                yield (
                    json.dumps(
                        {
                            "model": model,
                            "message": {"role": "assistant", "content": word + " "},
                            "done": False,
                        }
                    )
                    + "\n"
                )
            yield (
                json.dumps(
                    {
                        "model": model,
                        "message": {"role": "assistant", "content": ""},
                        "done": True,
                        "total_duration": 1000,
                        "prompt_eval_count": 12,
                        "eval_count": len(reply.split(" ")),
                    }
                )
                + "\n"
            )

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return app
