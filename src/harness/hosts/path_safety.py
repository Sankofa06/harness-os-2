"""Workspace-root containment for remote paths (HOST-002, SPEC/HOSTS_AND_NODE.md).

Two layers, because path resolution happens on the *remote* host:

1. Lexical containment: normalize `.`/`..` segments (POSIX semantics, no I/O) and
   reject anything that doesn't stay under a configured root. Catches the common
   `../../etc/passwd` case before any network round trip.
2. Remote-resolved containment (file operations only, where an SFTP client is
   already open): ask the remote host to resolve the *real* path via SFTP
   `realpath()` and re-check containment against that. Closes the gap where a
   symlink inside an allowed root points outside it — lexical checking alone can't
   see that, since it never touches the filesystem.

`resolve_and_check` requires callers to already hold an SFTP client so this module
has no dependency on `SSHHost`/`asyncssh` connection setup itself.
"""

from __future__ import annotations

import posixpath
from typing import Protocol

from harness.core.errors import PermissionDeniedError


class _SftpRealpath(Protocol):
    async def realpath(self, path: str) -> str: ...


def _normalize_root(root: str) -> str:
    normalized = posixpath.normpath(root)
    return normalized if normalized == "/" else normalized.rstrip("/")


def _is_contained(candidate: str, root: str) -> bool:
    return candidate == root or candidate.startswith(root + "/")


def canonicalize_and_check(path: str, roots: list[str]) -> str:
    """Lexically normalize ``path`` and verify it falls under one of ``roots``.

    Returns the normalized path. Raises PermissionDeniedError if no configured root
    contains it, or if no roots are configured at all (fail closed).
    """
    if not roots:
        raise PermissionDeniedError("no workspace roots configured for this host")
    if not posixpath.isabs(path):
        raise PermissionDeniedError(f"relative paths are not allowed: {path}")

    normalized = posixpath.normpath(path)
    for root in roots:
        if _is_contained(normalized, _normalize_root(root)):
            return normalized
    raise PermissionDeniedError(f"path {path} is outside all configured workspace roots")


async def resolve_and_check(sftp: _SftpRealpath, path: str, roots: list[str]) -> str:
    """Lexically check ``path``, then re-check its remote-resolved real path.

    Defends against a symlink inside an allowed root pointing outside it. The
    lexical pass runs first so an obviously-escaping request never even reaches the
    network.
    """
    canonicalize_and_check(path, roots)
    real_path = await sftp.realpath(path)
    return canonicalize_and_check(real_path, roots)
