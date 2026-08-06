from pathlib import Path

import pytest

from harness.core.errors import NotFoundError, UnsupportedCapabilityError
from harness.core.secrets import EncryptedFileBackend, EnvBackend, SecretStore


def test_env_backend_reads_process_environment(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_TEST_SECRET", "shh")
    backend = EnvBackend()
    assert backend.get("HARNESS_TEST_SECRET") == "shh"


def test_env_backend_missing_raises_not_found(monkeypatch) -> None:
    monkeypatch.delenv("HARNESS_TEST_MISSING", raising=False)
    backend = EnvBackend()
    with pytest.raises(NotFoundError):
        backend.get("HARNESS_TEST_MISSING")


def test_env_backend_is_read_only() -> None:
    backend = EnvBackend()
    with pytest.raises(UnsupportedCapabilityError):
        backend.set("X", "y")


def test_encrypted_file_backend_round_trip(tmp_path) -> None:
    pytest.importorskip("cryptography")
    backend = EncryptedFileBackend(tmp_path)
    backend.set("api-key", "super-secret-value")
    assert backend.get("api-key") == "super-secret-value"

    # The value must not appear in plaintext anywhere on disk.
    raw = (tmp_path / "secrets.enc").read_bytes()
    assert b"super-secret-value" not in raw

    backend.delete("api-key")
    with pytest.raises(NotFoundError):
        backend.get("api-key")


def test_secret_store_test_returns_false_for_missing(tmp_path) -> None:
    store = SecretStore(tmp_path)
    assert store.test("env", "HARNESS_TEST_DEFINITELY_MISSING") is False


def test_secret_store_unknown_kind_raises(tmp_path: Path) -> None:
    store = SecretStore(tmp_path)
    with pytest.raises(UnsupportedCapabilityError):
        store.get("bogus", "x")
