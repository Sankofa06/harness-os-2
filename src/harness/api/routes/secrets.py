"""Secret metadata endpoints (SPEC/API_CONTRACT.md). Values are never returned."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import SecretRef
from harness.core.ids import new_id

router = APIRouter(dependencies=[Depends(require_auth)], tags=["secrets"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class SecretCreate(BaseModel):
    name: str
    kind: Literal["keyring", "file", "env"]
    target: str
    # Only meaningful for writable backends (keyring/file); accepted here, never
    # returned by any endpoint. Omitted for "env", which reads an existing variable.
    value: str | None = None


@router.get("/secrets/metadata")
async def list_secret_metadata(request: Request) -> list[SecretRef]:
    return await _app(request).secret_refs.list()


@router.post("/secrets", status_code=201)
async def create_secret(request: Request, body: SecretCreate) -> SecretRef:
    app = _app(request)
    if body.value is not None:
        app.secret_store.set(body.kind, body.target, body.value)
    secret_ref = SecretRef(id=new_id("sec"), name=body.name, kind=body.kind, target=body.target)
    return await app.secret_refs.create(secret_ref)


@router.post("/secrets/{secret_id}/test")
async def test_secret(request: Request, secret_id: str) -> dict[str, bool]:
    app = _app(request)
    secret_ref = await app.secret_refs.get(secret_id)
    ok = app.secret_store.test(secret_ref.kind, secret_ref.target)
    return {"ok": ok}


@router.delete("/secrets/{secret_id}", status_code=204)
async def delete_secret(request: Request, secret_id: str) -> None:
    await _app(request).secret_refs.delete(secret_id)
