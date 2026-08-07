-- Native tool registry lifecycle records (TOOL-001, SPEC/MCP_SKILLS_TOOLS.md).

CREATE TABLE tool_runs (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL DEFAULT '{}',
    permission_class TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed', 'denied', 'pending_approval')
    ),
    result_json TEXT,
    error TEXT,
    workspace_id TEXT REFERENCES workspaces(id),
    session_id TEXT REFERENCES sessions(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
