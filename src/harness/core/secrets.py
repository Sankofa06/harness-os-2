"""Secret store abstraction (SPEC/SECURITY_PRIVACY.md).

Backend chain: OS keyring -> encrypted local file -> environment variable reference.
Each backend is optional; `keyring`/`cryptography` are lazy-imported so a missing
extra degrades that one backend rather than crashing the server (SPEC/ARCHITECTURE.md
failure-isolation rule). Secret *values* never round-trip through this module's
callers into logs, events, or API responses — only `SecretRef` metadata (kind/target)
does, which is not sensitive.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

from harness.core.errors import NotFoundError, UnsupportedCapabilityError

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

_KEYRING_SERVICE = "harness-os"


class SecretBackend(ABC):
    kind: str

    @abstractmethod
    def get(self, target: str) -> str: ...

    @abstractmethod
    def set(self, target: str, value: str) -> None: ...

    @abstractmethod
    def delete(self, target: str) -> None: ...

    def test(self, target: str) -> bool:
        """Return True if the backend can resolve ``target`` without raising."""
        try:
            self.get(target)
            return True
        except Exception:
            return False


class EnvBackend(SecretBackend):
    """Reads secrets from process environment variables. Always available."""

    kind = "env"

    def get(self, target: str) -> str:
        value = os.environ.get(target)
        if value is None:
            raise NotFoundError(f"environment variable not set: {target}")
        return value

    def set(self, target: str, value: str) -> None:
        raise UnsupportedCapabilityError(
            "env backend is read-only; set the variable in the process environment"
        )

    def delete(self, target: str) -> None:
        raise UnsupportedCapabilityError("env backend is read-only")


class KeyringBackend(SecretBackend):
    """Delegates to the OS keychain via the `keyring` package (optional extra)."""

    kind = "keyring"

    def _module(self) -> ModuleType:
        try:
            import keyring
        except ImportError as exc:
            raise UnsupportedCapabilityError(
                "OS keyring backend requires the 'secrets' extra (pip install "
                "harness-os[secrets]) and a functioning OS keychain"
            ) from exc
        return cast(ModuleType, keyring)

    def get(self, target: str) -> str:
        value: str | None = self._module().get_password(_KEYRING_SERVICE, target)
        if value is None:
            raise NotFoundError(f"no keyring entry for: {target}")
        return value

    def set(self, target: str, value: str) -> None:
        self._module().set_password(_KEYRING_SERVICE, target, value)

    def delete(self, target: str) -> None:
        self._module().delete_password(_KEYRING_SERVICE, target)


class EncryptedFileBackend(SecretBackend):
    """A local Fernet-encrypted key/value store, keyed by an on-disk key file.

    Both files are written with owner-only permissions. This is a local-machine
    protection (SPEC/SECURITY_PRIVACY.md "encrypted local secret file"), not
    protection against an attacker with read access to the user's account.
    """

    kind = "file"

    def __init__(self, data_dir: Path) -> None:
        self._key_path = data_dir / "secret.key"
        self._store_path = data_dir / "secrets.enc"
        self._data_dir = data_dir

    def _fernet(self) -> Fernet:
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise UnsupportedCapabilityError(
                "encrypted-file backend requires the 'secrets' extra "
                "(pip install harness-os[secrets])"
            ) from exc
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._key_path.exists():
            self._key_path.write_bytes(Fernet.generate_key())
            os.chmod(self._key_path, 0o600)
        return Fernet(self._key_path.read_bytes())

    def _load(self) -> dict[str, str]:
        import json

        if not self._store_path.exists():
            return {}
        token = self._store_path.read_bytes()
        plaintext = self._fernet().decrypt(token)
        return dict(json.loads(plaintext))

    def _save(self, data: dict[str, str]) -> None:
        import json

        token = self._fernet().encrypt(json.dumps(data).encode())
        self._store_path.write_bytes(token)
        os.chmod(self._store_path, 0o600)

    def get(self, target: str) -> str:
        value = self._load().get(target)
        if value is None:
            raise NotFoundError(f"no encrypted-file entry for: {target}")
        return value

    def set(self, target: str, value: str) -> None:
        data = self._load()
        data[target] = value
        self._save(data)

    def delete(self, target: str) -> None:
        data = self._load()
        data.pop(target, None)
        self._save(data)


class SecretStore:
    """Resolves a secret value given its ``kind``/``target``, chosen by the caller."""

    def __init__(self, data_dir: Path) -> None:
        self._backends: dict[str, SecretBackend] = {
            "env": EnvBackend(),
            "keyring": KeyringBackend(),
            "file": EncryptedFileBackend(data_dir),
        }

    def backend(self, kind: str) -> SecretBackend:
        try:
            return self._backends[kind]
        except KeyError:
            raise UnsupportedCapabilityError(f"unknown secret backend: {kind}") from None

    def get(self, kind: str, target: str) -> str:
        return self.backend(kind).get(target)

    def set(self, kind: str, target: str, value: str) -> None:
        self.backend(kind).set(target, value)

    def test(self, kind: str, target: str) -> bool:
        return self.backend(kind).test(target)
