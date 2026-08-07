-- Skill packages + per-session activations (SKL-001, SPEC/CONTEXT_COMPILER.md
-- "Skill format", SPEC/DATA_MODEL.md's `skills`/`skill_activations`). Metadata
-- (name/description/activation_hints/estimated_tokens/required_capabilities)
-- is always cheap; `body` (the SKILL.md content) is the expensive part and is
-- only ever returned by activation, mirroring MCP-001's compact-index/lazy-
-- schema split for MCP tools.

CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    activation_hints TEXT NOT NULL DEFAULT '[]',
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    required_capabilities TEXT NOT NULL DEFAULT '[]',
    scripts TEXT NOT NULL DEFAULT '[]',
    reference_docs TEXT NOT NULL DEFAULT '[]',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE skill_activations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (session_id, skill_id)
);
