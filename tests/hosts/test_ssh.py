import asyncio

import pytest

from harness.core.domain import Host
from harness.core.errors import PermissionDeniedError, ProviderError
from harness.hosts.ssh import SSHHost
from tests.hosts.fixtures import RunningSSHServer


def _host(
    server: RunningSSHServer,
    *,
    fingerprint: str | None = None,
    workspace_roots: list[str] | None = None,
) -> Host:
    return Host(
        id="host_test",
        display_name="test-ssh",
        kind="ssh",
        hostname="127.0.0.1",
        port=server.port,
        username=server.username,
        known_host_fingerprint=fingerprint,
        workspace_roots=workspace_roots or [],
    )


def _ssh_host(
    server: RunningSSHServer,
    *,
    fingerprint: str | None = None,
    workspace_roots: list[str] | None = None,
) -> SSHHost:
    return SSHHost(
        _host(server, fingerprint=fingerprint, workspace_roots=workspace_roots),
        password=server.password,
    )


@pytest.mark.asyncio
async def test_connection_returns_host_key_fingerprint(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server)
    fingerprint = await ssh_host.test_connection()
    assert fingerprint == ssh_server.host_key_fingerprint


@pytest.mark.asyncio
async def test_pinned_fingerprint_mismatch_is_rejected(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server, fingerprint="SHA256:not-the-real-fingerprint")
    with pytest.raises(PermissionDeniedError):
        await ssh_host.test_connection()


@pytest.mark.asyncio
async def test_pinned_fingerprint_match_succeeds(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server, fingerprint=ssh_server.host_key_fingerprint)
    fingerprint = await ssh_host.test_connection()
    assert fingerprint == ssh_server.host_key_fingerprint


@pytest.mark.asyncio
async def test_wrong_password_rejected(ssh_server: RunningSSHServer) -> None:
    host = _host(ssh_server)
    ssh_host = SSHHost(host, password="definitely-wrong")
    with pytest.raises(ProviderError):
        await ssh_host.test_connection()


@pytest.mark.asyncio
async def test_exec_stream_captures_stdout_and_exit_status(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server)
    chunks = [c async for c in ssh_host.exec_stream(["echo", "hello from harness"])]
    stdout = "".join(c.data for c in chunks if c.stream == "stdout")
    assert "hello from harness" in stdout
    final = chunks[-1]
    assert final.done is True
    assert final.exit_status == 0


@pytest.mark.asyncio
async def test_exec_stream_captures_stderr_and_nonzero_exit(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server)
    chunks = [c async for c in ssh_host.exec_stream(["sh", "-c", "echo oops 1>&2; exit 3"])]
    stderr = "".join(c.data for c in chunks if c.stream == "stderr")
    assert "oops" in stderr
    assert chunks[-1].exit_status == 3


@pytest.mark.asyncio
async def test_exec_stream_quotes_arguments_safely(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server)
    # An argument containing shell metacharacters must be treated as literal data,
    # never executed — proves argv is quoted rather than string-concatenated.
    dangerous = "hello; touch /tmp/should-not-exist-from-injection && echo pwned"
    chunks = [c async for c in ssh_host.exec_stream(["echo", dangerous])]
    stdout = "".join(c.data for c in chunks if c.stream == "stdout")
    assert dangerous in stdout
    assert "pwned" not in stdout.replace(dangerous, "")


@pytest.mark.asyncio
async def test_exec_stream_respects_cwd(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server, workspace_roots=["/tmp"])
    chunks = [c async for c in ssh_host.exec_stream(["pwd"], cwd="/tmp")]
    stdout = "".join(c.data for c in chunks if c.stream == "stdout")
    assert stdout.strip() == "/tmp"


@pytest.mark.asyncio
async def test_exec_stream_cwd_outside_workspace_roots_rejected(
    ssh_server: RunningSSHServer,
) -> None:
    ssh_host = _ssh_host(ssh_server, workspace_roots=["/tmp/allowed"])
    with pytest.raises(PermissionDeniedError):
        async for _ in ssh_host.exec_stream(["pwd"], cwd="/etc"):
            pass


@pytest.mark.asyncio
async def test_exec_stream_can_be_canceled(ssh_server: RunningSSHServer) -> None:
    ssh_host = _ssh_host(ssh_server)

    async def consume() -> list:
        return [c async for c in ssh_host.exec_stream(["sleep", "30"])]

    task = asyncio.ensure_future(consume())
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_sftp_write_read_list_move_delete_round_trip(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    ssh_host = _ssh_host(ssh_server, workspace_roots=[str(tmp_path)])
    base = str(tmp_path)
    file_path = f"{base}/greeting.txt"

    await ssh_host.write_file(file_path, b"hello sftp")
    assert await ssh_host.read_file(file_path) == b"hello sftp"

    entries = await ssh_host.list_dir(base)
    assert any(e.name == "greeting.txt" and not e.is_dir for e in entries)

    moved_path = f"{base}/renamed.txt"
    await ssh_host.move(file_path, moved_path)
    assert await ssh_host.read_file(moved_path) == b"hello sftp"

    await ssh_host.delete(moved_path)
    entries_after = await ssh_host.list_dir(base)
    assert not any(e.name == "renamed.txt" for e in entries_after)


@pytest.mark.asyncio
async def test_mkdir_creates_nested_directories(ssh_server: RunningSSHServer, tmp_path) -> None:
    ssh_host = _ssh_host(ssh_server, workspace_roots=[str(tmp_path)])
    nested = f"{tmp_path}/a/b/c"
    await ssh_host.mkdir(nested)
    entries = await ssh_host.list_dir(f"{tmp_path}/a/b")
    assert any(e.name == "c" and e.is_dir for e in entries)


@pytest.mark.asyncio
async def test_read_file_with_no_workspace_roots_fails_closed(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    ssh_host = _ssh_host(ssh_server)  # no workspace_roots configured at all
    with pytest.raises(PermissionDeniedError):
        await ssh_host.read_file(f"{tmp_path}/anything.txt")


@pytest.mark.asyncio
async def test_read_file_outside_workspace_roots_rejected(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    ssh_host = _ssh_host(ssh_server, workspace_roots=[f"{tmp_path}/allowed"])
    with pytest.raises(PermissionDeniedError):
        await ssh_host.read_file(f"{tmp_path}/other/secret.txt")


@pytest.mark.asyncio
async def test_write_file_traversal_outside_root_rejected(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    (tmp_path / "allowed").mkdir()
    ssh_host = _ssh_host(ssh_server, workspace_roots=[str(tmp_path / "allowed")])
    # Lexically normalizes to a path outside the allowed root before any I/O.
    traversal_path = f"{tmp_path}/allowed/../escaped.txt"
    with pytest.raises(PermissionDeniedError):
        await ssh_host.write_file(traversal_path, b"should never land")
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.asyncio
async def test_read_file_via_symlink_escaping_root_rejected(
    ssh_server: RunningSSHServer, tmp_path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    escape_link = allowed / "escape.txt"
    escape_link.symlink_to(secret)

    ssh_host = _ssh_host(ssh_server, workspace_roots=[str(allowed)])
    # Lexically the path is inside `allowed/`, but it resolves (via symlink) outside
    # it — only the SFTP-realpath-resolved second check catches this.
    with pytest.raises(PermissionDeniedError):
        await ssh_host.read_file(str(escape_link))
