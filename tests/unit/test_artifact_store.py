import pytest

from harness.artifacts.store import ArtifactBlobStore
from harness.core.errors import NotFoundError


def test_put_returns_sha256_and_size(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path)
    sha256, size = store.put(b"hello artifact")
    assert size == len(b"hello artifact")
    assert len(sha256) == 64  # hex-encoded sha256 digest


def test_put_is_idempotent_for_identical_content(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path)
    sha256_a, _ = store.put(b"same bytes")
    sha256_b, _ = store.put(b"same bytes")
    assert sha256_a == sha256_b
    # Only one blob file exists on disk despite two put() calls.
    blob_files = list(tmp_path.rglob("*"))
    blob_files = [p for p in blob_files if p.is_file()]
    assert len(blob_files) == 1


def test_get_returns_the_stored_bytes(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path)
    sha256, _ = store.put(b"round trip me")
    assert store.get(sha256) == b"round trip me"


def test_get_missing_blob_raises_not_found(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path)
    with pytest.raises(NotFoundError):
        store.get("0" * 64)


def test_different_content_produces_different_blobs(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path)
    sha256_a, _ = store.put(b"content a")
    sha256_b, _ = store.put(b"content b")
    assert sha256_a != sha256_b
    assert store.get(sha256_a) == b"content a"
    assert store.get(sha256_b) == b"content b"
