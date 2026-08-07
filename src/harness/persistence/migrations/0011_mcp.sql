-- Lazy MCP server registry + compact tool index (MCP-001,
-- SPEC/MCP_SKILLS_TOOLS.md). Full JSON schemas live only in
-- mcp_tool_index.schema_json, fetched separately on activation (MCP-002) —
-- everything else here is what the index needs to stay compact.

CREATE TABLE mcp_servers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    secret_ref_id TEXT REFERENCES secret_refs(id),
    enabled INTEGER NOT NULL DEFAULT 1,
    last_indexed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE mcp_tool_index (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    estimated_schema_tokens INTEGER NOT NULL DEFAULT 0,
    trust_class TEXT NOT NULL DEFAULT 'network',
    schema_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (server_id, tool_name)
);
