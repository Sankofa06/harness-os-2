-- Artifacts: typed first-class content references + a content-addressed blob
-- store (ART-001, SPEC/WORKSPACES_ARTIFACTS.md). The blob itself lives on disk,
-- keyed by sha256 (harness.artifacts.store.ArtifactBlobStore); this table is
-- metadata only, kept small so listing/filtering artifacts never touches content.

CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN (
        'code_file', 'image', 'video', 'screenshot', 'document', 'diff', 'patch',
        'log', 'test_report', 'plan', 'benchmark_report', 'arbitrary_file'
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
