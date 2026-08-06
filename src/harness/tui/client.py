"""Thin HTTP client the TUI uses to talk to the Harness API — never the database directly."""

from __future__ import annotations

from typing import Any, cast

import httpx


class HarnessClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v1", headers=headers, timeout=30.0
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def list_sessions(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/sessions")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    async def list_contacts(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/contacts")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    async def create_session(self, title: str, contacts: list[str]) -> dict[str, Any]:
        resp = await self._client.post("/sessions", json={"title": title, "contacts": contacts})
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        resp = await self._client.post(
            f"/sessions/{session_id}/messages", json={"content": content}
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def health(self) -> dict[str, Any]:
        resp = await self._client.get("/health")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())
