# STATUS.md — Current State

_Last updated: 2026-08-06_

## Current milestone
Phase 4 — vertical slice (architectural proof).

## Active task
SCAF-001 — Python monorepo scaffold.

## Completed milestones
- Phase 1: full spec-kit reading pass complete (all SPEC/, ADR/, BUILD/, TESTING/, CONFIG/, MARKETING/ files).
- Phase 2: control files created (TASKS.md, STATUS.md, DECISIONS.md, TEST_MATRIX.md).

## Known failures
None yet.

## Blockers
None.

## Architectural decisions made during implementation
See DECISIONS.md. Highlights: uv-managed Python 3.12 (D-001), SQLAlchemy 2 async + SQL migrations (D-003), incremental schema migrations per milestone (D-004), loopback-trust auth default (D-005), heuristic token estimator with pluggable interface (D-006).

## Exact commands to run the currently working application
Nothing runnable yet. Will be updated when the vertical slice boots.

Target commands (per DEPLOYMENT.md):
```bash
uv run harness serve --host 127.0.0.1 --port 4096
uv run harness tui --api http://127.0.0.1:4096
cd web && npm run dev   # WebUI dev server
```
