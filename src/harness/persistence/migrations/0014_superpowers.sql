-- Superpower bundle toggles (SKL-002, SPEC/MCP_SKILLS_TOOLS.md "Superpower
-- bundles"): a bundle's membership (which tool/skill names it bundles) is
-- fixed, declarative Python data (`harness.skills.superpowers`), not stored
-- here — this table only remembers which bundle ids are currently toggled
-- on. Absence of a row means disabled (the default); permission policies
-- are untouched by this table entirely ("permissions stay explicit").

CREATE TABLE superpower_toggles (
    bundle_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
