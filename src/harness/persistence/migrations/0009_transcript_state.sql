-- Structured, protected session facts that must survive Context Compiler history
-- trimming (CTX-003, SPEC/CONTEXT_COMPILER.md "never summarize away" list).

CREATE TABLE session_transcript_state (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    unresolved_requirements_json TEXT NOT NULL DEFAULT '[]',
    current_plan TEXT NOT NULL DEFAULT '',
    changed_files_json TEXT NOT NULL DEFAULT '[]',
    failing_tests_json TEXT NOT NULL DEFAULT '[]',
    permission_decisions_json TEXT NOT NULL DEFAULT '[]',
    rolling_summary TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
