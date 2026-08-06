# Contributing

Harness OS is developed spec-first: `SPEC/`, `ADR/`, and `AGENTS.md` are authoritative.
Read `AGENTS.md` before making changes — it defines the operating contract for
implementation work in this repository.

## Workflow

1. Check `TASKS.md` for the relevant task ID and its acceptance criteria/dependencies.
2. Implement the smallest change that satisfies the acceptance criteria. Prefer the
   smallest dependency set (AGENTS.md).
3. Add or update tests alongside the change — see `TEST_MATRIX.md` for what each
   Definition of Done requirement maps to.
4. Update `TASKS.md` (status), `STATUS.md` (current state), and — for any decision not
   already covered by an ADR — `DECISIONS.md`.
5. Run the full local check before opening a PR.

## Local checks

Backend:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/harness
uv run pytest tests -q
```

WebUI:

```bash
cd web
npm run lint
npm run test
npm run build
```

End-to-end (requires a running `harness serve` and `npm run dev`):

```bash
cd web
npx playwright test
```

## Conventions

- No placeholders, TODOs, or mock-only production code (AGENTS.md). Seeded demo
  fixtures under `HARNESS_DEMO_MODE=1` are the one sanctioned exception.
- No creator-specific machine names, paths, credentials, models, or personal data
  anywhere in the repository, including tests and fixtures.
- Adapters declare capabilities explicitly rather than faking parity with a provider
  that doesn't support a feature (ADR 0003).
- Context is a budgeted resource (ADR 0004) — new context sources must stay lazy and
  be covered by `tests/context/test_compiler.py`'s regression assertions.
- Every meaningful state transition emits an event (SPEC/ARCHITECTURE.md).

## Commit messages

Describe why the change was made, not just what changed. Reference the `TASKS.md`
task ID where applicable.
