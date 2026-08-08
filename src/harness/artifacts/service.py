"""Shared artifact-creation path (ART-001): stores content in the blob store,
records the catalog row, and publishes `artifact.created` — the one place
every caller that turns raw bytes into an Artifact goes through, so the
event is never forgotten. Originally private to `api.routes.artifacts`;
extracted once CRE-003 became a second real caller (storing ComfyUI workflow
JSON and captured output images as Artifacts).
"""

from __future__ import annotations

import mimetypes
from typing import Any

from harness.core.app import Application
from harness.core.domain import Artifact, ArtifactType
from harness.core.ids import new_id
from harness.events.model import Event, EventResource


async def store_and_record_artifact(
    app: Application,
    *,
    type: ArtifactType,
    display_name: str,
    content: bytes,
    mime_type: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    source_path: str | None = None,
    metadata: dict[str, Any] | None = None,
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
        metadata=metadata or {},
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
