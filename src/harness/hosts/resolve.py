"""Resolves a persisted Host + its secret reference into a connectable SSHHost.

Kept separate from `hosts.ssh` (which stays free of persistence/secret-store
dependencies) and narrow on its inputs (repo + store, not the whole Application) so
it's easy to test and reuse from any caller that already has those two objects.
"""

from __future__ import annotations

from harness.core.domain import Host
from harness.core.errors import ValidationFailedError
from harness.core.secrets import SecretStore
from harness.hosts.ssh import SSHHost
from harness.persistence.repos import SecretRefRepo

_PEM_MARKER = "-----BEGIN"


async def build_ssh_host(
    host: Host, secret_refs: SecretRefRepo, secret_store: SecretStore
) -> SSHHost:
    if host.kind != "ssh":
        raise ValidationFailedError(f"host {host.id} is not an SSH host (kind={host.kind})")

    password: str | None = None
    private_key: str | None = None
    if host.secret_ref_id:
        secret_ref = await secret_refs.get(host.secret_ref_id)
        value = secret_store.get(secret_ref.kind, secret_ref.target)
        if value.lstrip().startswith(_PEM_MARKER):
            private_key = value
        else:
            password = value

    return SSHHost(host, password=password, private_key=private_key)
