-- Adds 'workflow' to artifacts.type's allowed values (CRE-003,
-- SPEC/CREATIVE_COMPUTE.md: ComfyUI workflow JSON is stored as an Artifact,
-- by reference, never inlined into context). SQLite has no ALTER TABLE
-- support for CHECK constraints, so the table is rebuilt: create the new
-- shape, copy every row, drop the old table, rename the new one into place.

CREATE TABLE artifacts_new (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN (
        'code_file', 'image', 'video', 'screenshot', 'document', 'diff', 'patch',
        'log', 'test_report', 'plan', 'benchmark_report', 'arbitrary_file', 'workflow'
    )),
    mime_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    run_id TEXT,
    session_id TEXT,
    workspace_id TEXT REFERENCES workspaces(id),
    source_path TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO artifacts_new SELECT * FROM artifacts;

DROP TABLE artifacts;

ALTER TABLE artifacts_new RENAME TO artifacts;
