# TASKS.md — Master Implementation Backlog

Derived from `SPEC/DEFINITION_OF_DONE.md` + `BUILD/IMPLEMENTATION_PLAN.md`.
Statuses: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`.
Tasks tagged `[VS]` form the Phase-4 vertical slice.

Task format: ID — title / description / deps / components / acceptance / tests / status.

---

## Milestone 0 — Scaffolding

### SCAF-001 [VS] Python monorepo scaffold
- Desc: `pyproject.toml` (uv-managed, Python 3.12), `src/harness` package layout with module boundaries per SPEC/ARCHITECTURE.md, ruff + mypy + pytest config, `.gitignore`, `.env.example`.
- Deps: none. Components: repo root.
- Acceptance: `uv sync` succeeds; `ruff check`, `mypy`, `pytest` all runnable; `harness --help` entrypoint works.
- Tests: CI runs lint/type/test. Status: DONE

### SCAF-002 [VS] Web package scaffold
- Desc: `web/` Vite + React + TypeScript app, ESLint/prettier-free minimal config, Vitest set up.
- Deps: none. Components: web.
- Acceptance: `npm install && npm run build && npm test` succeed.
- Tests: vitest smoke test. Status: DONE

### SCAF-003 [VS] CI skeleton
- Desc: GitHub Actions workflow: backend lint/typecheck/test, web build/test.
- Deps: SCAF-001, SCAF-002. Components: .github.
- Acceptance: workflow file valid; all steps pass locally.
- Tests: the CI itself. Status: DONE

---

## Milestone 1 — Kernel

### CORE-001 [VS] Opaque prefixed IDs
- Desc: ULID-style time-sortable IDs with entity prefixes (`host_`, `run_`, `art_`, …) per SPEC/DATA_MODEL.md.
- Deps: SCAF-001. Components: core.
- Acceptance: IDs unique, sortable, prefix-validated.
- Tests: unit tests for format/monotonicity. Status: DONE

### CORE-002 [VS] Config system with precedence
- Desc: Pydantic v2 settings: defaults ← YAML config file ← env vars (`HARNESS_*`) ← CLI flags. Includes context budget targets, server bind, auth mode, data dir. Mirrors CONFIG/examples/harness.example.yaml.
- Deps: SCAF-001. Components: core.
- Acceptance: precedence order provable; example config loads.
- Tests: unit tests for each precedence layer. Status: DONE

### CORE-003 [VS] Error taxonomy + capability vocabulary
- Desc: typed error hierarchy (NotFound/Validation/Permission/Provider/Adapter…); capability enums for hosts, providers (L0–L5), permission classes.
- Deps: SCAF-001. Components: core.
- Acceptance: API maps errors to structured JSON with correlation IDs.
- Tests: unit + API error-shape tests. Status: DONE

### DB-001 [VS] SQLite engine + migration runner
- Desc: async SQLAlchemy (aiosqlite), sequential SQL migrations table, applies on startup, WAL mode.
- Deps: SCAF-001. Components: persistence.
- Acceptance: clean DB is created and migrated on first start; re-running is idempotent.
- Tests: unit tests migrate empty DB, re-migrate. Status: DONE

### DB-002 [VS] Kernel schema migration
- Desc: tables needed by kernel + slice: settings, secret_refs, roles, personas, contacts, contact_personas, teams, team_members, sessions, session_members, messages, runs, run_metrics, binding_snapshots, events, jobs. Remaining SPEC/DATA_MODEL.md tables land with their subsystems (see DECISIONS.md D-004).
- Deps: DB-001. Components: persistence.
- Acceptance: schema matches SPEC/DATA_MODEL.md naming; opaque IDs used.
- Tests: migration + repository round-trip tests. Status: DONE

### EVT-001 [VS] Event model + append-only store
- Desc: Event envelope (event_id, type, timestamp, correlation_id, resource, payload) per SPEC/API_CONTRACT.md; append-only `events` table with monotonic cursor; retention policy hook.
- Deps: DB-002. Components: events, persistence.
- Acceptance: events persist with cursor ordering; payloads versioned.
- Tests: unit store/replay tests. Status: DONE

### EVT-002 [VS] In-process event bus
- Desc: asyncio pub/sub with per-subscriber queues, type/resource filters, backpressure-safe fanout; persistence tap.
- Deps: EVT-001. Components: events.
- Acceptance: publisher never blocks on slow subscriber; filters work.
- Tests: unit tests incl. slow-subscriber. Status: DONE

### API-001 [VS] ASGI app factory + system endpoints
- Desc: FastAPI app, `/api/v1` versioned router, `GET /health`, `GET /system/info`, `GET /capabilities`, OpenAPI at `/openapi.json`, structured error handler, correlation IDs on mutations.
- Deps: CORE-002, CORE-003. Components: api.
- Acceptance: DoD "API" bullets 1–3; docs served in dev mode.
- Tests: API contract tests. Status: DONE

### API-002 [VS] `harness serve` CLI
- Desc: CLI entrypoint binding host/port from config/flags (default 127.0.0.1:4096).
- Deps: API-001. Components: api, cli.
- Acceptance: `harness serve --host 127.0.0.1 --port 4096` boots server + DB + bus.
- Tests: subprocess smoke test in integration suite. Status: DONE

### AUTH-001 [VS] Token authentication
- Desc: bearer-token auth; token auto-generated into data dir (0600). Loopback requests trusted when `auth.local_trust` (default true); non-loopback always requires token. Applies to REST + WebSocket.
- Deps: API-001. Components: api, core.
- Acceptance: unauthenticated remote request → 401; WS unauthenticated → closed; loopback dev flow works.
- Tests: API + WS auth tests. Status: DONE

### API-003 [VS] WebSocket event stream
- Desc: `/api/v1/events` WS; subscribe message with filters (session IDs, job IDs, host IDs, event types); replay from cursor; heartbeat.
- Deps: EVT-002, AUTH-001. Components: api, events.
- Acceptance: authenticated client subscribes/filters/replays; unauthenticated rejected.
- Tests: WS integration tests. Status: DONE

### SEC-001 Secrets abstraction
- Desc: secret store chain — OS keyring → encrypted local file → env-var reference; `secret_refs` metadata table; `/secrets/metadata`, `/secrets/{id}/test`; values never serialized.
- Deps: DB-002, API-001. Components: core, persistence, api.
- Acceptance: no secret value in DB/logs/events/API responses.
- Tests: unit + redaction tests. Status: DONE

### JOB-001 Job engine
- Desc: cancelable async jobs with state machine (queued/running/succeeded/failed/canceled), `/jobs`, `/jobs/{id}`, `POST /jobs/{id}/cancel`, job events.
- Deps: EVT-002, DB-002. Components: jobs, api.
- Acceptance: long actions create Jobs; cancel works mid-run.
- Tests: unit state machine + API integration. Status: DONE

---

## Milestone 2 — Control plane

### CP-001 Capability registry
- Desc: control-plane vocabulary (identity/capabilities/state/settings-schema/settings/actions/telemetry/history/health/events) as typed contracts adapters implement; unsupported capabilities explicit.
- Deps: CORE-003. Components: core.
- Acceptance: registry lists subsystem capabilities uniformly; `/capabilities` reflects it.
- Tests: unit contract tests. Status: DONE

### CP-002 Settings-schema system
- Desc: JSON-Schema-based settings descriptors with namespaced provider sections (`common` + `provider.<name>`); validation rejects unknown fields unless passthrough declared.
- Deps: CP-001. Components: core.
- Acceptance: schema round-trips to UI renderable form; unknown-field rejection works.
- Tests: unit validation tests. Status: DONE

### CP-003 Provider registry
- Desc: providers table + registration/config of language provider instances (endpoint, secret ref, enabled), `/language/providers`.
- Deps: CP-002, SEC-001. Components: providers, api.
- Acceptance: add/list/remove providers; secrets by reference only.
- Tests: API integration. Status: DONE

### CP-004 Host registry
- Desc: hosts + host_capabilities tables, `/hosts` CRUD, capability model per SPEC/HOSTS_AND_NODE.md.
- Deps: CP-001, SEC-001. Components: hosts, api.
- Acceptance: hosts persist with capability sets; `/hosts/{id}/capabilities` works.
- Tests: API integration. Status: DONE

---

## Milestone 3 — Language compute

### LP-001 [VS] Language provider contract
- Desc: adapter protocol with capability levels L0–L5 (SPEC/PROVIDER_MATRIX.md): chat streaming, tools, model discovery, lifecycle, telemetry, native extras; typed request/response; usage reporting.
- Deps: CORE-003. Components: providers.language.
- Acceptance: contract supports all matrix rows without core changes.
- Tests: contract conformance suite reused by all adapters. Status: DONE

### LP-002 [VS] Deterministic fake provider
- Desc: in-process provider fixture: scripted/deterministic streaming, token usage, TTFT simulation; used by demo mode and CI.
- Deps: LP-001. Components: providers.language.
- Acceptance: streams deterministic output with usage metrics.
- Tests: conformance suite. Status: DONE

### LP-003 Generic OpenAI-compatible adapter
- Desc: base URL + API key + model list when available; streaming chat + tools (L1).
- Deps: LP-001, CP-003. Components: providers.language.
- Acceptance: works against fake OpenAI-compatible test server.
- Tests: contract fixture tests. Status: DONE

### LP-004 LM Studio native adapter (L5)
- Desc: native v1 API: discovery/list/load/unload/settings from runtime schema, TTFT/throughput when exposed; OpenAI-compatible fallback; no hard-coded settings.
- Deps: LP-003. Components: providers.language.
- Acceptance: DoD Providers bullet 2 against fixture server.
- Tests: fake LM Studio fixture tests. Status: DONE

### LP-005 Ollama adapter (L4/L5)
- Desc: native API: list/show/pull progress/chat/generate/options/keep-alive/unload; embeddings metadata.
- Deps: LP-001, CP-003. Components: providers.language.
- Acceptance: DoD Providers bullet 3 against fixture.
- Tests: fake Ollama fixture tests. Status: DONE

### LP-006 OpenRouter adapter
- Desc: catalog, pricing/usage/routing metadata, namespaced routing settings.
- Deps: LP-003. Components: providers.language.
- Acceptance: catalog + chat against fixture; cost metadata captured.
- Tests: fixture tests. Status: DONE

### LP-007 OpenAI + Anthropic + Gemini native adapters
- Desc: native message/tool semantics per provider, secret references, usage capture.
- Deps: LP-003, SEC-001. Components: providers.language.
- Acceptance: DoD Providers bullet 4 against fixtures.
- Tests: fixture tests per adapter. Status: DONE

### LP-008 Model profiles + placement policy
- Desc: model_profiles table; policies manual/auto/prefer-loaded/local/fastest/lowest-pressure/lowest-cost; auto opt-in only.
- Deps: LP-001, CP-004. Components: providers, core.
- Acceptance: profile resolves to provider+model+settings; placement respects policy.
- Tests: unit placement tests. Status: DONE

### LP-009 Instance lifecycle API
- Desc: `/language/models*`, `/language/instances*` incl. load/unload/settings-schema/settings; long ops as Jobs.
- Deps: LP-004, JOB-001. Components: api, providers.
- Acceptance: lifecycle endpoints work against LM Studio/Ollama fixtures.
- Tests: API integration. Status: DONE

---

## Milestone 4 — Execution

### HOST-001 SSH agentless adapter
- Desc: asyncssh: test connection, exec with streamed stdout/stderr, cancel, sftp read/write/list/move/delete, known-host verification, keys via secret store, structured argv (no shell string concat).
- Deps: CP-004, SEC-001. Components: hosts.
- Acceptance: DoD Hosts/workspaces bullets vs local sshd fixture.
- Tests: integration vs local SSH server fixture. Status: DONE

### HOST-002 Path safety
- Desc: configured workspace roots, canonicalization, traversal rejection, no implicit sudo.
- Deps: HOST-001. Components: hosts, core.
- Acceptance: escapes rejected; security tests pass.
- Tests: unit traversal suite. Status: DONE

### WSP-001 Workspaces
- Desc: workspaces table + `/workspaces`, `/workspaces/{id}/tree|file|diff`, `/hosts/{id}/workspaces/browse`, create-folder remotely.
- Deps: HOST-002. Components: workspaces, api.
- Acceptance: phone workflow steps 3–7 (backend part) work.
- Tests: API integration vs SSH fixture. Status: DONE

### WSP-002 Git operations
- Desc: `/workspaces/{id}/git/*`: init/status/diff/add/commit/branch/log via structured exec.
- Deps: WSP-001. Components: workspaces.
- Acceptance: init/use git remotely; diff renders.
- Tests: integration vs fixture repo. Status: DONE

### TOOL-001 Tool registry + lifecycle
- Desc: native tool registry, typed schemas, lifecycle per SPEC/MCP_SKILLS_TOOLS.md (validate→permission→approve→execute→capture→artifact→events→compact result).
- Deps: EVT-002, JOB-001. Components: tools.
- Acceptance: tool runs recorded in tool_runs with events.
- Tests: unit lifecycle tests. Status: DONE

### TOOL-002 File/shell/git tools + permissions
- Desc: workspace-scoped tools exposed to agents behind permission classes with allow/ask/deny; approval events.
- Deps: TOOL-001, WSP-002, PERM-001. Components: tools.
- Acceptance: DoD MCP/skills/tools permission bullet; approval flow works.
- Tests: integration incl. deny/ask paths. Status: DONE

### ART-001 Artifacts
- Desc: artifacts table, typed catalog, disk store for blobs, `/artifacts*` incl. content + checksummed transfer, `artifact://` references.
- Deps: DB-002, HOST-001. Components: artifacts, api.
- Acceptance: artifacts referenced by ID; content lazy; transfers evented.
- Tests: unit + API integration. Status: DONE

---

## Milestone 5 — Agent runtime

### AGT-001 [VS] Roles + personas
- Desc: CRUD + seed roles (orchestrator, architect, researcher, coder, reviewer, tester, designer, operator) and demo personas; persona token budget 50–200 with deterministic stacking precedence.
- Deps: DB-002, API-001. Components: agents, api.
- Acceptance: CRUD works; seeds present; persona conflicts resolve deterministically.
- Tests: API + unit stacking tests. Status: DONE

### AGT-002 [VS] Contacts + teams
- Desc: contacts CRUD with handle/display/role/personas/binding; teams with members; identity stable across binding changes.
- Deps: AGT-001. Components: agents, api.
- Acceptance: DoD Agents bullets 1; contact history survives model change.
- Tests: API + identity tests. Status: DONE

### AGT-003 [VS] Mention parser
- Desc: `@contact`, multiple, `@team`, `@everyone`, natural delegation inference; explicit mention bypasses orchestrator per room policy.
- Deps: AGT-002. Components: agents.
- Acceptance: parser cases from SPEC/CONTACTS_ROLES_PERSONAS.md pass.
- Tests: unit parser suite. Status: DONE

### AGT-004 [VS] Binding resolution + snapshots
- Desc: 5-level precedence (turn > session/contact > contact > role > system); every run persists resolved snapshot to binding_snapshots.
- Deps: AGT-002, LP-001. Components: agents, persistence.
- Acceptance: DoD Agents binding bullets; `PATCH /sessions/{id}/contacts/{cid}/binding` + `POST /sessions/{id}/turn-overrides` work.
- Tests: unit precedence + API integration. Status: DONE

### CTX-001 [VS] Token estimator + budget report
- Desc: pluggable token estimator (heuristic default, see DECISIONS.md D-006); budget report JSON per SPEC/CONTEXT_COMPILER.md with per-section counts.
- Deps: CORE-002. Components: context.
- Acceptance: report shape matches spec; exposed to UI + `context.compiled` event.
- Tests: unit budget math. Status: DONE

### CTX-002 [VS] Context compiler layers
- Desc: 11-layer assembly (protocol, role, personas, session state, recent conversation, workspace facts, skills, tools, MCP, artifact excerpts, task memory); lazy capability surface (`capabilities.search`, `skills.activate`, `tools.describe`, `artifacts.get`, `agents.delegate`).
- Deps: CTX-001, AGT-004. Components: context.
- Acceptance: bootstrap ≤4K; nothing eager-injected.
- Tests: compile fixtures + budget assertions. Status: DONE

### CTX-003 Transcript management
- Desc: recent window, structured session state, rolling summaries, preserved tool outcomes/artifact refs; never summarize away unresolved requirements/plan/changed files/failing tests/permission decisions.
- Deps: CTX-002. Components: context.
- Acceptance: long-session compile keeps protected facts.
- Tests: unit compaction tests. Status: DONE

### CTX-004 [VS] Context regression tests
- Desc: representative sessions compiled in CI asserting ≤4K bootstrap, ≤8K normal, ≤16K expanded; fails on eager schema injection.
- Deps: CTX-002. Components: tests.
- Acceptance: DoD Context bullets enforced in CI.
- Tests: this task is tests. Status: DONE

### AGT-005 [VS] Run loop
- Desc: `POST /sessions/{id}/messages` → mention routing → run per target contact → compile → stream inference → events (run.started, run.binding_snapshot, context.compiled, inference.*) → persist messages + run_metrics.
- Deps: AGT-003, AGT-004, CTX-002, LP-002, API-003. Components: agents, api.
- Acceptance: vertical-slice items 9–12; streamed deltas visible over WS.
- Tests: end-to-end API test with fake provider. Status: DONE

### AGT-006 Delegation + orchestration graph
- Desc: `agents.delegate` tool, agent.spawned/completed events, `GET /sessions/{id}/graph` (nodes: user/orchestrator/contacts/jobs/tools; edges: delegation/handoff; statuses).
- Deps: AGT-005, TOOL-001. Components: agents, api.
- Acceptance: parallel plan→review→implement workflow runs; graph reflects it.
- Tests: multi-contact integration test. Status: DONE

### AGT-007 Stop/cancel
- Desc: `POST /sessions/{id}/stop` cancels active runs/jobs cleanly.
- Deps: AGT-005, JOB-001. Components: agents.
- Acceptance: DoD Agents stop bullet.
- Tests: integration cancel test. Status: DONE

### PERM-001 Permission engine
- Desc: classes (read/write/execute/network/git/process/model_lifecycle/creative_generation/training/destructive) × policies (allow/ask/deny); resolution explicit + logged; approval API + events.
- Deps: EVT-002, DB-002. Components: core, tools, api.
- Acceptance: ask flow blocks until approval; decisions logged.
- Tests: unit resolution + API approval tests. Status: DONE

---

## Milestone 6 — MCP + Skills

### MCP-001 Lazy MCP index
- Desc: mcp_servers + mcp_tool_index (server, tool, one-line desc, est. schema tokens, trust class); `/mcp/servers`, `/mcp/tools/index`; server lifecycle.
- Deps: TOOL-001, SEC-001. Components: mcp.
- Acceptance: adding server indexes tools without loading schemas.
- Tests: fixture MCP server tests. Status: DONE

### MCP-002 capabilities.search + activation
- Desc: `capabilities.search(query)` returns concise candidates across tools/skills/MCP; only selected schemas compiled next call.
- Deps: MCP-001, CTX-002. Components: mcp, context.
- Acceptance: DoD "Schema loads only when activated"; budget unaffected until activation.
- Tests: integration + context regression. Status: DONE

### SKL-001 Skills
- Desc: skill package format (metadata/SKILL.md/scripts/activation rules/tool requirements/cost estimate); index cheap, body lazy; `/skills`, `/skills/{id}/activate`.
- Deps: CTX-002. Components: skills.
- Acceptance: metadata indexed without body load; activation adds body to compile.
- Tests: unit + budget tests. Status: DONE

### SKL-002 Superpower bundles
- Desc: seed bundles (Coding, Git/GitHub, Browser, Creative, Research, Remote Host, Benchmarking) as capability-exposure toggles; permissions stay explicit.
- Deps: SKL-001, PERM-001. Components: skills, tools.
- Acceptance: toggles modify exposed surface only.
- Tests: integration exposure tests. Status: DONE

---

## Milestone 7 — Creative compute

### CRE-001 Stability Matrix discovery
- Desc: data-driven package catalog (all families in SPEC/CREATIVE_COMPUTE.md), Data-layout discovery of installations, unknown packages → `unknown/custom` with detected metadata.
- Deps: CP-004. Components: providers.creative.
- Acceptance: DoD Creative bullets 1–2 vs fixture layout.
- Tests: discovery fixture tests. Status: TODO

### CRE-002 Engine capability model
- Desc: per-engine supported_platforms/acceleration_backends/api_strategy/launch_strategy/asset_types/capability_set; integration hierarchy (native API → compat layer → HTTP adapter → launch/fs → read-only).
- Deps: CRE-001, CP-002. Components: providers.creative.
- Acceptance: engines show real capability level; no fake controls.
- Tests: unit capability mapping tests. Status: TODO

### CRE-003 ComfyUI deep adapter
- Desc: health, object/node metadata, queue, workflow submit, progress events, interrupt, history, image upload, workflow JSON stored by reference (never in LLM context by default), output artifact capture, asset discovery.
- Deps: CRE-002, ART-001, JOB-001. Components: providers.creative.
- Acceptance: DoD "ComfyUI deep adapter can submit workflow and capture output" vs fake ComfyUI server.
- Tests: fixture integration tests. Status: TODO

### CRE-004 A1111/Forge-compatible adapter
- Desc: txt2img/img2img/options/samplers/models/VAEs/LoRAs/progress/interrupt/extras where exposed; capability-negotiated.
- Deps: CRE-002, ART-001. Components: providers.creative.
- Acceptance: works vs fake A1111 server exposing partial capabilities.
- Tests: fixture tests incl. missing-capability paths. Status: TODO

### CRE-005 Remaining families at honest levels
- Desc: InvokeAI native detection; Fooocus-family launch/health/read-only; training engines (Kohya/OneTrainer/FluxGym) as approval-gated Jobs; video family listed.
- Deps: CRE-002, JOB-001, PERM-001. Components: providers.creative.
- Acceptance: DoD "represented with capability level, not fake controls".
- Tests: catalog + adapter-level tests. Status: TODO

### CRE-006 Creative assets catalog
- Desc: canonical asset types, hash/path dedupe across engines, creative_assets table.
- Deps: CRE-001, ART-001. Components: providers.creative.
- Acceptance: shared checkpoint appears once with multiple locations.
- Tests: dedupe unit tests. Status: TODO

### CRE-007 Creative profiles
- Desc: creative_profiles per SPEC (selector/settings/placement; checkpoint-profile bundles); not personas.
- Deps: CRE-006. Components: providers.creative, api.
- Acceptance: profile drives a generation on fixture engine.
- Tests: integration test. Status: TODO

### CRE-008 Batch comparison
- Desc: one prompt × N checkpoints/profiles, controlled seeds, sequential/parallel, capacity-aware placement, grid artifact, run metrics.
- Deps: CRE-007, ANA-001. Components: providers.creative, jobs.
- Acceptance: DoD batch comparison with deterministic fixture.
- Tests: fixture batch test. Status: TODO

### CRE-009 Provenance
- Desc: full provenance record per generation (engine/version/host/workflow/checkpoint+hash/loras/prompt/seed/sampler/dims/steps/CFG/duration/resources/timestamp) on artifacts.
- Deps: CRE-003, ART-001. Components: providers.creative, artifacts.
- Acceptance: DoD "Output becomes Artifact with provenance".
- Tests: provenance assertion tests. Status: TODO

---

## Milestone 8 — Analytics + benchmarks

### ANA-001 Run metrics persistence
- Desc: run_metrics capture per SPEC/ANALYTICS_BENCHMARKS.md (tokens, TTFT, tok/s, durations, tools, cost when reported, outcome).
- Deps: AGT-005. Components: analytics.
- Acceptance: DoD Analytics bullets 1–2.
- Tests: metric capture tests. Status: TODO

### ANA-002 Host metrics time-series
- Desc: host_samples bounded/configurable retention; ingestion from node + SSH probes.
- Deps: CP-004. Components: analytics.
- Acceptance: series stored + pruned per retention.
- Tests: retention unit tests. Status: TODO

### ANA-003 Analytics API
- Desc: `/analytics/runs|models|hosts|agents|creative` aggregations.
- Deps: ANA-001, ANA-002. Components: analytics, api.
- Acceptance: dashboard queries served.
- Tests: aggregation tests on fixtures. Status: TODO

### ANA-004 Benchmark engine
- Desc: benchmark_suites/runs; prompts/tasks × contacts/models/profiles, scoring strategy, repetitions, concurrency, seed policy; full binding snapshots for reproducibility; model + creative comparison workflows.
- Deps: ANA-001, AGT-005, CRE-008. Components: analytics.
- Acceptance: DoD benchmark bullet.
- Tests: benchmark run on fake providers. Status: TODO

---

## Milestone 9 — Node

### NODE-001 Harness Node daemon
- Desc: `harness-node start`; pairing via one-time token → per-node credential; telemetry (CPU/RAM/disk; GPU/VRAM via NVML when present; graceful sensor degradation); engine health advertisement; heartbeats.
- Deps: CP-004, AUTH-001, ANA-002. Components: node.
- Acceptance: DoD Node bullets; remote coding never requires it.
- Tests: pairing + degraded-sensor tests. Status: TODO

---

## Milestone 10 — UI

### WEB-001 [VS-minimal] Web app shell
- Desc: dark control-room shell, three-panel desktop layout, navigation (Chats/Agents/Workspaces/Compute/Models/Creative/Assets/Skills/MCP/Analytics/Settings), theme tokens, reduced-motion, WCAG AA base.
- Deps: SCAF-002, API-001. Components: web.
- Acceptance: shell renders; nav works; auth connect flow.
- Tests: vitest + Playwright smoke. Status: IN_PROGRESS

### WEB-002 [VS] Chat view
- Desc: streaming conversation, contact chips, composer, context meter, speed indicator; via REST + WS only.
- Deps: WEB-001, AGT-005. Components: web.
- Acceptance: vertical-slice item 13.
- Tests: Playwright chat flow vs fake provider. Status: IN_PROGRESS

### WEB-003 Graph view
- Desc: animated directed execution graph with statuses; node → inspector; infra events shown.
- Deps: WEB-002, AGT-006. Components: web.
- Acceptance: DoD WebUI graph bullet.
- Tests: Playwright graph test. Status: TODO

### WEB-004 Compute view
- Desc: host cards (state, CPU/RAM/GPU/VRAM, running engines, jobs, speed history).
- Deps: WEB-001, ANA-003. Components: web. Status: TODO

### WEB-005 Models view
- Desc: provider grouping, model states, instance controls, schema-driven settings forms, tok/s + TTFT history.
- Deps: WEB-001, LP-009. Components: web.
- Acceptance: DoD "Provider-specific settings schemas render in UI". Status: TODO

### WEB-006 Creative view
- Desc: installations, engines w/ capability level, assets, workflows/profiles, queue, batch compare.
- Deps: WEB-001, CRE-007. Components: web. Status: TODO

### WEB-007 Workspace/files view
- Desc: host browse, folder create, file tree, file view, diffs, git.
- Deps: WEB-001, WSP-002. Components: web. Status: TODO

### WEB-008 Artifacts view
- Desc: artifact catalog, previews, downloads.
- Deps: WEB-001, ART-001. Components: web. Status: TODO

### WEB-009 Analytics view
- Desc: restrained dense dashboard per SPEC/ANALYTICS_BENCHMARKS.md; numbers/bars over gauges.
- Deps: WEB-001, ANA-003. Components: web. Status: TODO

### WEB-010 Approvals
- Desc: approval cards in chat + approvals queue; permission decisions visible.
- Deps: WEB-002, PERM-001. Components: web. Status: TODO

### WEB-011 Typed API client from OpenAPI
- Desc: generate TS client from `/openapi.json` in build; no hand-maintained duplicate types.
- Deps: API-001, SCAF-002. Components: web.
- Acceptance: SPEC/API_CONTRACT.md OpenAPI bullet.
- Tests: build-time generation check. Status: TODO

### TUI-001 [VS-minimal] TUI shell + API client
- Desc: Textual app connecting to API (`harness tui --api …`); nav mirrors WebUI IA; keyboard-first.
- Deps: SCAF-001, API-003. Components: tui. Status: TODO

### TUI-002 [VS] TUI chat
- Desc: sessions list, conversation, mentions, streaming via WS.
- Deps: TUI-001, AGT-005. Components: tui.
- Acceptance: vertical-slice item 14; concurrent with WebUI.
- Tests: TUI integration tests (Textual pilot). Status: DONE

### TUI-003 TUI feature completion
- Desc: graph/status, contacts, hosts, files, model settings, approvals.
- Deps: TUI-002 + backend tasks. Components: tui.
- Acceptance: DoD TUI bullets.
- Tests: pilot tests per screen. Status: IN_PROGRESS

### WEB-012 Accessibility audit
- Desc: WCAG AA checks, keyboard nav, touch targets ≥44px, no color-only signals.
- Deps: WEB-001..010. Components: web.
- Acceptance: DoD accessibility bullet.
- Tests: axe audit in Playwright. Status: TODO

---

## Milestone 11 — Remote/mobile polish

### MOB-001 Responsive layouts
- Desc: landscape phone ≥2 panes mission-control; portrait single-pane with slide-over sheets, fully functional.
- Deps: WEB-002..010. Components: web.
- Acceptance: DoD iPhone landscape/portrait bullets.
- Tests: Playwright viewport tests. Status: TODO

### MOB-002 Phone workflow end-to-end
- Desc: full 10-step phone flow (auth → host → folder → session → contact → edit → run → artifacts → rebind) against SSH fixture.
- Deps: MOB-001, WSP-002, AGT-004. Components: web, api.
- Acceptance: DoD Phone section.
- Tests: Playwright mobile e2e. Status: TODO

### DOC-001 Secure remote access docs
- Desc: bind/auth/HTTPS/Tailscale-Serve/reverse-proxy patterns documented without making Tailscale mandatory.
- Deps: AUTH-001. Components: docs.
- Acceptance: SPEC/SECURITY_PRIVACY.md + GITHUB_PAGES.md constraints reflected. Status: TODO

---

## Milestone 12 — Release

### DEMO-001 Seeded demo mode
- Desc: `HARNESS_DEMO_MODE=1` loads deterministic fictional hosts/contacts/models/project/metrics/assets; no real credentials/network.
- Deps: AGT-005, ANA-003, CRE-006. Components: all.
- Acceptance: DoD demo bullet; fully offline.
- Tests: demo boot test. Status: TODO

### DEMO-002 Screenshot automation
- Desc: Playwright script capturing the 7 required screenshots (desktop chat/graph, compute, creative, analytics, iPhone landscape, iPhone portrait, TUI) into `site/public/screenshots/`.
- Deps: DEMO-001, MOB-001, TUI-003. Components: tests, site.
- Acceptance: MARKETING/README.md list satisfied.
- Tests: script produces all files. Status: TODO

### REL-001 Docs
- Desc: README (install/use/security/architecture), CONTRIBUTING, LICENSE decision documented.
- Deps: all. Components: docs. Status: TODO

### REL-002 Site + Pages workflow
- Desc: `site/` landing/docs/screenshots/static remote client (HTTPS-endpoint entry, session-memory credentials); Actions deploy on main.
- Deps: DEMO-002. Components: site, .github.
- Acceptance: SPEC/GITHUB_PAGES.md deliverables. Status: TODO

### REL-003 Marketing files
- Desc: reddit-local-llm.md, reddit-sideproject.md, linkedin.md, launch-notes.md from measured reality.
- Deps: DEMO-002, CTX-004. Components: marketing. Status: TODO

### REL-004 Final DoD + no-placeholder audit
- Desc: run full acceptance suite; grep audit (TODO/FIXME/placeholder/creator data/example keys); justify or remove every hit; clean tree; push.
- Deps: everything. Components: repo.
- Acceptance: SPEC/DEFINITION_OF_DONE.md complete. Status: TODO
