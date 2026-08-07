"""Agentless SSH host adapter (ADR 0002, SPEC/HOSTS_AND_NODE.md).

Remote coding works with standard SSH — no Harness install or daemon required on the
remote machine. Commands are never built by string-interpolating user input into a
shell line; argv lists are individually shell-quoted (`shlex.join`) before being sent
as the single command string the SSH protocol's exec channel carries (SSH has no
argv-array exec request type — quoting is the injection defense here, matching
AGENTS.md's "no shell string concatenation for SSH execution").
"""

from __future__ import annotations

import asyncio
import posixpath
import shlex
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import asyncssh

from harness.core.domain import Host
from harness.core.errors import PermissionDeniedError, ProviderError
from harness.hosts.path_safety import canonicalize_and_check, resolve_and_check


@dataclass
class ExecChunk:
    """One piece of streamed process output, or the final exit status."""

    stream: Literal["stdout", "stderr"] | None = None
    data: str = ""
    done: bool = False
    exit_status: int | None = None


@dataclass
class SftpEntry:
    name: str
    is_dir: bool
    size: int
    modified_at: float


class SSHHost:
    """One SSH connection target. Stateless between calls — each operation opens and
    closes its own connection, since Harness hosts are used intermittently rather than
    kept in a persistent session pool for this v1.

    Every file operation (and `exec_stream`'s ``cwd``, when given) is checked against
    ``host.workspace_roots`` before touching the network (HOST-002, SPEC/HOSTS_AND_
    NODE.md). File operations get a second, remote-resolved check via SFTP
    ``realpath()`` to catch a symlink inside an allowed root pointing outside it —
    something a purely lexical check can't see. Bare `exec_stream` calls with no
    ``cwd`` are intentionally unscoped: workspace roots bound *file* access, not
    general command execution (a separate permission, PermissionClass.EXECUTE).
    """

    def __init__(
        self,
        host: Host,
        *,
        password: str | None = None,
        private_key: str | None = None,
    ) -> None:
        if host.kind != "ssh":
            raise ValueError(f"not an SSH host: {host.id} (kind={host.kind})")
        if not host.hostname:
            raise ValueError(f"SSH host missing hostname: {host.id}")
        self._hostname = host.hostname
        self._port = host.port or 22
        self._username = host.username
        self._password = password
        self._client_keys = [asyncssh.import_private_key(private_key)] if private_key else None
        self._expected_fingerprint = host.known_host_fingerprint
        self._workspace_roots = host.workspace_roots

    async def _connect(self) -> asyncssh.SSHClientConnection:
        try:
            conn = await asyncssh.connect(
                self._hostname,
                port=self._port,
                username=self._username,
                password=self._password,
                client_keys=self._client_keys,
                known_hosts=None,  # verified manually below (pinned fingerprint model)
            )
        except (OSError, asyncssh.Error) as exc:
            raise ProviderError(f"ssh connection to {self._hostname} failed: {exc}") from exc

        server_key = conn.get_server_host_key()
        fingerprint = server_key.get_fingerprint() if server_key else None
        if self._expected_fingerprint is not None and fingerprint != self._expected_fingerprint:
            conn.close()
            raise PermissionDeniedError(
                f"SSH host key fingerprint mismatch for {self._hostname}: "
                f"expected {self._expected_fingerprint}, got {fingerprint}"
            )
        return conn

    async def test_connection(self) -> str:
        """Connect once and return the server's host-key fingerprint.

        Callers use this for trust-on-first-use: show the fingerprint to the user,
        then persist it as the Host's ``known_host_fingerprint`` before any real use.
        """
        conn = await self._connect()
        try:
            server_key = conn.get_server_host_key()
            fingerprint = server_key.get_fingerprint() if server_key else None
            if fingerprint is None:
                raise ProviderError(f"ssh server at {self._hostname} presented no host key")
            return str(fingerprint)
        finally:
            conn.close()

    async def exec_stream(
        self, argv: list[str], *, cwd: str | None = None
    ) -> AsyncIterator[ExecChunk]:
        """Run argv on the remote host, streaming stdout/stderr as they arrive."""
        command = shlex.join(argv)
        if cwd:
            cwd = canonicalize_and_check(cwd, self._workspace_roots)
            command = f"cd {shlex.quote(cwd)} && {command}"

        conn = await self._connect()
        try:
            async with conn.create_process(command) as process:
                async for chunk in _stream_process(process):
                    yield chunk
        except asyncssh.Error as exc:
            raise ProviderError(f"ssh exec failed: {exc}") from exc
        finally:
            conn.close()

    async def read_file(self, path: str) -> bytes:
        canonicalize_and_check(path, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await resolve_and_check(sftp, path, self._workspace_roots)
                async with sftp.open(path, "rb") as f:
                    return await f.read()
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp read failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def write_file(self, path: str, data: bytes) -> None:
        canonicalize_and_check(path, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                # A not-yet-existing file has no real path to resolve; check the
                # deepest already-existing ancestor instead so writes creating new
                # files still get a remote-resolved (symlink-aware) containment check.
                await resolve_and_check(
                    sftp, await _deepest_existing_ancestor(sftp, path), self._workspace_roots
                )
                async with sftp.open(path, "wb") as f:
                    await f.write(data)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp write failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def list_dir(self, path: str) -> list[SftpEntry]:
        canonicalize_and_check(path, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await resolve_and_check(sftp, path, self._workspace_roots)
                entries = []
                for name in await sftp.listdir(path):
                    if name in (".", ".."):
                        continue
                    attrs = await sftp.stat(f"{path.rstrip('/')}/{name}")
                    entries.append(
                        SftpEntry(
                            name=name,
                            is_dir=bool(attrs.type == asyncssh.FILEXFER_TYPE_DIRECTORY),
                            size=attrs.size or 0,
                            modified_at=float(attrs.mtime or 0),
                        )
                    )
                return entries
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp list failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def mkdir(self, path: str) -> None:
        canonicalize_and_check(path, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                # `path` itself may not exist yet (and makedirs can create several
                # new levels); check the deepest already-existing ancestor's real
                # path rather than `path` itself.
                await resolve_and_check(
                    sftp, await _deepest_existing_ancestor(sftp, path), self._workspace_roots
                )
                await sftp.makedirs(path, exist_ok=True)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp mkdir failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def move(self, src: str, dst: str) -> None:
        canonicalize_and_check(src, self._workspace_roots)
        canonicalize_and_check(dst, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await resolve_and_check(sftp, src, self._workspace_roots)
                await resolve_and_check(
                    sftp, await _deepest_existing_ancestor(sftp, dst), self._workspace_roots
                )
                await sftp.rename(src, dst)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp move failed for {src} -> {dst}: {exc}") from exc
        finally:
            conn.close()

    async def delete(self, path: str) -> None:
        canonicalize_and_check(path, self._workspace_roots)
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await resolve_and_check(sftp, path, self._workspace_roots)
                await sftp.remove(path)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp delete failed for {path}: {exc}") from exc
        finally:
            conn.close()


async def _deepest_existing_ancestor(sftp: asyncssh.SFTPClient, path: str) -> str:
    """Walk up from ``path`` to the nearest ancestor that actually exists remotely.

    Used to containment-check a not-yet-created path (a new file, a new directory
    tree) via its closest real anchor, since SFTP `realpath()` needs something that
    already exists.
    """
    candidate = path
    while True:
        if await sftp.exists(candidate):
            return candidate
        parent = posixpath.dirname(candidate)
        if parent == candidate:
            return candidate  # reached "/" without finding anything that exists
        candidate = parent


async def _stream_process(process: asyncssh.SSHClientProcess[str]) -> AsyncIterator[ExecChunk]:
    """Interleave stdout/stderr as they arrive, then yield the final exit status.

    Cancellation is standard asyncio generator cancellation: when the caller stops
    consuming (e.g. the driving task is cancelled by JobManager.cancel), CancelledError
    propagates out through this generator's `finally`, which cancels the two reader
    tasks; `exec_stream`'s own `finally: conn.close()` then tears down the SSH channel,
    which terminates the remote process.
    """
    queue: asyncio.Queue[ExecChunk | None] = asyncio.Queue()

    async def read_stream(
        reader: asyncssh.SSHReader[str], stream: Literal["stdout", "stderr"]
    ) -> None:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            await queue.put(ExecChunk(stream=stream, data=data))
        await queue.put(None)

    tasks = [
        asyncio.create_task(read_stream(process.stdout, "stdout")),
        asyncio.create_task(read_stream(process.stderr, "stderr")),
    ]
    finished = 0
    try:
        while finished < len(tasks):
            item = await queue.get()
            if item is None:
                finished += 1
                continue
            yield item
    finally:
        for task in tasks:
            task.cancel()

    await process.wait()
    yield ExecChunk(done=True, exit_status=process.exit_status)
