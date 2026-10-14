-- Creative generation presets (CRE-007, SPEC/CREATIVE_COMPUTE.md "Creative
-- Profile"). Explicitly not a Persona -- a separate table, separate
-- selection path, never routed through contacts/personas.

CREATE TABLE creative_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    engine_selector TEXT NOT NULL,
    workflow_artifact_id TEXT REFERENCES artifacts(id),
    checkpoint TEXT,
    vae TEXT,
    loras TEXT NOT NULL DEFAULT '[]',
    sampler TEXT,
    scheduler TEXT,
    settings TEXT NOT NULL DEFAULT '{}',
    prefer_loaded_asset INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
