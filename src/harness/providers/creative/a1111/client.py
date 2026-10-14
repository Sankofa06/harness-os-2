"""Hand-rolled A1111-compatible HTTP client (CRE-004).

Endpoint paths and request/response shapes below are verified against
AUTOMATIC1111/stable-diffusion-webui's own source
(`modules/api/api.py`/`modules/api/models.py`, plus the built-in LoRA
extension `extensions-builtin/Lora/scripts/lora_script.py`) — there is no
published API spec, so this is built from source inspection, not guessed.

"Capability-negotiated" (CRE-004's acceptance bar) means every call here
treats a 404 from the server as *that server doesn't have this endpoint*,
translating it to `UnsupportedCapabilityError` rather than a generic
`ProviderError` — a caller can distinguish "this engine instance doesn't
support X" from "X genuinely failed." `/sdapi/v1/loras` is the clearest
verified real-world case: it's registered by a built-in *extension* via
`on_app_started`, not `api.py`'s core route table, so a build running
without that extension genuinely lacks it. `/sdapi/v1/schedulers` is a
newer, separate addition from `/sdapi/v1/samplers` and is treated the same
way. Every other endpoint below is core (`api.py`'s own 36 registered
routes, per source) and is attempted directly; the same 404-translation
still applies if an unusual fork happens to lack one, rather than assuming
blanket parity.
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from harness.core.errors import ProviderError, UnsupportedCapabilityError

# Core (api.py) vs extension-provided (lora_script.py) / newer-addition
# endpoints, per source inspection — used only to word the 404 error clearly.
_EXTENSION_OR_NEWER_PATHS = frozenset({"/sdapi/v1/loras", "/sdapi/v1/schedulers"})


class A1111Client:
    def __init__(self, base_url: str, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            resp = await self._client.get(f"{self._base_url}{path}", params=params)
            if resp.status_code == 404:
                self._raise_unsupported(path)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"A1111 GET {path} failed: {exc}") from exc
        return resp.json()

    async def _post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        try:
            resp = await self._client.post(f"{self._base_url}{path}", json=json_body or {})
            if resp.status_code == 404:
                self._raise_unsupported(path)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"A1111 POST {path} failed: {exc}") from exc
        return resp.json() if resp.content else {}

    def _raise_unsupported(self, path: str) -> None:
        reason = (
            "a known extension-provided or newer-addition endpoint absent on this build"
            if path in _EXTENSION_OR_NEWER_PATHS
            else "not present on this server/fork"
        )
        raise UnsupportedCapabilityError(f"{self._base_url} has no {path} endpoint ({reason})")

    async def txt2img(self, **params: Any) -> dict[str, Any]:
        """Returns ``{"images": [base64, ...], "parameters": dict, "info": str}``."""
        return cast(dict[str, Any], await self._post("/sdapi/v1/txt2img", params))

    async def img2img(self, **params: Any) -> dict[str, Any]:
        """Same response shape as `txt2img`; ``params`` must include
        ``init_images`` (a list of base64 strings).
        """
        return cast(dict[str, Any], await self._post("/sdapi/v1/img2img", params))

    async def get_options(self) -> dict[str, Any]:
        return cast(dict[str, Any], await self._get("/sdapi/v1/options"))

    async def set_options(self, options: dict[str, Any]) -> None:
        await self._post("/sdapi/v1/options", options)

    async def samplers(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._get("/sdapi/v1/samplers"))

    async def schedulers(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._get("/sdapi/v1/schedulers"))

    async def sd_models(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._get("/sdapi/v1/sd-models"))

    async def sd_vae(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._get("/sdapi/v1/sd-vae"))

    async def loras(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._get("/sdapi/v1/loras"))

    async def progress(self, *, skip_current_image: bool = False) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._get("/sdapi/v1/progress", {"skip_current_image": skip_current_image}),
        )

    async def interrupt(self) -> None:
        await self._post("/sdapi/v1/interrupt")

    async def extra_single_image(self, **params: Any) -> dict[str, Any]:
        """``params`` must include ``image`` (a base64 string)."""
        return cast(dict[str, Any], await self._post("/sdapi/v1/extra-single-image", params))

    async def extra_batch_images(self, **params: Any) -> dict[str, Any]:
        """``params`` must include ``imageList`` (a list of
        ``{"data": base64, "name": str}``).
        """
        return cast(dict[str, Any], await self._post("/sdapi/v1/extra-batch-images", params))

    async def discover_capabilities(self) -> frozenset[str]:
        """Probes every read-only endpoint directly (side-effect-free, so
        safe to call eagerly) and returns the subset that actually responded.
        txt2img/img2img/interrupt/extras are mutating-by-design and are not
        probed destructively; they're reported present whenever ``options``
        responds at all, since they are core `api.py` routes with no verified
        real-world case of selective absence (unlike loras/schedulers) —
        callers calling them directly still get a clean
        `UnsupportedCapabilityError` on an actual 404 regardless.
        """
        caps: set[str] = set()
        probes = {
            "options": self.get_options,
            "samplers": self.samplers,
            "schedulers": self.schedulers,
            "sd_models": self.sd_models,
            "sd_vae": self.sd_vae,
            "loras": self.loras,
            "progress": self.progress,
        }
        for name, probe in probes.items():
            try:
                await probe()
                caps.add(name)
            except UnsupportedCapabilityError:
                continue
        if "options" in caps:
            caps.update({"txt2img", "img2img", "interrupt", "extras"})
        return frozenset(caps)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
