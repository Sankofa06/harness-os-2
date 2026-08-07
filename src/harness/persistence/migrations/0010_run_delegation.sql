-- Delegation edges between Runs (AGT-006): a Run created by another Run's
-- agents.delegate tool call records its parent, so a session's orchestration
-- graph can be reconstructed from the runs table alone.

ALTER TABLE runs ADD COLUMN parent_run_id TEXT REFERENCES runs(id);
