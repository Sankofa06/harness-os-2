# STATUS.md — Current State

_Last updated: 2026-08-07_

## Current milestone
Milestones 1 (kernel), 2 (control plane), 3 (language compute), 4 (execution),
and 5 (agent runtime) are all fully done. Milestone 6 (MCP + Skills) is in
progress: MCP-001 (lazy MCP index), MCP-002 (capabilities.search +
activation), and SKL-001 (Skills) are all done — see the notes below. Next up
in Milestone 6 is SKL-002 (Superpower bundles).

SKL-001: `skills` (metadata + lazy `body`) and `skill_activations`
(session_id, skill_id) tables mirror MCP-001/MCP-002's compact-index/lazy-body
split. `POST /skills` registers a full package (name, description,
activation_hints, required_capabilities, scripts, reference_docs, body);
`GET /skills` never returns the body. Activation is exposed two ways sharing
one code path (`harness.skills.activation.activate_skill`): `POST /skills/
{id}/activate` (REST, for UI-driven activation) and the `skills.activate`
native meta-tool (for model-driven activation). `harness.agents.runloop.
run_contact` resolves a session's activated skill bodies fresh from `SkillRepo`
on every compile, same pattern as MCP-002's tool-schema resolution.
`capabilities.search` now also searches skills by name/description/
activation_hints, closing the "no skill index yet" gap MCP-002 noted. Proven
end to end through the real run loop: a session's first turn compiles with
zero skill-body cost, and only the turn after activation carries it. See
D-042.

MCP-002: `capabilities.search` (`harness.capabilities.search`) and
`tools.describe` (`harness.capabilities.activation`) are two new native
meta-tools, callable the same way as any other tool (`POST /tools/{name}/
run`). `capabilities.search(query)` returns compact candidates — kind, ref,
name, description, estimated schema tokens, trust class — across the native
`ToolRegistry` and MCP-001's `mcp_tool_index`, plain case-insensitive keyword
matching against name+description, never a full JSON Schema. `tools.describe
(session_id, kind, ref)` fetches one candidate's full schema and records the
activation in a new `session_activated_capabilities` table; `harness.agents.
runloop.run_contact` resolves that session's activated capabilities fresh
from their source (`ToolRegistry`/`McpIndexRepo`) on every compile and passes
them to `ContextCompiler.compile`'s `active_tool_schemas`. Proven end to end:
a session's first turn compiles with zero tool-schema cost, `tools.describe`
activates one, and only the *next* turn's compile carries its cost — against
a real fixture MCP server and the real run loop, not by calling the compiler
directly. Skills aren't part of the search yet (SKL-001, next, still TODO) —
there's no skill index to search. See D-041.

MCP-001: `harness.mcp.client.McpClient` is a hand-rolled JSON-RPC 2.0 client
against the MCP spec's Streamable HTTP transport (a single POST endpoint),
implementing `initialize` and `tools/list` — the stdio transport is explicitly
declared unsupported rather than faked (ADR 0003). `POST /mcp/servers/{id}/
index` connects to a registered server and replaces its compact tool index
(`mcp_tool_index`: name/description/estimated-schema-token-cost/trust-class)
without ever loading a full JSON Schema — schemas are fetched lazily and only
per-tool via `GET /mcp/tools/{entry_id}/schema`. Every discovered tool defaults
to the `network` permission class (PERM-001's `ask` default), since the
protocol carries no danger-level metadata of its own. `McpServer.
secret_ref_id`, when set, resolves through the same just-in-time pattern as
`hosts.resolve.build_ssh_host` (SEC-001) and is sent as `Authorization: Bearer
<token>` on every request — proven with a real local fixture MCP server
(`tests/mcp/fixtures.py`, via `uvicorn.Server`) that actually rejects requests
missing the correct token, not just a client-side assertion. See D-040.

`SSHHost` (asyncssh-based) does test-connection/
exec-stream/cancel/sftp read-write-list-move-delete against a real local SSH server
in tests (not mocks), with explicit fingerprint pinning (no known_hosts file) and
argv quoting (no shell injection, proven by a regression test). `POST /hosts/{id}/
test` exercises this live. Every path-taking `SSHHost` method (and `exec_stream`'s
`cwd`) is now checked against `host.workspace_roots` via a two-layer containment
check (`harness.hosts.path_safety`): a lexical POSIX normalize-and-check with no
I/O, then — for file operations — a second check against the SFTP-resolved real
path, closing the gap where a symlink inside an allowed root points outside it.
Fails closed with no roots configured. Proven with real filesystem symlinks and
traversal attempts in tests, not just lexical assertions.

WSP-001 (Workspaces) and WSP-002 (Git operations) are also done. A `workspaces`
table pins a folder on a Host; `/hosts/{id}/workspaces/browse` and `.../create-
folder` let a caller pick/create a folder before a Workspace exists; `/workspaces*`
gives CRUD plus `tree` (SFTP list) and `file` (read/write). Every path a caller
supplies passes through two containment layers: the Host's own `workspace_roots`
(HOST-002, inside `SSHHost`) and — narrower — the Workspace's own `root_path`, so
one Workspace can't read/write into a sibling Workspace on the same Host even when
the Host's configured roots are broader than either Workspace. `/workspaces/{id}/
git/*` (init/status/diff/add/commit/branch/log) runs real git remotely via the same
structured-argv `exec_stream` HOST-001 established — never shell-interpolated —
returning `is_git_repo: false` rather than erroring when a folder isn't a repo yet,
and reporting a failed commit (e.g. nothing staged) as `{"ok": false, ...}` rather
than a 5xx.

TOOL-001 (Tool registry + lifecycle) is also done: `harness.tools` implements the
full SPEC/MCP_SKILLS_TOOLS.md lifecycle (validate JSON-Schema arguments → resolve
permission → execute → capture result/error → emit events → compact result), backed
by a persisted `tool_runs` table (`ToolRunRepo`) and run through `JobManager` (same
pattern as LP-009's model load/unload) so a slow tool is cancelable like any other
long action. Permission resolution goes through a `PermissionResolver` Protocol;
the only implementation so far is `AllowAllResolver` — an explicit stand-in, not a
fake permission system — so "ask"/"deny" are real, tested code paths
(`pending_approval`/`denied` ToolRun states, `tool.denied`/`tool.approval_required`
events) with no caller able to produce them yet. PERM-001 will supply the real
resolver. One built-in tool (`echo`, permission class `read`) is always registered,
mirroring `FakeProvider`'s role for language providers — a real, safe, zero-config
tool to exercise the lifecycle against. `/tools`, `/tools/{name}/run`, `/tools/
runs*` expose it over the API.

PERM-001 (Permission engine) is also done, replacing TOOL-001's `AllowAllResolver`
placeholder with a real `PermissionEngine`: ten permission classes each have a
policy (`allow`/`ask`/`deny`) — conservative defaults (`read`/`model_lifecycle`
allow, `destructive` deny, everything else asks), overridable per class via
`PUT /permissions/policies/{class}`. An `"ask"` decision genuinely blocks — the
tool's Job sits "running" until `POST /permissions/decisions/{run_id}/{approve,
reject}` resolves it — and every resolution (automatic or human) is logged to a
`permission_decisions` audit table. Building this surfaced and fixed a real
concurrency bug (D-030): SQLite's `:memory:`/single-file databases pool onto one
shared `StaticPool` connection that isn't safe for two coroutines to use at once,
and PERM-001 was the first feature to create that kind of sustained overlap (a
backgrounded Job racing live HTTP polling) — `Database` now serializes every
query/execute through an `asyncio.Lock`.

TOOL-002 (file/shell/git tools) is also done: `harness.tools.workspace_tools`
registers twelve workspace-scoped native tools (`fs_read_file`/`fs_write_file`/
`fs_list_dir`/`shell_exec`/`git_init`/`git_status`/`git_diff`/`git_add`/
`git_commit`/`git_branch_list`/`git_branch_create`/`git_log`) through the same
TOOL-001 lifecycle and PERM-001 permission engine the `echo` tool uses. Filesystem
reads are permission class `read` (allow by default); writes `write` and shell
exec `execute` (both ask by default); every git operation — including read-only
status/diff/log — is `git`, its own dedicated class (SPEC/SECURITY_PRIVACY.md's
taxonomy treats git as one bucket, not a read/write split). Path resolution and git
invocation are shared with the WSP-001/002 HTTP routes via a new `harness.
workspaces.service` module (extracted during this task so the HTTP layer and the
native-tool layer can't subtly diverge on path containment) — `api/routes/
workspaces.py` was refactored to use it too, with its existing 15 tests as the
regression check that the refactor changed nothing observable. Proven against a
real local SSH server: a full git workflow end-to-end through the tools (not the
HTTP routes), shell argv-injection resistance, path-traversal rejection at the
tool layer (the Job succeeds — it's the *ToolRun* that fails, per D-029's split),
and a `shell_exec` call genuinely blocking on its default `ask` policy until
approved.

ART-001 (Artifacts) is also done — this completes Milestone 4 (Execution) in full.
An `artifacts` table holds typed metadata only (twelve types from
SPEC/WORKSPACES_ARTIFACTS.md: code_file/image/video/screenshot/document/diff/
patch/log/test_report/plan/benchmark_report/arbitrary_file); actual bytes live in
a content-addressed disk blob store (`ArtifactBlobStore`, keyed by sha256, so
identical content is stored once no matter how many Artifacts reference it).
`GET /artifacts/{id}` never returns content — only `GET /artifacts/{id}/content`
does — so referencing `artifact://<id>` in agent context never implicitly pulls
bytes. `POST /artifacts` accepts inline base64 content (browser/client upload);
`POST /workspaces/{id}/artifacts/pull` and `POST /artifacts/{id}/push` move bytes
between the blob store and a Workspace's Host, reusing the same
`harness.workspaces.service` containment and SSH plumbing WSP-001/002 and TOOL-002
already share, and emit `artifact.created`/`artifact.transferred` events. Proven
against a real local SSH server, including a full push-then-pull round trip and a
path-traversal rejection on pull.

CTX-003 (Transcript management) is also done: a new `TranscriptState` (per
session, `session_transcript_state` table) holds explicit, typed "protected"
facts — unresolved requirements, current plan, changed files, failing tests,
permission decisions, plus a caller-maintained rolling summary — that the Context
Compiler now always includes verbatim, exempt from the history-trimming budget
squeeze (proven by a test where the budget is too small to fit *any* history
message, yet every protected fact still appears in the compiled prompt). When
older messages genuinely don't fit, the compiler now says so explicitly
("N earlier messages omitted for budget") and appends the rolling summary if one
exists, rather than silently truncating with no trace. `GET`/`PATCH /sessions/{id}/
transcript-state` let callers (the run loop, a future tool-result hook) read and
update it; the run loop now fetches it and passes it into every `compile()` call,
proven end-to-end via the real `context.compiled` event's budget report.

CTX-004 (Context regression tests) is also done: `tests/context/
test_regression_budgets.py` compiles realistic session compositions (real
history exchanges, a role, personas, `TranscriptState`, skill bodies, and — for
the full-expansion case — schemas pulled from a real `ToolRegistry` with every
production TOOL-001/002 tool registered) at each tier's *actual* `ContextConfig`
default (`bootstrap_target_tokens`=4096, `default_budget_tokens`=8192,
`full_capability_soft_limit_tokens`=16384), not an artificially shrunk budget.
No separate CI wiring was needed — `.github/workflows/ci.yml`'s existing
`pytest tests -q` step already covers this directory.

AGT-007 (Stop/cancel) is also done. Each mentioned contact's run now executes as
its own `asyncio.Task` (`agents/runloop.py`), tracked in a new `RunRegistry`
(`Application.run_registry`) rather than being awaited sequentially inline —
`POST /sessions/{id}/stop` reaches into that registry from a separate, later
request and cancels every task still in flight for that session.
`_run_contact` now has an explicit `except asyncio.CancelledError` branch that
marks the `Run` "canceled", publishes `run.canceled`, and re-raises so
cancellation propagates correctly; `handle_user_message` catches it per-task and
reports `status: "canceled"` in the response rather than letting one contact's
cancellation take down the others. Proven with a real concurrent test — a
message POST is started, allowed to begin streaming, and canceled mid-flight from
a second concurrent request on the same event loop — including that stopping one
session's runs leaves a different session's concurrently-running one untouched.

AGT-006 (Delegation + orchestration graph) is also done — this completes
Milestone 5 (Agent runtime) in full. `agents.delegate` is a real, registered Tool
(permission class `execute`, running through the same TOOL-001 lifecycle and
PERM-001 permission engine as every other tool) that spawns a genuine new `Run`
for the target contact via the same `run_contact()` the run loop itself uses —
same binding resolution, same context compilation, same event trail — and blocks
until that run finishes, returning its reply. `Run` gained a `parent_run_id`
field recording which run (if any) delegated to it; `run_contact` publishes
`agent.spawned` specifically for delegated runs (`agent.completed` already fired
for every run). Because each `POST /tools/agents.delegate/run` call runs as its
own Job/Task (TOOL-001), an orchestrator delegating to two contacts via two
concurrent tool calls gets genuine parallel execution — the same concurrency
AGT-007 established for @mention fan-out, proven directly with `asyncio.gather`
over two real delegate calls. `GET /sessions/{id}/graph` reconstructs a session's
orchestration graph (user/contact/tool nodes, message/delegation edges) fresh
from persisted Runs/ToolRuns on every request rather than a separately
maintained structure, so it can't drift from what actually happened.

## Active task
MCP-001, MCP-002, and SKL-001 are all done (see Current milestone above).
Next per `TASKS.md` is SKL-002 (Superpower bundles).

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
None functionally. 265/265 backend tests pass (repeatedly and reliably — see D-030
for a concurrency race that used to make some flaky before its fix), 2/2 web
unit tests pass, 1/1 Playwright e2e test passes. `ruff check`, `ruff format --check`,
and `mypy --strict` are clean on `src/harness`. `eslint`, `vitest`, and `tsc -b &&
vite build` are clean on `web/`.
Cosmetic: some test runs emit a `PytestUnhandledThreadExceptionWarning` from an
aiosqlite background thread racing pytest-asyncio's event-loop teardown in
short-lived tests; it does not affect pass/fail status and is a known aiosqlite/
asyncio interaction, not an application bug.

## Blockers
None.

## Architectural decisions made during implementation
See `DECISIONS.md` for the full list (D-001 through D-042). Notable ones affecting
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
superpower bundles (SKL-002), creative compute, analytics/benchmarks, the
Node daemon, the rest of the WebUI (graph/compute/models/creative/assets/
analytics/approvals views, full three-panel IA, context meter, accessibility
audit), TUI feature completion, demo mode content, screenshot automation,
GitHub Pages site, and marketing copy. These are tracked as their own
`TASKS.md` entries and proceed in dependency order per
`BUILD/IMPLEMENTATION_PLAN.md`.

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
uv run pytest tests -q                      # backend: 298 tests
cd web && npm run test                      # web unit: vitest
cd web && npx playwright test               # web e2e (needs both servers running)
```
