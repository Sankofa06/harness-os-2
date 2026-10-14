"""InvokeAI native-API detection (CRE-005).

InvokeAI's native API (distinct from the AUTOMATIC1111 "sdapi" convention
other families speak) exposes an unauthenticated version endpoint, verified
directly from source (`invokeai/app/api/routers/app_info.py`,
github.com/invoke-ai/InvokeAI): ``GET /api/v1/app/version`` -> ``{"version":
"<str>"}``. Detection means confirming a server at a given base URL
genuinely responds with that shape — not just that *something* answers HTTP,
which `harness.providers.creative.launch_fs.check_reachable` already covers
for engines with no documented API. InvokeAI gets both: reachability is
cheap and generic, but "native API detected" is the real, specific claim
SPEC calls for.
"""

from __future__ import annotations

import httpx

from harness.core.errors import ProviderError

_VERSION_PATH = "/api/v1/app/version"


async def detect_invokeai(
    base_url: str, *, http_client: httpx.AsyncClient | None = None, timeout_seconds: float = 5.0
) -> str | None:
    """Returns the reported version string if ``base_url`` genuinely answers
    InvokeAI's native version endpoint with the expected shape, or ``None``
    if it answers but doesn't look like InvokeAI (e.g. a 404, or JSON
    missing the expected field) — distinct from a connection failure, which
    raises `ProviderError` the same way every other adapter in this codebase
    reports "couldn't reach it at all".
    """
    client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
    owns_client = http_client is None
    try:
        try:
            resp = await client.get(f"{base_url.rstrip('/')}{_VERSION_PATH}")
        except httpx.HTTPError as exc:
            raise ProviderError(f"InvokeAI detection request failed: {exc}") from exc
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        version = data.get("version")
        return version if isinstance(version, str) else None
    finally:
        if owns_client:
            await client.aclose()
