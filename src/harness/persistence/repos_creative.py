"""Repository for discovered Stability Matrix installations (CRE-001)."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import CreativeInstallation
from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.persistence.db import Database
from harness.providers.creative.discovery import DiscoveredInstallation


class CreativeInstallationRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def replace_for_scan(
        self,
        host_id: str,
        data_dir: str,
        platform: str,
        installations: list[DiscoveredInstallation],
    ) -> list[CreativeInstallation]:
        """Replace every installation previously recorded for this
        (host, data_dir) scan — a rescan always reflects the full current
        state of that Data directory, so a since-uninstalled package must not
        linger (mirrors MCP-001's `McpIndexRepo.replace_for_server`).
        """
        await self._db.execute(
            "DELETE FROM creative_installations WHERE host_id = :host_id AND data_dir = :data_dir",
            {"host_id": host_id, "data_dir": data_dir},
        )
        created = []
        for installation in installations:
            row_id = new_id("cre")
            await self._db.execute(
                "INSERT INTO creative_installations (id, host_id, data_dir, package_name, "
                "display_name, library_path, launch_command, python_version, family_id, "
                "family_display_name, family_group, platform, supported_platforms, "
                "platform_supported, raw_metadata) VALUES (:id, :host_id, :data_dir, "
                ":package_name, :display_name, :library_path, :launch_command, "
                ":python_version, :family_id, :family_display_name, :family_group, "
                ":platform, :supported_platforms, :platform_supported, :raw_metadata)",
                {
                    "id": row_id,
                    "host_id": host_id,
                    "data_dir": data_dir,
                    "package_name": installation.package_name,
                    "display_name": installation.display_name,
                    "library_path": installation.library_path,
                    "launch_command": installation.launch_command,
                    "python_version": installation.python_version,
                    "family_id": installation.family_id,
                    "family_display_name": installation.family_display_name,
                    "family_group": installation.family_group,
                    "platform": platform,
                    "supported_platforms": json.dumps(list(installation.supported_platforms)),
                    "platform_supported": int(installation.platform_supported),
                    "raw_metadata": json.dumps(installation.raw),
                },
            )
            created.append(await self.get(row_id))
        return created

    async def get(self, installation_id: str) -> CreativeInstallation:
        row = await self._db.fetch_one(
            "SELECT * FROM creative_installations WHERE id = :id", {"id": installation_id}
        )
        if row is None:
            raise NotFoundError(f"creative installation not found: {installation_id}")
        return _installation(row)

    async def list(self, *, host_id: str | None = None) -> list[CreativeInstallation]:
        if host_id is not None:
            rows = await self._db.fetch_all(
                "SELECT * FROM creative_installations WHERE host_id = :host_id "
                "ORDER BY display_name",
                {"host_id": host_id},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM creative_installations ORDER BY display_name"
            )
        return [_installation(r) for r in rows]


def _installation(row: Any) -> CreativeInstallation:
    return CreativeInstallation(
        id=row["id"],
        host_id=row["host_id"],
        data_dir=row["data_dir"],
        package_name=row["package_name"],
        display_name=row["display_name"],
        library_path=row["library_path"],
        launch_command=row["launch_command"],
        python_version=row["python_version"],
        family_id=row["family_id"],
        family_display_name=row["family_display_name"],
        family_group=row["family_group"],
        platform=row["platform"],
        supported_platforms=json.loads(row["supported_platforms"]),
        platform_supported=bool(row["platform_supported"]),
        raw_metadata=json.loads(row["raw_metadata"]),
        created_at=row["created_at"],
    )
