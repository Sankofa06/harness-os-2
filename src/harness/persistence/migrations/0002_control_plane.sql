-- Control-plane configuration: persisted language-provider instances and hosts
-- (SPEC/DATA_MODEL.md, SPEC/PROVIDER_MATRIX.md, SPEC/HOSTS_AND_NODE.md).

CREATE TABLE providers (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    base_url TEXT,
    secret_ref_id TEXT REFERENCES secret_refs(id),
    enabled INTEGER NOT NULL DEFAULT 1,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE hosts (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('ssh', 'node', 'local')),
    hostname TEXT,
    port INTEGER,
    username TEXT,
    secret_ref_id TEXT REFERENCES secret_refs(id),
    workspace_roots_json TEXT NOT NULL DEFAULT '[]',
    known_host_fingerprint TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE host_capabilities (
    host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    PRIMARY KEY (host_id, capability)
);
