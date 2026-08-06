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
