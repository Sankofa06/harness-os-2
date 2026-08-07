"""Native tool registry + execution endpoints (TOOL-001, SPEC/MCP_SKILLS_TOOLS.md).

Execution runs as a Job (SPEC/API_CONTRACT.md "long actions create Jobs") since a
real tool (TOOL-002's shell/git tools) can run arbitrarily long; the ToolRun record
`ToolExecutor` persists is the tool-lifecycle-specific state (permission decision,
result, compact output), while the Job is generic scheduling/cancellation plumbing
around it — the same split LP-009 uses for model load/unload.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import ToolRun
from harness.jobs.manager import JobHandle
from harness.jobs.model import Job

router = APIRouter(dependencies=[Depends(require_auth)], tags=["tools"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters_schema: dict[str, Any]
    permission_class: str
    workspace_scoped: bool


@router.get("/tools")
async def list_tools(request: Request) -> list[ToolInfo]:
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            parameters_schema=t.parameters_schema,
            permission_class=t.permission_class,
            workspace_scoped=t.workspace_scoped,
        )
        for t in _app(request).tools.list()
    ]


class ToolRunRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    workspace_id: str | None = None
    session_id: str | None = None


@router.post("/tools/{tool_name}/run", status_code=202)
async def run_tool(request: Request, tool_name: str, body: ToolRunRequest) -> Job:
    app = _app(request)
    app.tools.get(tool_name)  # 404s if unknown, before scheduling a Job for it

    async def work(handle: JobHandle) -> dict[str, Any]:
        run = await app.tool_executor.execute(
            tool_name,
            body.arguments,
            workspace_id=body.workspace_id,
            session_id=body.session_id,
        )
        return {"tool_run_id": run.id, "status": run.status}

    return await app.job_manager.submit("tool.run", work, detail={"tool_name": tool_name})


@router.get("/tools/runs")
async def list_tool_runs(
    request: Request, tool_name: str | None = Query(default=None)
) -> list[ToolRun]:
    return await _app(request).tool_runs.list(tool_name=tool_name)


@router.get("/tools/runs/{run_id}")
async def get_tool_run(request: Request, run_id: str) -> ToolRun:
    return await _app(request).tool_runs.get(run_id)
