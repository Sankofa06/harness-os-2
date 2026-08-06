# AGENTS.md — Build Contract for Coding Agents

You are implementing Harness OS from these specifications.

## Operating mode

- Treat the specs as authoritative.
- Do not replace concrete requirements with placeholders, TODOs, mocks, "future support", or fake data except where the spec explicitly calls for seeded demo fixtures.
- Do not ask product questions that the specs already answer.
- When an external integration cannot expose a requested capability, implement the adapter with an explicit unsupported capability and a clear UI state.
- Prefer the smallest dependency set that meets the requirements.
- Keep the core engine UI-agnostic.
- Keep adapters isolated.
- The server, TUI, and WebUI MUST use public internal contracts rather than bypassing layers.
- No creator-specific or personal data may appear anywhere.

## Required implementation sequence

1. Create repository and baseline CI.
2. Implement domain types, persistence, config, secrets abstraction, event bus.
3. Implement provider/engine capability contracts and registries.
4. Implement language providers and SSH execution.
5. Implement context compiler and agent loop.
6. Implement Contacts/Roles/Personas/Skills/MCP.
7. Implement workspaces, artifacts, permissions, jobs.
8. Implement analytics/benchmark capture.
9. Implement Stability Matrix / creative adapters.
10. Implement optional Node service.
11. Implement API + WebSocket event protocol.
12. Implement TUI and WebUI in parallel against the API.
13. Implement seeded demo mode and screenshot automation.
14. Implement docs, GitHub Pages, marketing assets.
15. Run the complete acceptance suite.
16. Commit all files, initialize Git if needed, and prepare the repository for push. If credentials/remotes are available, push. If not, leave exact commands in `DEPLOYMENT.md`; never fabricate a successful push.

## Quality bar

The project must be runnable, testable, documented, typed, linted, and production-shaped. No silent exception swallowing. No giant god classes. No tool-schema dumps into prompts. No plaintext secrets. No shell string concatenation for SSH execution. No arbitrary remote path traversal outside configured workspace roots.

## Expected tech direction

The specification assumes:

- Python 3.12+ core/server
- FastAPI (or equivalently lightweight ASGI framework) for API
- Pydantic v2 for schemas/settings
- SQLite + SQLModel/SQLAlchemy for local persistence
- Textual for TUI
- React + TypeScript + Vite for WebUI
- WebSocket/SSE for streaming/events
- asyncssh for SSH
- httpx for adapters
- keyring/OS secret store abstraction with environment-variable fallback
- pytest for backend
- Vitest + Playwright for web
- GitHub Actions for CI
- static GitHub Pages shell/site

Deviate only when the replacement is clearly lighter or more robust, and document the decision in a new ADR.
