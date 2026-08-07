"""A real local SSH server, used to test SSHHost against actual SSH protocol
exchanges rather than mocks (TESTING/TEST_STRATEGY.md "local SSH container/server
fixture where practical"). Password auth only, ephemeral host key, loopback-only.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncssh

TEST_USERNAME = "harness-test"
TEST_PASSWORD = "harness-test-password"


class _TestSSHServer(asyncssh.SSHServer):
    def begin_auth(self, username: str) -> bool:
        return True

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        return username == TEST_USERNAME and password == TEST_PASSWORD


async def _handle_process(process: asyncssh.SSHServerProcess[str]) -> None:
    if not process.command:
        process.exit(1)
        return
    proc = await asyncio.create_subprocess_shell(
        process.command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def pump(src: asyncio.StreamReader, dst: asyncssh.SSHWriter[str]) -> None:
        while True:
            chunk = await src.read(4096)
            if not chunk:
                return
            dst.write(chunk.decode(errors="replace"))

    assert proc.stdout is not None
    assert proc.stderr is not None
    await asyncio.gather(pump(proc.stdout, process.stdout), pump(proc.stderr, process.stderr))
    exit_code = await proc.wait()
    process.exit(exit_code)


@dataclass
class RunningSSHServer:
    port: int
    host_key_fingerprint: str
    username: str = TEST_USERNAME
    password: str = TEST_PASSWORD


async def start_test_ssh_server() -> tuple[asyncssh.SSHAcceptor, RunningSSHServer]:
    host_key = asyncssh.generate_private_key("ssh-ed25519")
    server = await asyncssh.listen(
        "127.0.0.1",
        0,
        server_factory=_TestSSHServer,
        server_host_keys=[host_key],
        process_factory=_handle_process,
        sftp_factory=asyncssh.SFTPServer,
    )
    port = server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    fingerprint = host_key.get_fingerprint()
    return server, RunningSSHServer(port=port, host_key_fingerprint=fingerprint)
