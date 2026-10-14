"""Repository for the deduplicated creative asset catalog (CRE-006)."""

from __future__ import annotations

from typing import Any

from harness.core.domain import CreativeAsset, CreativeAssetLocation
from harness.core.errors import NotFoundError
from harness.core.ids import new_id
from harness.persistence.db import Database
from harness.providers.creative.assets import ScannedAssetFile


class CreativeAssetRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def record_scan(
        self, host_id: str, scanned: list[ScannedAssetFile]
    ) -> list[CreativeAsset]:
        """Dedupe ``scanned`` files by content hash into `creative_assets`,
        and record each one's (host, path) as a `creative_asset_locations`
        row -- this is what makes a checkpoint shared across hosts/engines
        appear once with multiple locations rather than once per path.
        A location already on file for this (host, path) is updated in
        place, so a rescan after a file changed in-place points it at the
        new content's asset rather than leaving it pointing at stale
        content.
        """
        assets: list[CreativeAsset] = []
        seen_asset_ids: set[str] = set()
        for file in scanned:
            asset = await self._get_or_create_asset(file)
            await self._db.execute(
                "INSERT INTO creative_asset_locations (id, asset_id, host_id, path) "
                "VALUES (:id, :asset_id, :host_id, :path) "
                "ON CONFLICT (host_id, path) DO UPDATE SET "
                "asset_id = excluded.asset_id, discovered_at = datetime('now')",
                {
                    "id": new_id("astloc"),
                    "asset_id": asset.id,
                    "host_id": host_id,
                    "path": file.path,
                },
            )
            if asset.id not in seen_asset_ids:
                seen_asset_ids.add(asset.id)
                assets.append(asset)
        return assets

    async def _get_or_create_asset(self, file: ScannedAssetFile) -> CreativeAsset:
        row = await self._db.fetch_one(
            "SELECT * FROM creative_assets WHERE content_hash = :content_hash",
            {"content_hash": file.content_hash},
        )
        if row is not None:
            return _asset(row)
        asset_id = new_id("asset")
        await self._db.execute(
            "INSERT INTO creative_assets (id, asset_kind, content_hash, size_bytes, "
            "canonical_filename) VALUES (:id, :asset_kind, :content_hash, :size_bytes, "
            ":canonical_filename)",
            {
                "id": asset_id,
                "asset_kind": file.asset_kind,
                "content_hash": file.content_hash,
                "size_bytes": file.size_bytes,
                "canonical_filename": file.filename,
            },
        )
        return await self.get(asset_id)

    async def get(self, asset_id: str) -> CreativeAsset:
        row = await self._db.fetch_one(
            "SELECT * FROM creative_assets WHERE id = :id", {"id": asset_id}
        )
        if row is None:
            raise NotFoundError(f"creative asset not found: {asset_id}")
        return _asset(row)

    async def find_by_filename(self, filename: str) -> list[CreativeAsset]:
        """CRE-009: provenance's checkpoint-hash lookup. Returns every
        cataloged asset recorded under this exact filename -- more than
        one is a real possibility (different files sharing a name), which
        is for the caller to treat as ambiguous, not for this method to
        resolve.
        """
        rows = await self._db.fetch_all(
            "SELECT * FROM creative_assets WHERE canonical_filename = :filename ORDER BY id",
            {"filename": filename},
        )
        return [_asset(r) for r in rows]

    async def list_locations(self, asset_id: str) -> list[CreativeAssetLocation]:
        rows = await self._db.fetch_all(
            "SELECT * FROM creative_asset_locations WHERE asset_id = :asset_id "
            "ORDER BY discovered_at, id",
            {"asset_id": asset_id},
        )
        return [_location(r) for r in rows]

    async def list(self, *, asset_kind: str | None = None) -> list[CreativeAsset]:
        if asset_kind is not None:
            rows = await self._db.fetch_all(
                "SELECT * FROM creative_assets WHERE asset_kind = :asset_kind "
                "ORDER BY canonical_filename, id",
                {"asset_kind": asset_kind},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM creative_assets ORDER BY canonical_filename, id"
            )
        return [_asset(r) for r in rows]


def _asset(row: Any) -> CreativeAsset:
    return CreativeAsset(
        id=row["id"],
        asset_kind=row["asset_kind"],
        content_hash=row["content_hash"],
        size_bytes=row["size_bytes"],
        canonical_filename=row["canonical_filename"],
        created_at=row["created_at"],
    )


def _location(row: Any) -> CreativeAssetLocation:
    return CreativeAssetLocation(
        id=row["id"],
        asset_id=row["asset_id"],
        host_id=row["host_id"],
        path=row["path"],
        discovered_at=row["discovered_at"],
    )
