-- Per-session activated capabilities (MCP-002, SPEC/MCP_SKILLS_TOOLS.md): which
-- native-tool or MCP-tool schemas a session's `tools.describe` calls have pulled
-- into context so far. Only (kind, ref) is stored — the full schema is always
-- resolved fresh from its source (ToolRegistry or mcp_tool_index) at compile
-- time, so a later change to a tool's schema, or its removal, is reflected
-- immediately rather than going stale here.

CREATE TABLE session_activated_capabilities (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('native_tool', 'mcp_tool')),
    ref TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (session_id, kind, ref)
);
