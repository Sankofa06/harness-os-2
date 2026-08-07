-- Workspaces: a folder on a Host that filesystem/shell operations are scoped to
-- (SPEC/WORKSPACES_ARTIFACTS.md, WSP-001).

CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES hosts(id),
    root_path TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
