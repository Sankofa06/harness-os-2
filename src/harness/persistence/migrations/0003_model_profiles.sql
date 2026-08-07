-- Model profiles: reusable provider+model+settings+policy bundles (SPEC/PROVIDER_MATRIX.md
-- "Model profile" / "Placement policy").

CREATE TABLE model_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    provider_config_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    load_policy TEXT NOT NULL DEFAULT 'on_demand'
        CHECK (load_policy IN ('manual', 'always_loaded', 'on_demand')),
    placement_policy TEXT NOT NULL DEFAULT 'manual'
        CHECK (placement_policy IN (
            'manual', 'auto', 'prefer-loaded', 'prefer-local',
            'prefer-fastest', 'prefer-lowest-pressure', 'prefer-lowest-cost'
        )),
    tool_capability_policy TEXT NOT NULL DEFAULT 'inherit'
        CHECK (tool_capability_policy IN ('inherit', 'disabled', 'required')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
