-- Creative asset catalog (CRE-006, SPEC/CREATIVE_COMPUTE.md "Creative
-- assets"). `creative_assets` is the deduplicated-by-content-hash identity
-- of one model file; `creative_asset_locations` is every (host, path) a
-- scan has found that same content at, so a checkpoint shared across
-- multiple hosts/engines is recorded once with multiple locations rather
-- than once per place it happens to sit on disk.

CREATE TABLE creative_assets (
    id TEXT PRIMARY KEY,
    asset_kind TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    canonical_filename TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE creative_asset_locations (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES creative_assets(id) ON DELETE CASCADE,
    host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (host_id, path)
);

CREATE INDEX idx_creative_asset_locations_asset_id ON creative_asset_locations(asset_id);
