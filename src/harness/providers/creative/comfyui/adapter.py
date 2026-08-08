"""Submit -> stream progress -> capture output, run as a Job (JOB-001)
(CRE-003, SPEC/CREATIVE_COMPUTE.md "Required deep integration" > ComfyUI's
required bullet list: health/queue/submit/progress/interrupt/history/
upload/output-capture, all implemented here except image-upload and
interrupt, which are exposed directly on `ComfyUIClient` for a caller to use
independently rather than folded into this one generation flow).

The workflow JSON is stored as an Artifact *before* submission and only ever
referenced by id from here on (ART-001) — SPEC: "ComfyUI workflow JSON MUST
NOT be injected into LLM context by default." Captured output images become
Artifacts the same way, so a caller only ever sees `artifact://<id>`
references, never inlined bytes.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from harness.artifacts.service import store_and_record_artifact
from harness.core.app import Application
from harness.core.errors import ProviderError
from harness.events.model import Event, EventResource
from harness.jobs.manager import JobHandle
from harness.providers.creative.comfyui.client import ComfyUIClient

_TERMINAL_EVENT_TYPES = frozenset({"execution_success", "execution_error", "execution_interrupted"})


async def run_comfyui_generation(
    app: Application,
    handle: JobHandle,
    *,
    base_url: str,
    workflow: dict[str, Any],
    session_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    workflow_artifact = await store_and_record_artifact(
        app,
        type="workflow",
        display_name="comfyui-workflow.json",
        content=json.dumps(workflow).encode("utf-8"),
        mime_type="application/json",
        session_id=session_id,
        workspace_id=workspace_id,
        metadata={"engine_id": "comfyui", "base_url": base_url},
    )

    client = ComfyUIClient(base_url)
    try:
        client_id = uuid.uuid4().hex
        resource = EventResource(type="job", id=handle.job_id)
        error_detail: dict[str, Any] | None = None

        # Connect the WS *before* submitting: ComfyUI starts executing (and
        # pushing progress) as soon as POST /prompt returns, and there is no
        # event replay for a late subscriber (see ComfyUIClient.ws_connect).
        async with client.ws_connect(client_id) as ws:
            await ws.recv()  # initial "status" handshake frame confirms registration

            submitted = await client.submit_prompt(workflow, client_id=client_id)
            prompt_id = submitted.get("prompt_id")
            if not prompt_id:
                raise ProviderError(f"ComfyUI did not return a prompt_id: {submitted}")
            if submitted.get("node_errors"):
                raise ProviderError(f"ComfyUI rejected workflow: {submitted['node_errors']}")

            events = client.iter_ws_events(ws)
            try:
                async for message in events:
                    msg_type = message.get("type", "")
                    data = message.get("data", {})
                    if data.get("prompt_id") not in (None, prompt_id):
                        continue  # traffic for a different prompt on a shared server
                    await app.publish(
                        Event(
                            type=f"creative.comfyui.{msg_type}",
                            resource=resource,
                            context={"job_id": handle.job_id},
                            payload=data,
                        )
                    )
                    if msg_type == "progress" and data.get("max"):
                        await handle.set_progress(data["value"] / data["max"])
                    if msg_type == "execution_error":
                        error_detail = data
                    if msg_type in _TERMINAL_EVENT_TYPES:
                        break
            finally:
                await events.aclose()

        if error_detail is not None:
            raise ProviderError(
                f"ComfyUI execution failed: {error_detail.get('exception_message', error_detail)}"
            )

        history = await client.history(prompt_id)
        record = history.get(prompt_id, {})
        outputs = record.get("outputs", {})

        output_artifact_ids: list[str] = []
        for node_id, node_output in outputs.items():
            for image in node_output.get("images", []):
                content = await client.download_output(
                    image["filename"],
                    subfolder=image.get("subfolder", ""),
                    type=image.get("type", "output"),
                )
                artifact = await store_and_record_artifact(
                    app,
                    type="image",
                    display_name=image["filename"],
                    content=content,
                    session_id=session_id,
                    workspace_id=workspace_id,
                    metadata={
                        "engine_id": "comfyui",
                        "base_url": base_url,
                        "prompt_id": prompt_id,
                        "workflow_artifact_id": workflow_artifact.id,
                        "node_id": node_id,
                    },
                )
                output_artifact_ids.append(artifact.id)

        return {
            "prompt_id": prompt_id,
            "workflow_artifact_id": workflow_artifact.id,
            "output_artifact_ids": output_artifact_ids,
        }
    finally:
        await client.aclose()
