import pytest

from harness.core.errors import PermissionDeniedError
from harness.hosts.path_safety import canonicalize_and_check, resolve_and_check


def test_path_inside_root_is_allowed() -> None:
    assert canonicalize_and_check("/workspace/proj/file.py", ["/workspace"]) == (
        "/workspace/proj/file.py"
    )


def test_path_equal_to_root_is_allowed() -> None:
    assert canonicalize_and_check("/workspace", ["/workspace"]) == "/workspace"


def test_dotdot_traversal_out_of_root_is_rejected() -> None:
    with pytest.raises(PermissionDeniedError):
        canonicalize_and_check("/workspace/../etc/passwd", ["/workspace"])


def test_dotdot_traversal_that_stays_inside_root_is_allowed() -> None:
    # "/workspace/a/../b" normalizes to "/workspace/b", which is still contained.
    assert canonicalize_and_check("/workspace/a/../b", ["/workspace"]) == "/workspace/b"


def test_sibling_directory_with_shared_prefix_is_rejected() -> None:
    # "/workspace-evil" must not be treated as contained in "/workspace" just because
    # it shares a string prefix.
    with pytest.raises(PermissionDeniedError):
        canonicalize_and_check("/workspace-evil/file.py", ["/workspace"])


def test_relative_path_is_rejected() -> None:
    with pytest.raises(PermissionDeniedError):
        canonicalize_and_check("relative/path.txt", ["/workspace"])


def test_no_roots_configured_fails_closed() -> None:
    with pytest.raises(PermissionDeniedError):
        canonicalize_and_check("/anything", [])


def test_root_with_trailing_slash_normalizes_correctly() -> None:
    assert canonicalize_and_check("/workspace/file.py", ["/workspace/"]) == ("/workspace/file.py")


def test_matches_any_of_multiple_configured_roots() -> None:
    roots = ["/workspace/a", "/workspace/b"]
    assert canonicalize_and_check("/workspace/b/file.py", roots) == "/workspace/b/file.py"
    with pytest.raises(PermissionDeniedError):
        canonicalize_and_check("/workspace/c/file.py", roots)


class _FakeSftp:
    def __init__(self, real_path: str) -> None:
        self._real_path = real_path

    async def realpath(self, path: str) -> str:
        return self._real_path


@pytest.mark.asyncio
async def test_resolve_and_check_allows_symlink_resolving_inside_root() -> None:
    sftp = _FakeSftp("/workspace/real-target.txt")
    result = await resolve_and_check(sftp, "/workspace/link.txt", ["/workspace"])
    assert result == "/workspace/real-target.txt"


@pytest.mark.asyncio
async def test_resolve_and_check_rejects_symlink_resolving_outside_root() -> None:
    # Lexically "/workspace/link.txt" looks fine; the SFTP-resolved real path escapes.
    sftp = _FakeSftp("/etc/passwd")
    with pytest.raises(PermissionDeniedError):
        await resolve_and_check(sftp, "/workspace/link.txt", ["/workspace"])


@pytest.mark.asyncio
async def test_resolve_and_check_rejects_lexically_bad_path_before_touching_sftp() -> None:
    class _ExplodingSftp:
        async def realpath(self, path: str) -> str:
            raise AssertionError("must not reach the network for a lexically bad path")

    with pytest.raises(PermissionDeniedError):
        await resolve_and_check(_ExplodingSftp(), "/etc/passwd", ["/workspace"])
