"""Shared workspace resolution + git helpers (WSP-001/002).

Kept separate from the API routes (`harness.api.routes.workspaces`) and the native
tools (`harness.tools.workspace_tools`, TOOL-002) so both callers share one
path-containment and git-invocation implementation rather than risking the two
subtly diverging — path safety is exactly the kind of logic that must not exist in
two slightly different copies.
"""

from __future__ import annotations

import posixpath

from harness.core.domain import Workspace
from harness.core.secrets import SecretStore
from harness.hosts.path_safety import canonicalize_and_check
from harness.hosts.resolve import build_ssh_host
from harness.hosts.ssh import ExecChunk, SSHHost
from harness.persistence.repos import SecretRefRepo
from harness.persistence.repos_control_plane import HostRepo


async def ssh_host_for_host_id(
    host_id: str,
    hosts: HostRepo,
    secret_refs: SecretRefRepo,
    secret_store: SecretStore,
) -> SSHHost:
    host = await hosts.get(host_id)
    return await build_ssh_host(host, secret_refs, secret_store)


async def ssh_host_for_workspace(
    workspace: Workspace,
    hosts: HostRepo,
    secret_refs: SecretRefRepo,
    secret_store: SecretStore,
) -> SSHHost:
    return await ssh_host_for_host_id(workspace.host_id, hosts, secret_refs, secret_store)


def resolve_within_workspace(workspace: Workspace, relative_path: str) -> str:
    """Join a caller-supplied relative path onto the workspace root and verify the
    result still falls under that root — the workspace-level containment layer, on
    top of (not instead of) the Host-level check `SSHHost` performs on every call.
    """
    absolute = posixpath.normpath(posixpath.join(workspace.root_path, relative_path.lstrip("/")))
    return canonicalize_and_check(absolute, [workspace.root_path])


async def run_git(ssh_host: SSHHost, root_path: str, args: list[str]) -> tuple[int, str, str]:
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


async def is_git_repo(ssh_host: SSHHost, root_path: str) -> bool:
    exit_status, _, _ = await run_git(ssh_host, root_path, ["rev-parse", "--is-inside-work-tree"])
    return exit_status == 0
