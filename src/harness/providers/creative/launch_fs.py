"""Generic "launch_fs"-tier capability (CRE-005, SPEC/CREATIVE_COMPUTE.md
"Integration strategy hierarchy" tier 4/5): reachability health-checking and
SSH-launching an already-discovered Stability Matrix installation's own
recorded launch command — the honest, real thing Harness can do for every
family that has no documented control API (Fooocus and its variants,
StableSwarmUI, SDFX, VoltaML, the training engines, CogStudio), rather than
a per-engine adapter it has no verified protocol detail for.

Both tools below are plain native Tools (TOOL-001): `POST /tools/{name}/run`
already wraps the whole call in a Job (JOB-001) and resolves permission
through PERM-001 *before* the handler runs, so this module needs neither a
second Job layer nor its own permission check — reusing that lifecycle is
what makes "explicit user approval" and "stop controls" (SPEC) real rather
than reimplemented. Training engines get their own tool
(`creative.launch_training`, permission class `training`) rather than
sharing `creative.launch_engine`'s `execute` class — SPEC: "Treat training
as Jobs with explicit user approval... They are not implicitly available to
LLM agents." Both call the same launch implementation and differ only in
which family group they accept, enforced in code so a training installation
can never be started through the lower-friction `execute`-gated tool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from harness.core.domain import CreativeInstallation
from harness.core.errors import ValidationFailedError
from harness.events.model import Event, EventResource
from harness.hosts.resolve import build_ssh_host
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry

if TYPE_CHECKING:
    # Only for the type checker: `core.app` imports this module to register the
    # tools, so importing `Application` back at module load time would cycle
    # (matching `agents.delegate_tool`'s precedent for the same reason).
    from harness.core.app import Application

_MAX_OUTPUT_TAIL_LINES = 200

LAUNCH_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {"installation_id": {"type": "string"}},
    "required": ["installation_id"],
    "additionalProperties": False,
}


async def check_reachable(
    base_url: str, *, http_client: httpx.AsyncClient | None = None, timeout_seconds: float = 5.0
) -> bool:
    """A plain HTTP GET — the "health" half of the launch_fs tier. Any
    response at all (even a non-2xx one, which is normal for e.g. a Gradio
    app's root page) counts as reachable; only a connection-level failure
    means it isn't.
    """
    client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
    owns_client = http_client is None
    try:
        await client.get(base_url)
        return True
    except httpx.HTTPError:
        return False
    finally:
        if owns_client:
            await client.aclose()


async def _run_launch(app: Application, installation: CreativeInstallation) -> dict[str, Any]:
    """Runs inside the Job `POST /tools/{name}/run` already wraps every tool
    call in — canceling that Job (`POST /jobs/{id}/cancel`) cancels this
    coroutine's task, which propagates into `exec_stream`'s loop below and
    closes the SSH connection (`SSHHost.exec_stream`'s own `finally`),
    stopping the remote process rather than leaving it orphaned. That's the
    real "stop control" SPEC calls for, not a separate mechanism.
    """
    if not installation.launch_command:
        raise ValidationFailedError(
            f"installation {installation.id} has no recorded launch command"
        )
    host = await app.hosts.get(installation.host_id)
    ssh_host = await build_ssh_host(host, app.secret_refs, app.secret_store)
    cwd = f"{installation.data_dir.rstrip('/')}/{installation.library_path}"

    resource = EventResource(type="creative_installation", id=installation.id)
    tail: list[str] = []
    async for chunk in ssh_host.exec_stream(installation.launch_command.split(), cwd=cwd):
        tail.append(chunk.data)
        if len(tail) > _MAX_OUTPUT_TAIL_LINES:
            tail.pop(0)
        await app.publish(
            Event(
                type="creative.launch.output",
                resource=resource,
                context={"installation_id": installation.id},
                payload={"stream": chunk.stream, "data": chunk.data},
            )
        )
    return {"installation_id": installation.id, "output_tail": tail}


def register_creative_launch_tools(registry: ToolRegistry, app: Application) -> None:
    async def launch_engine(arguments: dict[str, Any]) -> dict[str, Any]:
        installation = await app.creative_installations.get(arguments["installation_id"])
        if installation.family_group == "training":
            raise ValidationFailedError(
                "training-family installations must be launched via "
                "creative.launch_training, not creative.launch_engine"
            )
        return await _run_launch(app, installation)

    async def launch_training(arguments: dict[str, Any]) -> dict[str, Any]:
        installation = await app.creative_installations.get(arguments["installation_id"])
        if installation.family_group != "training":
            raise ValidationFailedError(
                f"installation {installation.id} (family group "
                f"'{installation.family_group}') is not a training engine"
            )
        return await _run_launch(app, installation)

    registry.register(
        ToolDefinition(
            name="creative.launch_engine",
            description="Launch an already-discovered creative-engine installation's own "
            "recorded command over SSH and stream its output; stays running (as this call's "
            "Job) until it exits or the Job is canceled. Rejects training-family installations.",
            parameters_schema=LAUNCH_PARAMETERS_SCHEMA,
            permission_class="execute",
            handler=launch_engine,
        )
    )
    registry.register(
        ToolDefinition(
            name="creative.launch_training",
            description="Launch an already-discovered training-engine installation (Kohya "
            "GUI/OneTrainer/FluxGym) over SSH as an explicitly-approved Job — training is "
            "never implicitly available to agents (SPEC/CREATIVE_COMPUTE.md).",
            parameters_schema=LAUNCH_PARAMETERS_SCHEMA,
            permission_class="training",
            handler=launch_training,
        )
    )
