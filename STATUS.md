# STATUS.md — Current State

_Last updated: 2026-08-06_

## Current milestone
Milestones 1 (kernel), 2 (control plane), and 3 (language compute) are all fully
done. Milestone 4 (execution) is in progress: HOST-001 (SSH agentless adapter) is
done — `SSHHost` (asyncssh-based) does test-connection/exec-stream/cancel/sftp
read-write-list-move-delete against a real local SSH server in tests (not mocks),
with explicit fingerprint pinning (no known_hosts file) and argv quoting (no shell
injection, proven by a regression test). `POST /hosts/{id}/test` exercises this live.

## Active task
None in flight. Next up per `TASKS.md`: HOST-002 (path safety — workspace roots,
canonicalization, traversal rejection).

## Completed milestones
- Phase 1: full spec-kit reading pass (all `SPEC/`, `ADR/`, `BUILD/`, `TESTING/`,
  `CONFIG/`, `MARKETING/` files).
- Phase 2: control files created (`TASKS.md`, `STATUS.md`, `DECISIONS.md`,
  `TEST_MATRIX.md`).
- Phase 3: repository scaffolded — Python package (`uv`, Python 3.12), web package
  (Vite + React + TS + Vitest + Playwright), CI skeleton, `.gitignore`,
  `.env.example`, `README.md`, `CONTRIBUTING.md`, `LICENSE` placeholder.
- Phase 4: vertical slice built and verified. All 14 architectural-proof items from
  the build brief are demonstrated:
  1. Harness server starts (`harness serve`).
  2. SQLite initializes and migrates (kernel schema).
  3. `/api/v1/health` works.
  4. Event bus works (in-process pub/sub with filters).
  5. WebSocket client receives a real event (`/api/v1/events`, tested both via
     `TestClient` and a live browser WS connection).
  6. Language-provider adapter interface exists (`LanguageProvider`, capability
     levels L0–L5).
  7. A deterministic fake provider streams a response through that interface.
  8. A Contact can be created (API + persisted).
  9. A Session can be created.
  10. A message invokes the Contact via `@mention` routing.
  11. A Run and binding snapshot are persisted (5-level precedence resolved and
      recorded in `binding_snapshots`).
  12. The Context Compiler reports its token budget (`context.compiled` event +
      budget report; bootstrap stays under the 4K target in tests).
  13. The WebUI displays the conversation (proven with a live Playwright run against
      the real server, not just mocked component tests).
  14. The TUI displays the same conversation through the API only (Textual app using
      a plain HTTP client, no direct DB/runtime access).
- Milestone 1 (kernel), completed beyond the vertical slice: SEC-001 secrets
  abstraction (keyring/encrypted-file/env backends, `/secrets/*`) and JOB-001 job
  engine (cancelable async jobs, persisted state machine, `job.*` events, `/jobs/*`).
- Milestone 2 (control plane), fully done: CP-001 uniform control-plane descriptor
  (`ControlPlaneDescriptor`/`describe()`, reflected in `/capabilities`); CP-002
  JSON-Schema settings system (`SettingsSchema`/`validate_settings`, namespaced
  `common`/`provider.<name>`, passthrough opt-in); CP-003 persisted language-provider
  configuration (`/language/providers*`, distinct from the in-memory adapter
  registry); CP-004 host registry (`/hosts*`, capability model from
  SPEC/HOSTS_AND_NODE.md, `host_capabilities` table).

## Known failures
None functionally. 163/163 backend tests pass, 2/2 web unit tests pass, 1/1 Playwright
e2e test passes. `ruff check`, `ruff format --check`, and `mypy --strict` are clean on
`src/harness`. `eslint`, `vitest`, and `tsc -b && vite build` are clean on `web/`.
Cosmetic: some test runs emit a `PytestUnhandledThreadExceptionWarning` from an
aiosqlite background thread racing pytest-asyncio's event-loop teardown in
short-lived tests; it does not affect pass/fail status and is a known aiosqlite/
asyncio interaction, not an application bug.

## Blockers
None.

## Architectural decisions made during implementation
See `DECISIONS.md` for the full list (D-001 through D-023). Notable ones affecting
what's built so far:
- D-003/D-004: SQLAlchemy async + plain SQL migrations, schema grows incrementally
  per subsystem milestone rather than all at once.
- D-005: bearer-token auth with loopback trust by default.
- D-006: heuristic token estimator (~1 token/4 chars), pluggable for real tokenizers
  later.
- D-011: `Role` carries a system prompt only; the "role" binding-precedence level is
  a defined no-op until a real use case needs role-level model defaults.
- D-012: the WebUI's API client is hand-written for the vertical slice; `WEB-011`
  will replace it with an OpenAPI-generated client.
- D-013: CORS is enabled by default for the Vite dev server origin only.
- D-014: license selection is deferred to the project owner (placeholder in place).

## What is NOT yet built
HOST-002's path-safety layer (SSHHost itself has no workspace-root enforcement yet —
it will execute/read/write anywhere the SSH user can), Workspaces (WSP-001/002:
`/workspaces*`, git operations), the Tool registry/lifecycle and permission engine
(TOOL-001/002, PERM-001), Artifacts (ART-001), MCP/skills, creative compute,
analytics/benchmarks, the Node daemon, the rest of the WebUI (graph/compute/models/
creative/assets/analytics/approvals views, full three-panel IA, context meter,
accessibility audit), TUI feature completion, demo mode content, screenshot
automation, GitHub Pages site, and marketing copy. These are tracked as their own
`TASKS.md` entries and proceed in dependency order per `BUILD/IMPLEMENTATION_PLAN.md`.

## Exact commands to run the currently working application

Backend API server:
```bash
uv sync
uv run harness serve --host 127.0.0.1 --port 4096
```

TUI client (in a second terminal, after the server is running):
```bash
uv run harness tui --api http://127.0.0.1:4096
```

WebUI dev server (in a third terminal):
```bash
cd web
npm install
npm run dev   # http://127.0.0.1:5173, talks to the API via CORS
```

Deterministic seeded/demo boot (no real credentials or network calls, in-memory DB):
```bash
HARNESS_DEMO_MODE=1 uv run harness serve
```

Test suites:
```bash
uv run pytest tests -q                      # backend: 163 tests
cd web && npm run test                      # web unit: vitest
cd web && npx playwright test               # web e2e (needs both servers running)
```
