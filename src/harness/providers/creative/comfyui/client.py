"""Hand-rolled ComfyUI HTTP + WebSocket client (CRE-003).

Endpoint paths, request/response shapes, and WebSocket message types below
are verified against ComfyUI's own server.py/execution.py source
(github.com/comfyanonymous/ComfyUI) — there is no published API spec, so
this module is built from source inspection, not guessed. Hand-rolled
against httpx + websockets (both already dependencies) rather than a vendor
SDK, matching every other adapter in this codebase (harness.mcp.client,
harness.providers.language.*).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from harness.core.errors import ProviderError


class ComfyUIClient:
    def __init__(self, base_url: str, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    @property
    def _ws_url(self) -> str:
        return self._base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = await self._client.get(f"{self._base_url}{path}", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ComfyUI GET {path} failed: {exc}") from exc
        return cast(dict[str, Any], resp.json())

    async def _post(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = await self._client.post(f"{self._base_url}{path}", json=json_body or {})
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail: Any = exc.response.json()
            except ValueError:
                detail = exc.response.text
            raise ProviderError(
                f"ComfyUI POST {path} failed ({exc.response.status_code}): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"ComfyUI POST {path} failed: {exc}") from exc
        return cast(dict[str, Any], resp.json()) if resp.content else {}

    async def system_stats(self) -> dict[str, Any]:
        """Health check — ComfyUI has no dedicated `/health`; `/system_stats`
        is the documented liveness endpoint (verified via source).
        """
        return await self._get("/system_stats")

    async def object_info(self) -> dict[str, Any]:
        return await self._get("/object_info")

    async def object_info_for(self, node_class: str) -> dict[str, Any]:
        return await self._get(f"/object_info/{node_class}")

    async def submit_prompt(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str,
        extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Returns ``{"prompt_id": str, "number": float, "node_errors": dict}``."""
        body: dict[str, Any] = {"prompt": prompt, "client_id": client_id}
        if extra_data:
            body["extra_data"] = extra_data
        return await self._post("/prompt", body)

    async def queue(self) -> dict[str, Any]:
        return await self._get("/queue")

    async def queue_depth(self) -> int:
        result = await self._get("/prompt")
        return int(result.get("exec_info", {}).get("queue_remaining", 0))

    async def interrupt(self, prompt_id: str | None = None) -> None:
        await self._post("/interrupt", {"prompt_id": prompt_id} if prompt_id else None)

    async def clear_queue(self, *, clear: bool = False, delete: list[str] | None = None) -> None:
        body: dict[str, Any] = {}
        if clear:
            body["clear"] = True
        if delete:
            body["delete"] = delete
        await self._post("/queue", body)

    async def history(self, prompt_id: str | None = None) -> dict[str, Any]:
        path = f"/history/{prompt_id}" if prompt_id else "/history"
        return await self._get(path)

    async def upload_image(
        self, filename: str, data: bytes, *, image_type: str = "input", subfolder: str = ""
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(
                f"{self._base_url}/upload/image",
                data={"type": image_type, "subfolder": subfolder},
                files={"image": (filename, data)},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ComfyUI image upload failed: {exc}") from exc
        return cast(dict[str, Any], resp.json())

    async def download_output(
        self, filename: str, *, subfolder: str = "", type: str = "output"
    ) -> bytes:
        try:
            resp = await self._client.get(
                f"{self._base_url}/view",
                params={"filename": filename, "subfolder": subfolder, "type": type},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ComfyUI image download failed: {exc}") from exc
        return resp.content

    def ws_connect(self, client_id: str) -> websockets.connect:
        """An async context manager connecting to ComfyUI's WebSocket progress
        stream for ``client_id``, yielding the raw connection.

        Callers MUST open this connection — and consume its first frame,
        ComfyUI's initial ``status`` handshake message, confirming the
        connection is registered server-side — *before* calling
        `submit_prompt` for the same ``client_id``. ComfyUI starts executing
        (and pushing progress) as soon as `POST /prompt` returns; there is no
        event replay for a late subscriber, so connecting afterward risks
        silently missing early events. `iter_ws_events` assumes this ordering.
        """
        uri = f"{self._ws_url}/ws?clientId={client_id}"
        return websockets.connect(uri)

    async def iter_ws_events(self, ws: ClientConnection) -> AsyncGenerator[dict[str, Any], None]:
        """Yields decoded ``{"type": ..., "data": ...}`` progress messages
        (SPEC: ComfyUI progress events over WebSocket) from an already-open
        connection (see `ws_connect`) until it closes. Caller breaks out on a
        terminal event (``execution_success``/``execution_error``/
        ``execution_interrupted``) for the ``prompt_id`` it submitted, and
        calls ``.aclose()`` on the returned generator to stop consuming
        promptly rather than waiting on garbage collection.
        """
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue  # binary preview frames are not progress events
                yield json.loads(raw)
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            raise ProviderError(f"ComfyUI WebSocket connection failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
