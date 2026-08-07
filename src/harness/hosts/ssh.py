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
import shlex
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import asyncssh

from harness.core.domain import Host
from harness.core.errors import PermissionDeniedError, ProviderError


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
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp, sftp.open(path, "rb") as f:
                return await f.read()
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp read failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def write_file(self, path: str, data: bytes) -> None:
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp, sftp.open(path, "wb") as f:
                await f.write(data)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp write failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def list_dir(self, path: str) -> list[SftpEntry]:
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
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
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await sftp.makedirs(path, exist_ok=True)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp mkdir failed for {path}: {exc}") from exc
        finally:
            conn.close()

    async def move(self, src: str, dst: str) -> None:
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await sftp.rename(src, dst)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp move failed for {src} -> {dst}: {exc}") from exc
        finally:
            conn.close()

    async def delete(self, path: str) -> None:
        conn = await self._connect()
        try:
            async with conn.start_sftp_client() as sftp:
                await sftp.remove(path)
        except (OSError, asyncssh.SFTPError) as exc:
            raise ProviderError(f"sftp delete failed for {path}: {exc}") from exc
        finally:
            conn.close()


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
