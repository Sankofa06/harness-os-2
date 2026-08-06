# Harness OS

Harness OS is a local-first agent operating system and AI compute control plane. It
unifies local/cloud language-model providers, role/persona-based agent "Contacts",
agentless SSH remote execution, MCP/skills, creative compute (Stability Matrix,
ComfyUI, A1111-style backends), artifacts, and analytics behind one versioned API,
with a TUI and a responsive WebUI as equal clients of that API.

This repository contains both the build specification (`SPEC/`, `ADR/`, `BUILD/`,
`TESTING/`, `CONFIG/`, `MARKETING/` — see `README.spec-kit.md`) and the implementation
that follows it. `TASKS.md`, `STATUS.md`, `DECISIONS.md`, and `TEST_MATRIX.md` track
implementation progress against `SPEC/DEFINITION_OF_DONE.md`.

## Install

Requires Python 3.12+ and Node.js 20+.

```bash
uv sync              # backend dependencies (see pyproject.toml)
cd web && npm install && cd ..   # WebUI dependencies
```

## Use

```bash
uv run harness serve --host 127.0.0.1 --port 4096   # start the API server
uv run harness tui --api http://127.0.0.1:4096       # start the TUI client
cd web && npm run dev                                # start the WebUI dev server
```

Deterministic seeded demo data (no real credentials or network calls):

```bash
HARNESS_DEMO_MODE=1 uv run harness serve
```

See `DEPLOYMENT.md` for private-network phone access and remote-host setup, and
`.env.example` for configuration knobs.

## Security

- The server binds `127.0.0.1` by default. Binding elsewhere requires an explicit
  `--host` flag.
- Non-loopback requests (REST and WebSocket) require a bearer token, generated on
  first start into `<data_dir>/api_token` (mode `0600`). Loopback requests are
  trusted by default (`auth.local_trust`); set it to `false` to require the token
  everywhere.
- Secrets are never stored in plaintext config, database rows, logs, or events — see
  `SPEC/SECURITY_PRIVACY.md` for the secret-store chain and permission model.
- Remote filesystem/shell access is scoped to configured workspace roots with path
  canonicalization; see `SPEC/HOSTS_AND_NODE.md`.

## Architecture

```
Clients (CLI / TUI / WebUI / static Pages shell)
        |
Harness API + Event Stream  (/api/v1, WebSocket /api/v1/events)
        |
Agent Runtime · Control Plane · Persistence (SQLite)
        |
Language & Creative Providers · Hosts (SSH / optional Node) · MCP · Tools
```

See `SPEC/ARCHITECTURE.md` for the full module map and control-plane vocabulary, and
`ADR/` for the standing architectural decisions (API-first/event-driven, agentless-first
remote hosts, capability/schema adapters, budgeted context, stable Contact identity,
static GitHub Pages).

## Repository layout

- `src/harness/` — Python backend: `core`, `events`, `persistence`, `providers`,
  `hosts`, `workspaces`, `agents`, `context`, `tools`, `mcp`, `skills`, `artifacts`,
  `analytics`, `api`, `node`, `tui`.
- `web/` — React + TypeScript WebUI.
- `site/` — static GitHub Pages landing/docs/screenshots.
- `tests/` — backend test suite.
- `CONFIG/examples/` — example configuration and profile YAML.

## Contributing

See `CONTRIBUTING.md`.

## License

See `LICENSE` (license selection tracked in `DECISIONS.md`).
