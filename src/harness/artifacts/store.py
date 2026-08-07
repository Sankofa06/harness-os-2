"""Content-addressed disk blob store for artifact bytes (ART-001).

Sync file I/O, matching `harness.core.secrets.EncryptedFileBackend`'s precedent for
small-to-medium local files — artifact content is written/read once per call, not
streamed, so there's no async benefit to justify aiofiles or a thread-pool wrapper
here. Content-addressing (path derived from the sha256 of the bytes) means two
artifacts with identical content automatically share one file, and writes are
idempotent — storing the same bytes twice is a no-op the second time.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from harness.core.errors import NotFoundError


class ArtifactBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path_for(self, sha256: str) -> Path:
        return self._root / sha256[:2] / sha256

    def put(self, data: bytes) -> tuple[str, int]:
        """Store `data`, returning (sha256, size). Idempotent for identical bytes."""
        sha256 = hashlib.sha256(data).hexdigest()
        path = self._path_for(sha256)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return sha256, len(data)

    def get(self, sha256: str) -> bytes:
        path = self._path_for(sha256)
        if not path.exists():
            raise NotFoundError(f"artifact blob not found: {sha256}")
        return path.read_bytes()
