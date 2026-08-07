-- Persisted model-load lifecycle records (LP-009, SPEC/API_CONTRACT.md /language/instances).

CREATE TABLE model_instances (
    id TEXT PRIMARY KEY,
    provider_config_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    native_instance_id TEXT,
    status TEXT NOT NULL DEFAULT 'loading'
        CHECK (status IN ('loading', 'loaded', 'unloading', 'unloaded', 'failed')),
    settings_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_model_instances_provider ON model_instances(provider_config_id);
