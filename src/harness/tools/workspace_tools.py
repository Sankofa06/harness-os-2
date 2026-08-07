"""Workspace-scoped native tools (TOOL-002): filesystem, shell, git.

Each tool's `parameters_schema` requires `workspace_id` as an explicit JSON-Schema
property — a `ToolHandler` (TOOL-001) only ever receives the schema-validated
`arguments` dict, not out-of-band context, so resolving *which* Workspace/Host to
act on has to come from the arguments themselves. Path containment reuses
`harness.workspaces.service` (WSP-001/002) exactly — the same two-layer check the
HTTP workspace endpoints use, not a second copy of it.

Permission classes follow SPEC/SECURITY_PRIVACY.md's taxonomy: filesystem reads are
`read`, filesystem writes are `write`, `shell_exec` is `execute`, and every git
operation — including read-only ones like status/diff/log — is `git`, its own
dedicated class rather than reusing `read`/`write` (SPEC lists `git` as one of the
ten classes precisely so the whole git surface gets one policy knob). All of these
default to `ask` except plain filesystem reads (see `harness.core.permissions.
DEFAULT_POLICIES`), so registering these tools does not silently grant
write/execute/git access — PERM-001 must be configured (or a human must approve
each call) before they do anything.
"""

from __future__ import annotations

from typing import Any

from harness.core.domain import Workspace
from harness.core.secrets import SecretStore
from harness.hosts.ssh import SSHHost
from harness.persistence.repos import SecretRefRepo
from harness.persistence.repos_control_plane import HostRepo
from harness.persistence.repos_workspaces import WorkspaceRepo
from harness.tools.base import ToolDefinition
from harness.tools.registry import ToolRegistry
from harness.workspaces.service import (
    is_git_repo,
    resolve_within_workspace,
    run_git,
    ssh_host_for_workspace,
)

_WORKSPACE_ID_PROPERTY = {"workspace_id": {"type": "string"}}
_LOG_FORMAT = "%H%x1f%an%x1f%ad%x1f%s"


def register_workspace_tools(
    registry: ToolRegistry,
    workspaces: WorkspaceRepo,
    hosts: HostRepo,
    secret_refs: SecretRefRepo,
    secret_store: SecretStore,
) -> None:
    async def _ssh_host(arguments: dict[str, Any]) -> tuple[Workspace, SSHHost]:
        workspace = await workspaces.get(arguments["workspace_id"])
        ssh_host = await ssh_host_for_workspace(workspace, hosts, secret_refs, secret_store)
        return workspace, ssh_host

    async def fs_read_file(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        absolute = resolve_within_workspace(workspace, arguments["path"])
        data = await ssh_host.read_file(absolute)
        try:
            return {"content": data.decode("utf-8"), "size": len(data), "binary": False}
        except UnicodeDecodeError:
            return {"content": "", "size": len(data), "binary": True}

    async def fs_write_file(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        absolute = resolve_within_workspace(workspace, arguments["path"])
        content = arguments["content"]
        await ssh_host.write_file(absolute, content.encode("utf-8"))
        return {"path": arguments["path"], "bytes_written": len(content.encode("utf-8"))}

    async def fs_list_dir(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        absolute = resolve_within_workspace(workspace, arguments.get("path", ""))
        entries = await ssh_host.list_dir(absolute)
        return {
            "entries": [
                {"name": e.name, "is_dir": e.is_dir, "size": e.size, "modified_at": e.modified_at}
                for e in entries
            ]
        }

    async def shell_exec(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        cwd = resolve_within_workspace(workspace, arguments.get("cwd", ""))
        chunks = [c async for c in ssh_host.exec_stream(arguments["argv"], cwd=cwd)]
        stdout = "".join(c.data for c in chunks if c.stream == "stdout")
        stderr = "".join(c.data for c in chunks if c.stream == "stderr")
        return {"stdout": stdout, "stderr": stderr, "exit_status": chunks[-1].exit_status}

    async def git_init(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        exit_status, stdout, stderr = await run_git(ssh_host, workspace.root_path, ["init"])
        return {"ok": exit_status == 0, "output": stdout if exit_status == 0 else stderr}

    async def git_status(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        if not await is_git_repo(ssh_host, workspace.root_path):
            return {"is_git_repo": False, "branch": None, "entries": []}
        _, branch_stdout, _ = await run_git(
            ssh_host, workspace.root_path, ["branch", "--show-current"]
        )
        _, status_stdout, _ = await run_git(
            ssh_host, workspace.root_path, ["status", "--porcelain=v1"]
        )
        entries = [
            {"status": line[:2], "path": line[3:]} for line in status_stdout.splitlines() if line
        ]
        return {
            "is_git_repo": True,
            "branch": branch_stdout.strip() or None,
            "entries": entries,
        }

    async def git_diff(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        if not await is_git_repo(ssh_host, workspace.root_path):
            return {"is_git_repo": False, "diff": ""}
        path = arguments.get("path", "")
        args = ["diff", "--", path] if path else ["diff"]
        _, stdout, _ = await run_git(ssh_host, workspace.root_path, args)
        return {"is_git_repo": True, "diff": stdout}

    async def git_add(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        exit_status, stdout, stderr = await run_git(
            ssh_host, workspace.root_path, ["add", "--", *arguments["paths"]]
        )
        return {"ok": exit_status == 0, "output": stdout if exit_status == 0 else stderr}

    async def git_commit(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        config_args = []
        if arguments.get("author_name"):
            config_args += ["-c", f"user.name={arguments['author_name']}"]
        if arguments.get("author_email"):
            config_args += ["-c", f"user.email={arguments['author_email']}"]
        exit_status, stdout, stderr = await run_git(
            ssh_host,
            workspace.root_path,
            [*config_args, "commit", "-m", arguments["message"]],
        )
        if exit_status != 0:
            return {"ok": False, "commit_hash": None, "output": stderr.strip() or stdout.strip()}
        _, hash_stdout, _ = await run_git(ssh_host, workspace.root_path, ["rev-parse", "HEAD"])
        return {"ok": True, "commit_hash": hash_stdout.strip() or None, "output": stdout}

    async def git_branch_list(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        _, stdout, _ = await run_git(ssh_host, workspace.root_path, ["branch", "--list"])
        branches = [
            {"name": line.lstrip("* ").strip(), "current": line.startswith("*")}
            for line in stdout.splitlines()
            if line.strip()
        ]
        return {"branches": branches}

    async def git_branch_create(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        checkout = arguments.get("checkout", False)
        args = ["checkout", "-b", arguments["name"]] if checkout else ["branch", arguments["name"]]
        exit_status, stdout, stderr = await run_git(ssh_host, workspace.root_path, args)
        return {"ok": exit_status == 0, "output": stdout if exit_status == 0 else stderr}

    async def git_log(arguments: dict[str, Any]) -> dict[str, Any]:
        workspace, ssh_host = await _ssh_host(arguments)
        if not await is_git_repo(ssh_host, workspace.root_path):
            return {"entries": []}
        limit = arguments.get("limit", 20)
        exit_status, stdout, _ = await run_git(
            ssh_host,
            workspace.root_path,
            ["log", f"-n{limit}", f"--pretty=format:{_LOG_FORMAT}", "--date=iso-strict"],
        )
        if exit_status != 0:
            return {"entries": []}
        entries = []
        for line in stdout.splitlines():
            if not line:
                continue
            commit_hash, author, date, subject = line.split("\x1f", 3)
            entries.append(
                {"commit_hash": commit_hash, "author": author, "date": date, "subject": subject}
            )
        return {"entries": entries}

    registry.register(
        ToolDefinition(
            name="fs_read_file",
            description="Read a text file inside a Workspace.",
            parameters_schema={
                "type": "object",
                "properties": {**_WORKSPACE_ID_PROPERTY, "path": {"type": "string"}},
                "required": ["workspace_id", "path"],
                "additionalProperties": False,
            },
            permission_class="read",
            handler=fs_read_file,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="fs_write_file",
            description="Write (create or overwrite) a text file inside a Workspace.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["workspace_id", "path", "content"],
                "additionalProperties": False,
            },
            permission_class="write",
            handler=fs_write_file,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="fs_list_dir",
            description="List a directory inside a Workspace.",
            parameters_schema={
                "type": "object",
                "properties": {**_WORKSPACE_ID_PROPERTY, "path": {"type": "string"}},
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="read",
            handler=fs_list_dir,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="shell_exec",
            description="Run a command (argv list, never a shell string) inside a "
            "Workspace, defaulting to its root directory.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "cwd": {"type": "string"},
                },
                "required": ["workspace_id", "argv"],
                "additionalProperties": False,
            },
            permission_class="execute",
            handler=shell_exec,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_init",
            description="git init a Workspace's root as a new repository.",
            parameters_schema={
                "type": "object",
                "properties": _WORKSPACE_ID_PROPERTY,
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_init,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_status",
            description="git status for a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": _WORKSPACE_ID_PROPERTY,
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_status,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_diff",
            description="git diff for a Workspace's repository (optionally scoped to one path).",
            parameters_schema={
                "type": "object",
                "properties": {**_WORKSPACE_ID_PROPERTY, "path": {"type": "string"}},
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_diff,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_add",
            description="git add one or more paths in a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
                "required": ["workspace_id", "paths"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_add,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_commit",
            description="git commit staged changes in a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "message": {"type": "string"},
                    "author_name": {"type": "string"},
                    "author_email": {"type": "string"},
                },
                "required": ["workspace_id", "message"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_commit,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_branch_list",
            description="List branches in a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": _WORKSPACE_ID_PROPERTY,
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_branch_list,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_branch_create",
            description="Create (and optionally check out) a branch in a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "name": {"type": "string"},
                    "checkout": {"type": "boolean"},
                },
                "required": ["workspace_id", "name"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_branch_create,
            workspace_scoped=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="git_log",
            description="Commit history for a Workspace's repository.",
            parameters_schema={
                "type": "object",
                "properties": {
                    **_WORKSPACE_ID_PROPERTY,
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["workspace_id"],
                "additionalProperties": False,
            },
            permission_class="git",
            handler=git_log,
            workspace_scoped=True,
        )
    )
