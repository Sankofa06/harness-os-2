"""Workspace endpoints (WSP-001/WSP-002, SPEC/WORKSPACES_ARTIFACTS.md,
SPEC/API_CONTRACT.md).

A Workspace pins a folder on a Host that filesystem/shell operations are scoped to.
Two containment layers apply to every path a caller supplies: the Host's own
``workspace_roots`` (enforced inside ``SSHHost``, HOST-002) and — narrower — the
Workspace's own ``root_path``, enforced here so one Workspace can never read or write
across into a sibling Workspace that happens to share the same Host.

Only SSH hosts are supported so far, matching HOST-001/HOST-002; other Host kinds
raise a validation error rather than silently no-op'ing (AGENTS.md: adapters declare
capabilities honestly, never fake parity).

Git operations (WSP-002) run through structured `exec_stream` argv — the same
injection-safe pattern HOST-001 established — never a shell-interpolated command
string.
"""

from __future__ import annotations

import posixpath
from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from harness.api.auth import require_auth
from harness.core.app import Application
from harness.core.domain import Workspace
from harness.core.errors import ProviderError, ValidationFailedError
from harness.core.ids import new_id
from harness.hosts.path_safety import canonicalize_and_check
from harness.hosts.resolve import build_ssh_host
from harness.hosts.ssh import ExecChunk, SftpEntry, SSHHost

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


async def _run_git(ssh_host: SSHHost, root_path: str, args: list[str]) -> tuple[int, str, str]:
    """Run `git -C <root_path> <args...>` via structured argv exec and collect its
    output. Returns (exit_status, stdout, stderr); never raises on a nonzero exit —
    callers decide what a failing git invocation means (not a repo, merge conflict,
    nothing to commit, ...).
    """
    argv = ["git", "-C", root_path, *args]
    chunks: list[ExecChunk] = [c async for c in ssh_host.exec_stream(argv)]
    stdout = "".join(c.data for c in chunks if c.stream == "stdout")
    stderr = "".join(c.data for c in chunks if c.stream == "stderr")
    exit_status = chunks[-1].exit_status if chunks[-1].exit_status is not None else -1
    return exit_status, stdout, stderr


async def _is_git_repo(ssh_host: SSHHost, root_path: str) -> bool:
    exit_status, _, _ = await _run_git(ssh_host, root_path, ["rev-parse", "--is-inside-work-tree"])
    return exit_status == 0


class WorkspaceDiff(BaseModel):
    is_git_repo: bool
    diff: str


@router.get("/workspaces/{workspace_id}/diff")
async def get_workspace_diff(
    request: Request, workspace_id: str, path: str = Query(default="")
) -> WorkspaceDiff:
    """Unstaged `git diff` for the workspace (or one path within it). Returns
    ``is_git_repo: False`` rather than an error when the workspace root isn't a Git
    repository yet. Also available (identical behavior) as `GET .../git/diff`.
    """
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    return await _diff(ssh_host, workspace.root_path, path)


async def _diff(ssh_host: SSHHost, root_path: str, path: str) -> WorkspaceDiff:
    if not await _is_git_repo(ssh_host, root_path):
        return WorkspaceDiff(is_git_repo=False, diff="")
    args = ["diff", "--", path] if path else ["diff"]
    _, stdout, _ = await _run_git(ssh_host, root_path, args)
    return WorkspaceDiff(is_git_repo=True, diff=stdout)


class GitInitResult(BaseModel):
    ok: bool
    output: str


@router.post("/workspaces/{workspace_id}/git/init")
async def git_init(request: Request, workspace_id: str) -> GitInitResult:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    exit_status, stdout, stderr = await _run_git(ssh_host, workspace.root_path, ["init"])
    if exit_status != 0:
        raise ProviderError(f"git init failed: {stderr.strip() or stdout.strip()}")
    return GitInitResult(ok=True, output=stdout)


@router.get("/workspaces/{workspace_id}/git/diff")
async def git_diff(
    request: Request, workspace_id: str, path: str = Query(default="")
) -> WorkspaceDiff:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    return await _diff(ssh_host, workspace.root_path, path)


class GitStatusEntry(BaseModel):
    status: str  # raw two-character porcelain status code, e.g. " M", "??", "A "
    path: str


class GitStatus(BaseModel):
    is_git_repo: bool
    branch: str | None = None
    entries: list[GitStatusEntry] = Field(default_factory=list)


@router.get("/workspaces/{workspace_id}/git/status")
async def git_status(request: Request, workspace_id: str) -> GitStatus:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    if not await _is_git_repo(ssh_host, workspace.root_path):
        return GitStatus(is_git_repo=False)

    _, branch_stdout, _ = await _run_git(
        ssh_host, workspace.root_path, ["branch", "--show-current"]
    )
    _, status_stdout, _ = await _run_git(
        ssh_host, workspace.root_path, ["status", "--porcelain=v1"]
    )
    entries = [
        GitStatusEntry(status=line[:2], path=line[3:])
        for line in status_stdout.splitlines()
        if line
    ]
    return GitStatus(is_git_repo=True, branch=branch_stdout.strip() or None, entries=entries)


class GitAddRequest(BaseModel):
    paths: list[str] = Field(min_length=1)


@router.post("/workspaces/{workspace_id}/git/add")
async def git_add(request: Request, workspace_id: str, body: GitAddRequest) -> GitInitResult:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    exit_status, stdout, stderr = await _run_git(
        ssh_host, workspace.root_path, ["add", "--", *body.paths]
    )
    if exit_status != 0:
        raise ProviderError(f"git add failed: {stderr.strip() or stdout.strip()}")
    return GitInitResult(ok=True, output=stdout)


class GitCommitRequest(BaseModel):
    message: str
    author_name: str | None = None
    author_email: str | None = None


class GitCommitResult(BaseModel):
    ok: bool
    commit_hash: str | None = None
    output: str


@router.post("/workspaces/{workspace_id}/git/commit")
async def git_commit(
    request: Request, workspace_id: str, body: GitCommitRequest
) -> GitCommitResult:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)

    config_args = []
    if body.author_name:
        config_args += ["-c", f"user.name={body.author_name}"]
    if body.author_email:
        config_args += ["-c", f"user.email={body.author_email}"]
    exit_status, stdout, stderr = await _run_git(
        ssh_host, workspace.root_path, [*config_args, "commit", "-m", body.message]
    )
    if exit_status != 0:
        return GitCommitResult(ok=False, output=stderr.strip() or stdout.strip())

    _, hash_stdout, _ = await _run_git(ssh_host, workspace.root_path, ["rev-parse", "HEAD"])
    return GitCommitResult(ok=True, commit_hash=hash_stdout.strip() or None, output=stdout)


class GitBranch(BaseModel):
    name: str
    current: bool


@router.get("/workspaces/{workspace_id}/git/branch")
async def git_list_branches(request: Request, workspace_id: str) -> list[GitBranch]:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    _, stdout, _ = await _run_git(ssh_host, workspace.root_path, ["branch", "--list"])
    branches = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        current = line.startswith("*")
        branches.append(GitBranch(name=line.lstrip("* ").strip(), current=current))
    return branches


class GitBranchCreateRequest(BaseModel):
    name: str
    checkout: bool = False


@router.post("/workspaces/{workspace_id}/git/branch")
async def git_create_branch(
    request: Request, workspace_id: str, body: GitBranchCreateRequest
) -> GitInitResult:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    args = ["checkout", "-b", body.name] if body.checkout else ["branch", body.name]
    exit_status, stdout, stderr = await _run_git(ssh_host, workspace.root_path, args)
    if exit_status != 0:
        raise ProviderError(f"git branch failed: {stderr.strip() or stdout.strip()}")
    return GitInitResult(ok=True, output=stdout)


class GitLogEntry(BaseModel):
    commit_hash: str
    author: str
    date: str
    subject: str


_LOG_FORMAT = "%H%x1f%an%x1f%ad%x1f%s"


@router.get("/workspaces/{workspace_id}/git/log")
async def git_log(
    request: Request, workspace_id: str, limit: int = Query(default=20, ge=1, le=500)
) -> list[GitLogEntry]:
    app = _app(request)
    workspace = await app.workspaces.get(workspace_id)
    ssh_host = await _ssh_host_for(app, workspace.host_id)
    if not await _is_git_repo(ssh_host, workspace.root_path):
        return []
    exit_status, stdout, _ = await _run_git(
        ssh_host,
        workspace.root_path,
        ["log", f"-n{limit}", f"--pretty=format:{_LOG_FORMAT}", "--date=iso-strict"],
    )
    if exit_status != 0:
        # An empty repo with no commits yet: `git log` fails rather than printing
        # nothing, so this is expected and not an error worth surfacing.
        return []
    entries = []
    for line in stdout.splitlines():
        if not line:
            continue
        commit_hash, author, date, subject = line.split("\x1f", 3)
        entries.append(
            GitLogEntry(commit_hash=commit_hash, author=author, date=date, subject=subject)
        )
    return entries
