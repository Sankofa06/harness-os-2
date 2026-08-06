"""Repositories for persisted provider configuration and hosts (CP-003/CP-004)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import Host, ProviderConfig
from harness.core.errors import ConflictError, NotFoundError
from harness.persistence.db import Database


class ProviderConfigRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, config: ProviderConfig) -> ProviderConfig:
        if await self._db.fetch_one(
            "SELECT id FROM providers WHERE display_name = :n", {"n": config.display_name}
        ):
            raise ConflictError(f"provider display name already exists: {config.display_name}")
        await self._db.execute(
            "INSERT INTO providers (id, type, display_name, base_url, secret_ref_id, "
            "enabled, settings_json) VALUES (:id, :type, :display_name, :base_url, "
            ":secret_ref_id, :enabled, :settings_json)",
            {
                "id": config.id,
                "type": config.type,
                "display_name": config.display_name,
                "base_url": config.base_url,
                "secret_ref_id": config.secret_ref_id,
                "enabled": int(config.enabled),
                "settings_json": json.dumps(config.settings),
            },
        )
        return config

    async def get(self, provider_id: str) -> ProviderConfig:
        row = await self._db.fetch_one(
            "SELECT * FROM providers WHERE id = :id", {"id": provider_id}
        )
        if row is None:
            raise NotFoundError(f"provider not found: {provider_id}")
        return _provider_config(row)

    async def list(self) -> list[ProviderConfig]:
        rows = await self._db.fetch_all("SELECT * FROM providers ORDER BY display_name")
        return [_provider_config(r) for r in rows]

    async def delete(self, provider_id: str) -> None:
        await self.get(provider_id)
        await self._db.execute("DELETE FROM providers WHERE id = :id", {"id": provider_id})

    async def set_enabled(self, provider_id: str, enabled: bool) -> ProviderConfig:
        await self.get(provider_id)
        await self._db.execute(
            "UPDATE providers SET enabled = :e, updated_at = datetime('now') WHERE id = :id",
            {"e": int(enabled), "id": provider_id},
        )
        return await self.get(provider_id)


class HostRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, host: Host) -> Host:
        if await self._db.fetch_one(
            "SELECT id FROM hosts WHERE display_name = :n", {"n": host.display_name}
        ):
            raise ConflictError(f"host display name already exists: {host.display_name}")
        await self._db.execute(
            "INSERT INTO hosts (id, display_name, kind, hostname, port, username, "
            "secret_ref_id, workspace_roots_json, known_host_fingerprint) VALUES "
            "(:id, :display_name, :kind, :hostname, :port, :username, :secret_ref_id, "
            ":workspace_roots_json, :known_host_fingerprint)",
            {
                "id": host.id,
                "display_name": host.display_name,
                "kind": host.kind,
                "hostname": host.hostname,
                "port": host.port,
                "username": host.username,
                "secret_ref_id": host.secret_ref_id,
                "workspace_roots_json": json.dumps(host.workspace_roots),
                "known_host_fingerprint": host.known_host_fingerprint,
            },
        )
        await self._set_capabilities(host.id, host.capabilities)
        return host

    async def _set_capabilities(self, host_id: str, capabilities: list[str]) -> None:
        for capability in capabilities:
            await self._db.execute(
                "INSERT INTO host_capabilities (host_id, capability) VALUES (:h, :c)",
                {"h": host_id, "c": capability},
            )

    async def get(self, host_id: str) -> Host:
        row = await self._db.fetch_one("SELECT * FROM hosts WHERE id = :id", {"id": host_id})
        if row is None:
            raise NotFoundError(f"host not found: {host_id}")
        return await self._hydrate(row)

    async def delete(self, host_id: str) -> None:
        await self.get(host_id)
        await self._db.execute("DELETE FROM hosts WHERE id = :id", {"id": host_id})

    async def set_capabilities(self, host_id: str, capabilities: list[str]) -> Host:
        await self.get(host_id)
        await self._db.execute("DELETE FROM host_capabilities WHERE host_id = :id", {"id": host_id})
        await self._set_capabilities(host_id, capabilities)
        return await self.get(host_id)

    # Defined last: a method named `list` shadows the builtin generic `list[...]` for
    # any annotation written after it elsewhere in this class body (mypy semantic
    # analysis quirk with `from __future__ import annotations`).
    async def list(self) -> list[Host]:
        rows = await self._db.fetch_all("SELECT * FROM hosts ORDER BY display_name")
        return [await self._hydrate(r) for r in rows]

    async def _hydrate(self, row: Any) -> Host:
        capability_rows = await self._db.fetch_all(
            "SELECT capability FROM host_capabilities WHERE host_id = :id ORDER BY capability",
            {"id": row["id"]},
        )
        return Host(
            id=row["id"],
            display_name=row["display_name"],
            kind=row["kind"],
            hostname=row["hostname"],
            port=row["port"],
            username=row["username"],
            secret_ref_id=row["secret_ref_id"],
            workspace_roots=json.loads(row["workspace_roots_json"]),
            known_host_fingerprint=row["known_host_fingerprint"],
            capabilities=[c["capability"] for c in capability_rows],
        )


def _provider_config(row: Any) -> ProviderConfig:
    return ProviderConfig(
        id=row["id"],
        type=row["type"],
        display_name=row["display_name"],
        base_url=row["base_url"],
        secret_ref_id=row["secret_ref_id"],
        enabled=bool(row["enabled"]),
        settings=json.loads(row["settings_json"]),
    )
