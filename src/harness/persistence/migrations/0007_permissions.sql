-- Permission policy overrides + decision audit log (PERM-001,
-- SPEC/SECURITY_PRIVACY.md).

CREATE TABLE permission_policies (
    permission_class TEXT PRIMARY KEY CHECK (permission_class IN (
        'read', 'write', 'execute', 'network', 'git', 'process',
        'model_lifecycle', 'creative_generation', 'training', 'destructive'
    )),
    policy TEXT NOT NULL CHECK (policy IN ('allow', 'ask', 'deny')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE permission_decisions (
    id TEXT PRIMARY KEY,
    tool_run_id TEXT NOT NULL REFERENCES tool_runs(id),
    permission_class TEXT NOT NULL,
    policy TEXT NOT NULL CHECK (policy IN ('allow', 'ask', 'deny')),
    outcome TEXT NOT NULL CHECK (outcome IN ('allow', 'deny')),
    decided_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
