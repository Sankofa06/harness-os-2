"""Artifact catalog + transfer endpoints (ART-001, SPEC/WORKSPACES_ARTIFACTS.md).

Content is lazy: `GET /artifacts/{id}` returns metadata only, never the blob —
callers fetch `GET /artifacts/{id}/content` separately, so referencing an artifact
(e.g. an agent holding `artifact://<id>` in context) never implicitly pulls bytes.
Blobs are content-addressed by sha256 (`ArtifactBlobStore`), so identical content
uploaded twice, or pulled from two different Workspaces, is stored once.

Transfers move bytes between Harness's managed blob store and a Workspace's Host:
`POST /workspaces/{id}/artifacts/pull` (remote host -> Harness) and
`POST /artifacts/{id}/push` (Harness -> remote host) — SPEC/WORKSPACES_ARTIFACTS.md's
"browser/client -> workspace" transfer is this same push, applied to an Artifact a
client already created via the plain `POST /artifacts` upload; "creative host ->
workspace" is deferred to the (not yet built) creative-compute milestone, which
will create Artifacts the same way and can reuse `push` unchanged.
"""

from __future__ import annotations

import base64
import binascii
import mimetypes
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import Artifact, ArtifactType
from harness.core.errors import ValidationFailedError
from harness.core.ids import new_id
from harness.events.model import Event, EventResource
from harness.workspaces.service import resolve_within_workspace, ssh_host_for_workspace

router = APIRouter(dependencies=[Depends(require_auth)], tags=["artifacts"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class ArtifactCreate(BaseModel):
    type: ArtifactType
    display_name: str
    content_base64: str
    mime_type: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _store_and_record(
    app: Application,
    *,
    type: ArtifactType,
    display_name: str,
    content: bytes,
    mime_type: str | None,
    run_id: str | None,
    session_id: str | None,
    workspace_id: str | None,
    source_path: str | None,
    metadata: dict[str, Any],
) -> Artifact:
    sha256, size = app.artifact_blobs.put(content)
    artifact = Artifact(
        id=new_id("art"),
        type=type,
        mime_type=mime_type or mimetypes.guess_type(display_name)[0] or "application/octet-stream",
        display_name=display_name,
        size=size,
        sha256=sha256,
        run_id=run_id,
        session_id=session_id,
        workspace_id=workspace_id,
        source_path=source_path,
        metadata=metadata,
    )
    created = await app.artifacts.create(artifact)
    await app.publish(
        Event(
            type="artifact.created",
            resource=EventResource(type="artifact", id=created.id),
            payload={"sha256": sha256, "size": size, "type": type},
        )
    )
    return created


@router.post("/artifacts", status_code=201)
async def create_artifact(request: Request, body: ArtifactCreate) -> Artifact:
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except binascii.Error as exc:
        raise ValidationFailedError(f"content_base64 is not valid base64: {exc}") from exc
    return await _store_and_record(
        _app(request),
        type=body.type,
        display_name=body.display_name,
        content=content,
        mime_type=body.mime_type,
        run_id=body.run_id,
        session_id=body.session_id,
        workspace_id=None,
        source_path=None,
        metadata=body.metadata,
    )


@router.get("/artifacts")
async def list_artifacts(
    request: Request,
    run_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
) -> list[Artifact]:
    return await _app(request).artifacts.list(
        run_id=run_id, session_id=session_id, artifact_type=type
    )


@router.get("/artifacts/{artifact_id}")
async def get_artifact(request: Request, artifact_id: str) -> Artifact:
    return await _app(request).artifacts.get(artifact_id)


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_content(request: Request, artifact_id: str) -> Response:
    app = _app(request)
    artifact = await app.artifacts.get(artifact_id)
    content = app.artifact_blobs.get(artifact.sha256)
    return Response(content=content, media_type=artifact.mime_type)


@router.delete("/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(request: Request, artifact_id: str) -> None:
    # Removes only the catalog record. The blob is content-addressed and may be
    # shared by other artifacts, so it is left on disk (no reference counting yet).
    await _app(request).artifacts.delete(artifact_id)


class ArtifactPullRequest(BaseModel):
    path: str
    type: ArtifactType
    display_name: str | None = None
    mime_type: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/workspaces/{workspace_id}/artifacts/pull", status_code=201)
async def pull_artifact(request: Request, workspace_id: str, body: ArtifactPullRequest) -> Artifact:
    """Copy a file from a Workspace's Host into Harness's managed artifact store
    (SPEC/WORKSPACES_ARTIFACTS.md "remote host -> Harness").
    """
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    absolute = resolve_within_workspace(workspace, body.path)
    ssh_host = await ssh_host_for_workspace(workspace, app.hosts, app.secret_refs, app.secret_store)
    content = await ssh_host.read_file(absolute)
    return await _store_and_record(
        app,
        type=body.type,
        display_name=body.display_name or body.path.rsplit("/", 1)[-1],
        content=content,
        mime_type=body.mime_type,
        run_id=body.run_id,
        session_id=body.session_id,
        workspace_id=workspace_id,
        source_path=body.path,
        metadata=body.metadata,
    )


class ArtifactPushRequest(BaseModel):
    workspace_id: str
    path: str


class ArtifactPushResult(BaseModel):
    sha256: str
    size: int
    path: str


@router.post("/artifacts/{artifact_id}/push")
async def push_artifact(
    request: Request, artifact_id: str, body: ArtifactPushRequest
) -> ArtifactPushResult:
    """Write an Artifact's content out to a path in a Workspace
    (SPEC/WORKSPACES_ARTIFACTS.md "Harness -> remote host"; the same primitive
    covers "browser/client -> workspace" for a client-uploaded Artifact).
    """
    app = _app(request)
    artifact = await app.artifacts.get(artifact_id)
    content = app.artifact_blobs.get(artifact.sha256)
    workspace = await app.workspaces.get(body.workspace_id)
    absolute = resolve_within_workspace(workspace, body.path)
    ssh_host = await ssh_host_for_workspace(workspace, app.hosts, app.secret_refs, app.secret_store)
    await ssh_host.write_file(absolute, content)
    await app.publish(
        Event(
            type="artifact.transferred",
            resource=EventResource(type="artifact", id=artifact_id),
            payload={
                "direction": "push",
                "workspace_id": body.workspace_id,
                "path": body.path,
                "sha256": artifact.sha256,
                "size": artifact.size,
            },
        )
    )
    return ArtifactPushResult(sha256=artifact.sha256, size=artifact.size, path=body.path)
