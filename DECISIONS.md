# DECISIONS.md — Implementation-level decisions

Below the ADR threshold; recorded so choices don't live only in conversation history.
Format: decision / reason / alternatives / consequences.

## D-001 — Python 3.12 via uv
- Decision: manage Python 3.12 and all backend deps with `uv` (pyproject + lockfile).
- Reason: spec requires 3.12+; system Python is 3.11; uv is present and gives reproducible installs.
- Alternatives: system 3.11 (violates AGENTS.md), pyenv (heavier), poetry (slower).
- Consequences: contributors need uv or any 3.12 interpreter; CI uses uv.

## D-002 — FastAPI + uvicorn, httpx, Pydantic v2
- Decision: use the exact stack AGENTS.md names ("Expected tech direction").
- Reason: spec-endorsed; smallest deviation risk.
- Alternatives: Litestar/Starlette bare (no benefit worth an ADR).
- Consequences: OpenAPI generation is free, matching SPEC/API_CONTRACT.md.

## D-003 — SQLAlchemy 2 async (aiosqlite) + plain SQL migrations
- Decision: SQLAlchemy Core/ORM for queries; migrations are ordered `.sql` files applied by a small runner recorded in a `schema_migrations` table.
- Reason: AGENTS.md allows SQLModel/SQLAlchemy; plain SQL migrations keep the schema exactly as SPEC/DATA_MODEL.md names it without Alembic dependency.
- Alternatives: Alembic (autogen drift, extra dep), SQLModel (couples Pydantic to tables), raw aiosqlite (loses typing).
- Consequences: writing migrations is manual; runner must stay idempotent and sequential.

## D-004 — Incremental schema, one migration per subsystem milestone
- Decision: migration 0001 creates kernel/slice tables only; each subsystem milestone ships its own migration (hosts/workspaces, tools/mcp/skills, creative, analytics…), converging on the full SPEC/DATA_MODEL.md table list.
- Reason: avoids a giant speculative schema that drifts before the subsystem lands; keeps every table exercised by tests when introduced.
- Alternatives: all ~34 tables up front.
- Consequences: DATA_MODEL completeness is verified at REL-004 audit; TEST_MATRIX tracks it.

## D-005 — Auth: bearer token, loopback trust by default
- Decision: a random API token is generated on first start into `<data_dir>/api_token` (0600). Non-loopback requests always require `Authorization: Bearer <token>` (REST and WS). Loopback requests are trusted when `auth.local_trust: true` (default), satisfying "Remote use requires Harness authentication" while keeping single-machine UX frictionless. Setting `auth.mode: required` enforces tokens everywhere.
- Reason: SPEC/SECURITY_PRIVACY.md requires auth for remote use; DEPLOYMENT.md shows plain local commands.
- Alternatives: always-require (breaks casual local TUI/WebUI), session cookies (CSRF surface; bearer chosen per spec's "bearer-token design with equivalent protections").
- Consequences: WebUI/TUI must support token entry for remote connections; tests cover both paths.

## D-006 — Token estimator: pluggable, heuristic default
- Decision: `context.tokens.TokenEstimator` protocol; default implementation estimates ~1 token / 4 chars (English/code-calibrated, word-boundary aware). Provider adapters may supply exact tokenizers later; budget tests use the default with headroom margins.
- Reason: exact tokenization is model-specific; the spec requires budget measurement/reporting, not a particular tokenizer; avoids heavyweight tokenizer deps in core.
- Alternatives: tiktoken (OpenAI-specific, native wheel), HF tokenizers (heavy).
- Consequences: budgets are estimates; regression tests assert with margin (e.g. bootstrap ≤ 4K estimated). Documented in budget report as `estimator: "heuristic-v1"`.

## D-007 — Event cursor = SQLite rowid-backed sequence
- Decision: events table has an INTEGER PRIMARY KEY `seq` used as the replay cursor; `event_id` remains the opaque `evt_` ULID.
- Reason: monotonic, cheap, transactional; replay-from-cursor per SPEC/API_CONTRACT.md.
- Alternatives: timestamp cursors (collisions), ULID ordering (clock skew).
- Consequences: cursors are per-installation, not globally meaningful — fine for local-first.

## D-008 — Web stack: hand-rolled minimal Vite app, no UI framework
- Decision: React 18 + TypeScript + Vite, no component library; design tokens/CSS custom properties implement the "dark technical control room" system.
- Reason: SPEC/UI_UX.md demands a specific visual grammar; component libraries fight it and bloat the bundle; AGENTS.md prefers smallest deps.
- Alternatives: Tailwind (acceptable, still a dep), MUI/Chakra (styling fight).
- Consequences: we own the CSS system; accessibility must be tested explicitly (axe in Playwright).

## D-009 — Spec kit unpacked into repo root
- Decision: the uploaded `harness-os-spec-kit.zip` was extracted to the repo root (SPEC/, ADR/, BUILD/, TESTING/, CONFIG/, MARKETING/, AGENTS.md, DEPLOYMENT.md, manifest.json); kit README kept as `README.spec-kit.md`; original zip retained untouched.
- Reason: specs must be versioned and referenceable from code/tests; the repo previously contained only the zip.
- Consequences: root README.md describes the implementation and links to the kit docs.

## D-010 — Fake provider is a first-class adapter, not test-only code
- Decision: the deterministic provider (LP-002) ships in `harness.providers.language.fake` as a real adapter used by demo mode (`HARNESS_DEMO_MODE=1`) and CI.
- Reason: SPEC/UI_UX.md seeded screenshot mode requires deterministic fictional data with no network; DoD requires fixture-exercised adapters.
- Consequences: demo mode and tests share one code path; it must meet the same adapter contract (conformance suite).

## D-011 — Role carries a system prompt, not a binding
- Decision: `Role` (core/domain.py) contributes `system_prompt` to the context compiler but no `provider`/`model`/host fields. The "role default" level in the 5-level binding precedence (SPEC/ARCHITECTURE.md) is therefore a defined no-op in v1: it participates in precedence order but never supplies a value, so resolution falls through to contact/system.
- Reason: SPEC/CONTACTS_ROLES_PERSONAS.md's Role example shows only responsibility/permissions, never model/host defaults; CONFIG/examples/contact.example.yaml is where `binding` first appears. Adding an unused field speculatively would violate AGENTS.md's "no placeholders" rule.
- Alternatives: give Role a `binding: Binding` field now.
- Consequences: if a future requirement needs per-role default models, add the field then; `resolve_binding()` already accepts a `role` argument so the change is additive, not a rework.

## D-012 — Vertical-slice WebUI client is hand-written, pending WEB-011 codegen
- Decision: `web/src/api/client.ts` hand-declares types for only the endpoints the
  vertical-slice chat view calls (health, contacts, sessions, messages).
- Reason: SPEC/API_CONTRACT.md requires a TS client generated from `/openapi.json`
  (WEB-011), but generating it needs the OpenAPI surface to stabilize past the kernel
  slice; blocking the vertical-slice proof on codegen tooling would stall Phase 4.
- Alternatives: wire up openapi-typescript now against the partial API.
- Consequences: WEB-011 must delete this hand-written client and replace all call
  sites with the generated one — tracked so it isn't mistaken for the final shape.

## D-013 — CORS enabled by default for the WebUI dev server origin only
- Decision: `security.cors_origins` defaults to `http://localhost:5173` /
  `http://127.0.0.1:5173` (the Vite dev server); the API adds `CORSMiddleware` only
  when the list is non-empty, so setting it to `[]` disables CORS entirely (e.g. once
  a production build serves the WebUI from the same origin as the API).
- Reason: `harness serve` and `npm run dev` are separate processes/ports per
  DEPLOYMENT.md; without CORS the browser blocks every WebUI→API request, which would
  make SPEC/DEFINITION_OF_DONE.md's WebUI section untestable in dev.
- Alternatives: reverse-proxy the two behind one origin in dev (adds a dependency);
  wildcard `*` origin (too permissive given bearer-token auth headers).
- Consequences: production/packaged builds that serve WebUI static assets from the API
  process should set `security.cors_origins: []`.

## D-014 — License selection deferred to project owner
- Decision: ship a placeholder `LICENSE` file and `license = "LicenseRef-Pending"` in
  `pyproject.toml` rather than choosing an open-source license unilaterally.
- Reason: license choice (MIT/Apache-2.0/AGPL/proprietary/etc.) has legal and business
  consequences for the project owner that a spec kit cannot answer on their behalf;
  SPEC/DEFINITION_OF_DONE.md only requires the decision to be *documented*, not made.
- Alternatives: default to MIT (common OSS default) or Apache-2.0.
- Consequences: `REL-004`'s final audit should re-flag this until the owner picks a
  license; MARKETING copy that references "open-source" should wait for that choice.

## D-015 — LM Studio adapter: native `/api/v1/models*` for lifecycle, OpenAI-compatible for chat
- Decision: `LMStudioProvider` uses LM Studio's native v1 REST API only for
  discovery/lifecycle (`GET /api/v1/models`, `POST /api/v1/models/load`,
  `POST /api/v1/models/unload`, verified field names: `instance_id`, `model`,
  `context_length`, `eval_batch_size`, `flash_attention`, `offload_kv_to_gpu`,
  `echo_load_config`, `status`, `load_time_seconds`) and delegates chat entirely to
  `OpenAICompatibleProvider` against LM Studio's `/v1/chat/completions`.
- Reason: LM Studio's native chat surface (`/api/v1/chat`) is *stateful* — the server
  stores conversation history server-side and returns a `response_id` for
  continuation. Harness's `ChatRequest` contract is stateless (the Context Compiler
  owns history, per SPEC/CONTEXT_COMPILER.md); adopting the stateful native chat
  endpoint would duplicate state ownership between Harness and LM Studio. The
  OpenAI-compatible endpoint matches our existing stateless contract exactly, and
  SPEC/PROVIDER_MATRIX.md explicitly names it as the fallback path.
- Verification: endpoint/field names confirmed via LM Studio's public developer docs
  (lmstudio.ai/docs/developer/rest/*) as of this implementation date, not guessed;
  `settings_schema()` only exposes the load-time fields the docs document, per
  SPEC/PROVIDER_MATRIX.md's "do not hard-code settings the installed version doesn't
  advertise."
- Consequences: if a future LM Studio version changes these field names, only this
  adapter needs updating — the contract (`LanguageProvider`) is unaffected.

## D-016 — Ollama's `model_id` doubles as its `instance_id`; load/unload ride `/api/generate`
- Decision: `OllamaProvider.load_model`/`unload_model` use `POST /api/generate` with no
  `prompt` (loads into memory) and `keep_alive: 0` (unloads), respectively — verified
  against Ollama's public API reference. `ModelInstance.instance_id` is just the model
  name; Ollama has no multi-instance concept the way LM Studio does.
- Reason: Ollama has no dedicated load/unload endpoints; the documented mechanism for
  both is a generate/chat call with specific field combinations. `LanguageProvider`'s
  `load_model`/`unload_model` contract (added for LM Studio, D-015) is general enough
  to express this without adapter-specific API changes.
- Consequences: `common.max_output_tokens` maps to Ollama's `num_predict` option
  (`_translate_common`); other common fields not present in Ollama's `options` are
  simply omitted rather than guessed.

## D-017 — `OpenAICompatibleProvider` gained an `extra_payload` hook for OpenRouter's cost accounting
- Decision: `OpenAICompatibleProvider.__init__` accepts `extra_payload: dict | None`,
  merged into every chat request. `OpenRouterProvider` subclasses it purely to set
  `{"usage": {"include": true}}`, which makes OpenRouter return an authoritative
  per-request USD cost in the final streamed usage chunk. `ChatUsage` gained an
  optional `cost` field to carry this, and the run loop now writes it into
  `RunMetrics.cost_estimate` when a provider reports it.
- Reason: OpenRouter's chat/completions endpoint is otherwise identical to the
  generic OpenAI-compatible shape (SPEC/PROVIDER_MATRIX.md explicitly groups them),
  so subclassing avoids duplicating SSE parsing; the cost field only appears in the
  response when the request opts in, so an extension point was necessary rather than
  hard-coding a new field into the base adapter for every consumer.
- Verification: `usage.cost`/`usage: {"include": true}` behavior confirmed against
  OpenRouter's public docs, not assumed.
- Consequences: any future adapter needing a small per-request payload addition (not
  a full protocol departure) can reuse the same hook instead of re-implementing chat
  streaming.

## D-018 — OpenAI/Anthropic/Gemini native adapters: one thin subclass, two dedicated implementations
- Decision: `OpenAIProvider` is a thin `OpenAICompatibleProvider` subclass (OpenAI's
  API *is* the OpenAI-compatible reference shape). `AnthropicProvider` and
  `GeminiProvider` are dedicated implementations against their real wire protocols —
  Anthropic's `/v1/messages` (top-level `system` field, required `max_tokens`,
  multi-event SSE: `message_start`/`content_block_delta`/`message_delta`/
  `message_stop`) and Gemini's `streamGenerateContent?alt=sse` (`contents` with
  `role: "user"|"model"` — not `"assistant"`, plus `usageMetadata` per chunk).
- Reason: forcing Anthropic/Gemini through the OpenAI-compatible code path would mean
  either a lossy translation layer or silently wrong behavior (e.g. dropping the
  system prompt, or omitting the `max_tokens` Anthropic requires and getting a 400).
  ADR 0003 requires adapters to match what a provider actually does.
- Verification: Gemini's classic `generateContent`/`streamGenerateContent` API was
  confirmed still fully supported (not fully replaced by the new stateful
  Interactions API, GA June 2026) and explicitly recommended for stateless calls —
  which matches Harness's contract, same reasoning as D-015/D-016. Anthropic's shape
  is Anthropic's own public API and was implemented directly, not guessed.
- Consequences: all three adapters' fixture tests passed on the first run against the
  verified shapes, which is corroborating evidence the researched details were
  accurate rather than just internally self-consistent.

## D-019 — Placement policies needing telemetry fail loudly rather than guessing
- Decision: `resolve_placement()` (LP-008) is a pure function taking explicit
  `Host` candidates and optional per-host `HostSignal`s. `prefer-fastest`,
  `prefer-lowest-pressure`, and `prefer-lowest-cost` raise `ValidationFailedError`
  when no candidate has the needed signal, rather than falling back to an arbitrary
  choice. `auto` (opt-in only, per SPEC/PROVIDER_MATRIX.md and HOSTS_AND_NODE.md) and
  `prefer-loaded` degrade to "first candidate" only when no candidate reports
  `model_loaded`, which is an honest no-preference outcome, not a fake optimization.
- Reason: ADR 0003 (capability/schema adapters, no fake parity) applies just as much
  to scheduling as to provider adapters — a "fastest" pick with no throughput data
  would be indistinguishable from a coin flip presented as if it were principled.
  Host telemetry (ANA-002) doesn't exist yet, so the signal-dependent policies simply
  cannot be honestly satisfied today.
- Consequences: `load_policy` and `tool_capability_policy` values on `ModelProfile`
  aren't enumerated by SPEC/PROVIDER_MATRIX.md (only `placement_policy` is); the
  three-value sets chosen (`manual`/`always_loaded`/`on_demand` and
  `inherit`/`disabled`/`required`) are this implementation's minimal reasonable set,
  documented here since the spec doesn't pin them down.

## D-020 — Adapter `provider_id` is overridden to the persisted `ProviderConfig.id` at construction
- Decision: `build_provider()` (LP-009) constructs the adapter matching
  `ProviderConfig.type`, resolves its secret just-in-time via `SecretStore`, then sets
  `provider.provider_id = config.id` and `provider.display_name = config.display_name`
  before registering it in the live `ProviderRegistry` — overriding the adapter
  class's fixed default (e.g. `AnthropicProvider.provider_id == "anthropic"`).
  `Application.get_or_build_provider()` is the single entry point: check the registry
  first, build-and-register on a cache miss.
- Reason: the registry is keyed by `provider_id`; if every Anthropic adapter kept the
  class-level `"anthropic"` id, a user configuring two Anthropic accounts (or two
  OpenAI-compatible endpoints) would have the second overwrite the first in the
  registry. Keying by the persisted config's own opaque id makes every configured
  provider addressable independently, matching CP-003's "persisted configuration
  distinct from the in-memory adapter registry."
- Consequences: `Binding.provider` (used throughout the run loop, SPEC/ARCHITECTURE.md
  binding precedence) now refers to a `ProviderConfig.id`, not a fixed adapter-type
  string, for anything beyond the built-in `"fake"` provider (which stays registered
  under its literal id with no backing `ProviderConfig` row, so the system works with
  zero configuration per D-010). `/language/models`, `/language/instances/load`, and
  `/language/instances/{id}/unload` all run through this same lazy-build path, and a
  single provider failing model discovery doesn't fail the whole `/language/models`
  aggregation (SPEC/ARCHITECTURE.md failure-isolation).

## D-021 — asyncssh moved from optional extra to a core dependency
- Decision: `asyncssh` was originally scoped as `[project.optional-dependencies] ssh`;
  HOST-001 moved it into the core `dependencies` list.
- Reason: ADR 0002 (agentless-first) makes SSH the foundational remote-execution
  mechanism, not an opt-in feature — "remote coding MUST work via standard SSH plus
  existing model/engine APIs" is a non-negotiable product principle (README.md), not
  something the server should be installable without.
- Consequences: `harness-os` now always installs `asyncssh`; only `node` (psutil)
  remains a true optional extra, matching NODE-001's "optional lightweight service"
  framing.

## D-022 — SSH host-key trust is explicit fingerprint pinning, not a known_hosts file
- Decision: `SSHHost._connect()` always calls `asyncssh.connect(..., known_hosts=None)`
  and does its own verification: it reads `conn.get_server_host_key()`, computes the
  fingerprint, and compares it against `Host.known_host_fingerprint` when that field is
  set. `test_connection()` returns the discovered fingerprint without requiring a match,
  so a caller can implement trust-on-first-use (show the fingerprint, get user
  confirmation, then persist it via a separate `PATCH /hosts/{id}`) rather than the
  adapter silently trusting an unpinned host.
- Reason: SPEC/HOSTS_AND_NODE.md requires "known-host verification"; a conventional
  `~/.ssh/known_hosts` file is a poor fit for a multi-user server process managing
  hosts on behalf of different sessions, and asyncssh's own known_hosts format expects
  the raw public key, not just a fingerprint — storing only the fingerprint (which is
  what fits naturally in `Host.known_host_fingerprint`, a single text column) means
  Harness owns verification directly instead of shelling out to OS SSH tooling.
- Consequences: `POST /hosts/{id}/test` (HOST-001) never raises on a fingerprint
  mismatch — it reports `{"ok": false, "error": ...}` so the caller can decide what to
  do, since "testing" a host and "trusting" a host are different actions and the API
  must not silently pin an attacker-supplied key just because someone called `/test`.

## D-023 — SSH command execution: shlex.join, not an argv-array exec request
- Decision: `SSHHost.exec_stream()` builds one command string via `shlex.join(argv)`
  (each argument individually shell-quoted) and sends that as the SSH `exec` channel's
  command. `cwd` is applied as a quoted `cd <dir> &&` prefix rather than a separate
  channel option.
- Reason: the SSH protocol's exec request (RFC 4254 §6.5) carries exactly one string,
  interpreted by the remote user's login shell — there is no argv-array exec request
  type the way local `subprocess` supports. AGENTS.md's "no shell string concatenation
  for SSH execution" therefore means *quote every argument*, not *avoid the shell
  entirely* (which SSH doesn't allow). A regression test
  (`test_exec_stream_quotes_arguments_safely`, tests/hosts/test_ssh.py) sends an
  argument containing `; && echo pwned` as a literal `echo` argument against a real
  local SSH server and asserts it comes back as inert text, not executed.
- Consequences: any future caller building argv must never pre-format a shell string
  itself — `exec_stream` owns quoting for the whole call.

## D-024 — Path safety is two-layer containment built into SSHHost, not a wrapper
- Decision: `harness.hosts.path_safety` exposes two functions rather than a class:
  `canonicalize_and_check(path, roots)` (pure, lexical POSIX `normpath` + prefix
  containment check, no I/O) and `resolve_and_check(sftp, path, roots)` (calls the
  first, then re-checks containment against the SFTP `realpath()`-resolved path).
  `SSHHost` calls the lexical check on every path-taking method (and on
  `exec_stream`'s `cwd`, when given) before opening any connection, and the
  remote-resolved check inside every SFTP operation once a client is already open.
  For paths that may not exist yet (a new file being written, a new nested directory
  tree from `mkdir`), a `_deepest_existing_ancestor()` helper walks up the path to
  the nearest ancestor SFTP reports as existing and resolves *that* instead, since
  `realpath()` needs something real to resolve against.
- Reason: path resolution happens on the *remote* host, so a purely lexical check
  can't see a symlink inside an allowed root that points outside it — only asking
  the remote host to resolve the real path closes that gap (proven by
  `test_read_file_via_symlink_escaping_root_rejected`, which creates a real symlink
  escaping the allowed root and asserts it's rejected, not just asserted lexically).
  Built directly into `SSHHost` rather than as a separate decorator/wrapper class to
  avoid duplicating connection-management and SFTP-client-lifecycle code across two
  layers; `path_safety` itself stays framework-free (a `Protocol` for the one SFTP
  method it needs) so it has no dependency on `asyncssh` connection setup and can be
  unit-tested with a fake in `tests/security/test_path_safety.py`. Fails closed: an
  empty `workspace_roots` list rejects every path rather than defaulting to
  unrestricted access, since an unconfigured host is the most common accidental
  misconfiguration and the least safe default to interpret permissively.
- Consequences: bare `exec_stream` calls with no `cwd` remain intentionally
  unscoped by workspace roots — those bound *file* access (SPEC/HOSTS_AND_NODE.md),
  not general command execution, which is a separate permission
  (`PermissionClass.EXECUTE`, still enforced at the tool-permission layer once
  TOOL-002/PERM-001 land). Every `Host` used for real file I/O must have at least
  one `workspace_roots` entry configured, or every SFTP call on it raises
  `PermissionDeniedError` immediately.

## D-025 — Workspace containment is narrower than, and additional to, Host containment
- Decision: a `Workspace` (WSP-001) pins one `root_path` on one `Host`. Every
  `/workspaces/{id}/*` endpoint that takes a caller-supplied relative path resolves
  it onto `root_path` and re-checks containment against `root_path` alone (via
  `harness.hosts.path_safety.canonicalize_and_check`) *before* calling into
  `SSHHost`, which then independently re-checks containment against the *Host's*
  (broader) `workspace_roots`. `POST /workspaces` itself is rejected up front if the
  requested `root_path` doesn't fall under the target Host's configured roots.
- Reason: a Host's `workspace_roots` is deliberately host-wide (e.g. `/home/user/
  projects`), but a single Workspace is scoped to one folder inside it (e.g. `/home/
  user/projects/proj-a`). Without a second, narrower check, a relative path like
  `../proj-b/secret.txt` sent to Workspace A's `/file` endpoint would still pass the
  Host-level check (proj-b is under the same host root) and leak into a sibling
  Workspace's files — proven by `test_workspace_file_path_cannot_escape_workspace_
  root` (tests/api/test_workspaces.py), which creates two sibling project folders
  under one Host root and confirms Workspace A cannot read Workspace B's file.
- Consequences: two independent containment checks now run on every Workspace file
  operation (workspace-root lexical check in the route handler, Host-root
  lexical+SFTP-resolved check inside `SSHHost`) — deliberate defense in depth rather
  than redundancy to remove, since they enforce different (nested) boundaries owned
  by different layers.

## D-026 — Workspace `diff` ships with WSP-001; the rest of git waits for WSP-002
- Decision: `GET /workspaces/{id}/diff` runs `git rev-parse --is-inside-work-tree`
  to detect a repo, then a real `git diff` (optionally scoped to one path) via
  `SSHHost.exec_stream`, returning `{"is_git_repo": false, "diff": ""}` rather than
  an error when the folder isn't a Git repo yet. `git init`/status/add/commit/
  branch/log are left for WSP-002.
- Reason: SPEC/WORKSPACES_ARTIFACTS.md's phone-workflow requirement ("see file tree
  and diffs") needs *some* diff view to be usable at all before a session can show
  an agent's edits, and TASKS.md's own WSP-001 acceptance line lists `diff` in its
  endpoint set alongside `tree`/`file`. Read-only `git diff` doesn't need the
  broader structured multi-subcommand plumbing (init/add/commit/branch/log) that
  WSP-002 is scoped to build; scoping it out of WSP-001 would leave phone-workflow
  step "see diffs" unimplementable until a later milestone for no real benefit.
- Consequences: WSP-002 reuses this same `exec_stream`-based pattern for its own
  git subcommands rather than introducing a second git-invocation helper.

## D-027 — Git subcommand results distinguish "failed" from "errored"
- Decision: WSP-002's `/workspaces/{id}/git/*` endpoints run every git subcommand
  through one shared `_run_git()` helper that never raises on a nonzero exit — it
  returns `(exit_status, stdout, stderr)` and each endpoint decides what a failure
  means. `git commit` with nothing staged (or no author identity configured)
  returns HTTP 200 with `{"ok": false, "output": ...}`; `git init`/`add`/`branch`
  raise `ProviderError` (502) on a nonzero exit, since those have no legitimate
  "expected to fail" case the way an empty commit does. `git status`/`log` report
  `is_git_repo: false` / `[]` rather than erroring when the workspace isn't a repo
  yet or has no commits.
- Reason: "nothing to commit" is a routine, expected outcome of calling `git commit`
  in normal use (e.g. an agent re-running a commit step after a prior run already
  committed the same changes) — treating it as a 5xx would make ordinary polling/
  retry flows look like server errors. `git init` failing, by contrast, means
  something is actually wrong (permissions, disk, not a valid path) and should
  surface as an error. Test coverage
  (`test_git_commit_with_nothing_staged_reports_failure_not_error`,
  tests/api/test_workspaces_git.py) pins this distinction against a real git commit
  invocation, not just an assumption about git's exit codes.
- Consequences: any future git subcommand endpoint must decide, case by case,
  whether its failure modes are "normal, report as ok:false" or "abnormal, raise" —
  there's no blanket rule the router applies automatically.

## D-028 — Tool permission resolution is a Protocol; PERM-001 fills it in later
- Decision: `ToolExecutor` (TOOL-001) takes a `PermissionResolver` — a `Protocol`
  with one method, `resolve(permission_class) -> "allow"|"ask"|"deny"` — as a
  constructor argument rather than importing a concrete permission engine. The only
  implementation that exists yet, `AllowAllResolver`, always returns `"allow"`.
  `Application` wires it in `create_application()`. The lifecycle's branching on
  all three outcomes (`deny` -> `ToolRun.status="denied"` + `tool.denied`; `ask` ->
  `status="pending_approval"` + `tool.pending_approval`; `allow` -> execute) is
  fully implemented and unit-tested with a fake resolver
  (`tests/unit/test_tool_lifecycle.py`), even though nothing in the running system
  can currently produce `ask`/`deny` outcomes.
- Reason: TOOL-001 (this task) and PERM-001 (a real class×policy resolver with a
  persisted decision table and an approval-blocking API) are separate TASKS.md
  entries with TOOL-002 depending on both. Building the lifecycle against an
  abstract resolver now means PERM-001 is a pure additive change later — a new
  `PermissionResolver` implementation swapped into `create_application()` — with no
  changes to `ToolExecutor`, `ToolRun`, the event names, or any test that already
  exercises the three-way branch.
- Consequences: until PERM-001 lands, every tool call effectively runs
  unconditionally once a caller reaches `ToolExecutor.execute()` — acceptable
  because the only tool registered so far (`echo`) is read-only and side-effect
  free; TOOL-002's file/shell/git tools must not be registered before PERM-001
  supplies a real resolver, since those carry `write`/`execute`/`git` permission
  classes that need actual policy enforcement.

## D-029 — Tool execution runs through JobManager like model load/unload
- Decision: `POST /tools/{name}/run` submits a `JobManager` job whose work function
  calls `ToolExecutor.execute()` and returns `{"tool_run_id": ..., "status": ...}`;
  the endpoint responds `202` with the `Job`, not the `ToolRun` directly. Callers
  poll `/jobs/{id}` for scheduling status or `/tools/runs/{id}` for the
  lifecycle-specific record (permission decision, compact result, error).
- Reason: matches LP-009's existing split for model load/unload — Job records
  generic scheduling/cancellation state, the domain-specific repo (here, ToolRun)
  records what actually happened. A future TOOL-002 shell tool invoking a
  long-running remote command needs the same cancelability `JobManager` already
  gives every other long action (SPEC/API_CONTRACT.md); building tool execution on
  a plain synchronous endpoint now would mean revisiting every caller once a real
  long-running tool exists, whereas building it on Jobs from the start costs
  nothing extra for `echo` (which finishes instantly) and is already correct for
  what comes next.
- Consequences: a `ToolRun`'s `id` is not the same as its `Job`'s `id` — API
  clients that need the `ToolRun` must look it up (by tool name, or by listing
  `/tools/runs` after the Job succeeds) rather than assume the Job's own ID.
