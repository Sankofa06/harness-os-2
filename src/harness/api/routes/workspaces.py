"""Workspace endpoints (WSP-001, SPEC/WORKSPACES_ARTIFACTS.md, SPEC/API_CONTRACT.md).

A Workspace pins a folder on a Host that filesystem/shell operations are scoped to.
Two containment layers apply to every path a caller supplies: the Host's own
``workspace_roots`` (enforced inside ``SSHHost``, HOST-002) and — narrower — the
Workspace's own ``root_path``, enforced here so one Workspace can never read or write
across into a sibling Workspace that happens to share the same Host.

Only SSH hosts are supported so far, matching HOST-001/HOST-002; other Host kinds
raise a validation error rather than silently no-op'ing (AGENTS.md: adapters declare
capabilities honestly, never fake parity).
"""

from __future__ import annotations

import posixpath
from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import Workspace
from harness.core.errors import ValidationFailedError
from harness.core.ids import new_id
from harness.hosts.path_safety import canonicalize_and_check
from harness.hosts.resolve import build_ssh_host
from harness.hosts.ssh import SftpEntry, SSHHost

router = APIRouter(dependencies=[Depends(require_auth)], tags=["workspaces"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


async def _ssh_host_for(app: Application, host_id: str) -> SSHHost:
    host = await app.hosts.get(host_id)
    return await build_ssh_host(host, app.secret_refs, app.secret_store)


def _resolve_within_workspace(workspace: Workspace, relative_path: str) -> str:
    """Join a caller-supplied relative path onto the workspace root and verify the
    result still falls under that root — the workspace-level containment layer, on
    top of (not instead of) the Host-level check `SSHHost` performs on every call.
    """
    absolute = posixpath.normpath(posixpath.join(workspace.root_path, relative_path.lstrip("/")))
    return canonicalize_and_check(absolute, [workspace.root_path])


class WorkspaceCreate(BaseModel):
    host_id: str
    root_path: str
    display_name: str


@router.get("/hosts/{host_id}/workspaces/browse")
async def browse_host_path(
    request: Request, host_id: str, path: str = Query(...)
) -> list[SftpEntry]:
    """List a directory under one of the Host's configured workspace roots — used to
    let the caller pick or confirm a folder before a Workspace record exists.
    """
    ssh_host = await _ssh_host_for(_app(request), host_id)
    return await ssh_host.list_dir(path)


class CreateFolderRequest(BaseModel):
    path: str


@router.post("/hosts/{host_id}/workspaces/create-folder", status_code=201)
async def create_folder(request: Request, host_id: str, body: CreateFolderRequest) -> None:
    ssh_host = await _ssh_host_for(_app(request), host_id)
    await ssh_host.mkdir(body.path)


@router.post("/workspaces", status_code=201)
async def create_workspace(request: Request, body: WorkspaceCreate) -> Workspace:
    app = _app(request)
    host = await app.hosts.get(body.host_id)
    if host.kind != "ssh":
        raise ValidationFailedError(f"host {host.id} is not an SSH host (kind={host.kind})")
    # Fail fast with a clear error before persisting a Workspace whose root isn't
    # actually reachable under the Host's configured roots.
    canonicalize_and_check(body.root_path, host.workspace_roots)
    workspace = Workspace(
        id=new_id("ws"),
        host_id=body.host_id,
        root_path=body.root_path,
        display_name=body.display_name,
    )
    return await app.workspaces.create(workspace)


@router.get("/workspaces")
async def list_workspaces(request: Request) -> list[Workspace]:
    return await _app(request).workspaces.list()


@router.get("/workspaces/{workspace_id}")
async def get_workspace(request: Request, workspace_id: str) -> Workspace:
    return await _app(request).workspaces.get(workspace_id)


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(request: Request, workspace_id: str) -> None:
    # Deletes only the Harness-side record; files on the Host are left untouched.
    await _app(request).workspaces.delete(workspace_id)


@router.get("/workspaces/{workspace_id}/tree")
async def get_workspace_tree(
    request: Request, workspace_id: str, path: str = Query(default="")
) -> list[SftpEntry]:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    absolute = _resolve_within_workspace(workspace, path)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    return await ssh_host.list_dir(absolute)


class FileContent(BaseModel):
    path: str
    content: str
    size: int
    binary: bool


@router.get("/workspaces/{workspace_id}/file")
async def read_workspace_file(
    request: Request, workspace_id: str, path: str = Query(...)
) -> FileContent:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    absolute = _resolve_within_workspace(workspace, path)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    data = await ssh_host.read_file(absolute)
    try:
        return FileContent(path=path, content=data.decode("utf-8"), size=len(data), binary=False)
    except UnicodeDecodeError:
        return FileContent(path=path, content="", size=len(data), binary=True)


class FileWrite(BaseModel):
    path: str
    content: str


@router.put("/workspaces/{workspace_id}/file", status_code=204)
async def write_workspace_file(request: Request, workspace_id: str, body: FileWrite) -> None:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    absolute = _resolve_within_workspace(workspace, body.path)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    await ssh_host.write_file(absolute, body.content.encode("utf-8"))


class WorkspaceDiff(BaseModel):
    is_git_repo: bool
    diff: str


@router.get("/workspaces/{workspace_id}/diff")
async def get_workspace_diff(
    request: Request, workspace_id: str, path: str = Query(default="")
) -> WorkspaceDiff:
    """Unstaged `git diff` for the workspace (or one path within it). Returns
    ``is_git_repo: False`` rather than an error when the workspace root isn't a Git
    repository yet — WSP-002 owns `git init`/status/commit/branch/log.
    """
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)

    status_argv = ["git", "-C", workspace.root_path, "rev-parse", "--is-inside-work-tree"]
    status_chunks = [c async for c in ssh_host.exec_stream(status_argv)]
    if status_chunks[-1].exit_status != 0:
        return WorkspaceDiff(is_git_repo=False, diff="")

    diff_argv = (
        ["git", "-C", workspace.root_path, "diff", "--", path]
        if path
        else [
            "git",
            "-C",
            workspace.root_path,
            "diff",
        ]
    )
    diff_chunks = [c async for c in ssh_host.exec_stream(diff_argv)]
    diff_text = "".join(c.data for c in diff_chunks if c.stream == "stdout")
    return WorkspaceDiff(is_git_repo=True, diff=diff_text)
