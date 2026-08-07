-- Discovered Stability Matrix installations (CRE-001,
-- SPEC/CREATIVE_COMPUTE.md). One row per package entry found in a scanned
-- Data directory's settings.json; `raw_metadata` preserves the full detected
-- entry so an unmatched ("unknown/custom") package still carries whatever
-- Stability Matrix itself recorded about it.

CREATE TABLE creative_installations (
    id TEXT PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    data_dir TEXT NOT NULL,
    package_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    library_path TEXT NOT NULL DEFAULT '',
    launch_command TEXT,
    python_version TEXT,
    family_id TEXT NOT NULL DEFAULT 'unknown',
    family_display_name TEXT NOT NULL DEFAULT 'Unknown/Custom',
    family_group TEXT NOT NULL DEFAULT 'unknown',
    platform TEXT NOT NULL,
    supported_platforms TEXT NOT NULL DEFAULT '[]',
    platform_supported INTEGER NOT NULL DEFAULT 0,
    raw_metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (host_id, data_dir, library_path)
);
