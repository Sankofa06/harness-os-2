# Definition of Done

The product is NOT complete until all of the following are demonstrably true.

## API

- Server starts from clean install with one command.
- `/health`, OpenAPI, REST resources and WebSocket stream work.
- API is versioned.
- Server can bind localhost or an explicitly chosen interface/port.
- Auth protects remote access.
- API contract tests pass.

## Context

- Empty/default Contact bootstrap measured <= 4K tokens.
- Standard coding session harness overhead <= 8K tokens.
- Tool/MCP/skill bodies are lazy.
- Context budget UI/report works.
- Tests fail if accidental eager schema injection regresses the budget.

## Providers

- Generic OpenAI-compatible adapter works.
- LM Studio native discovery/list/load/unload/settings works against a supported install or integration test fixture.
- Ollama adapter works or is exercised against deterministic fixture when not installed in CI.
- OpenRouter and at least OpenAI/Anthropic/Gemini cloud adapters are implemented with secret references.
- Provider-specific settings schemas render in UI.
- Unknown provider failure is graceful.

## Hosts/workspaces

- Add SSH host.
- Test connection.
- Browse allowed root.
- Create folder remotely.
- Create Workspace.
- Read/write files remotely.
- Run shell command with streamed output.
- Initialize/use Git.
- Cancel command.
- Works without Harness Node on remote host.

## Node

- Optional node registers and authenticates.
- Basic CPU/RAM/disk telemetry.
- GPU/VRAM telemetry where supported.
- Runtime/engine health advertised.
- Missing sensor does not break node.

## Agents

- Create Role, Persona, Contact, Team.
- Mention one/many/team contacts.
- Change Contact model/host globally, per session, per turn.
- Binding snapshots prove changes without losing conversation identity.
- Parallel plan -> review -> implementation workflow functions.
- Stop/cancel works.

## MCP/skills/tools

- Add MCP server.
- Tool index remains compact.
- Schema loads only when activated.
- Skill metadata indexes without loading body.
- Superpower toggles modify capability exposure.
- Permission ask/allow/deny works.

## Creative

- Stability Matrix installation discovery supports documented Data layout.
- Installed package catalog shows package type/platform.
- ComfyUI deep adapter can submit workflow and capture output.
- Compatible A1111/Forge-style adapter supports capabilities actually exposed.
- Other Stability Matrix package families are represented with capability level, not fake controls.
- Creative asset catalog deduplicates shared assets.
- Creative Profile works.
- Batch checkpoint/profile comparison works with deterministic fixture.
- Output becomes Artifact with provenance.

## Analytics

- Every inference run persists tokens/duration/model/contact/binding.
- tok/s and TTFT stored when available/calculable.
- Tool metrics stored.
- Host telemetry visualized.
- Creative run metrics stored.
- Benchmark suite can compare multiple contacts/models and multiple creative profiles.
- No telemetry leaves machine.

## WebUI

- Desktop/landscape three-panel view.
- iPhone landscape fully useful.
- iPhone portrait fully useful.
- Conversation streaming.
- Graph view.
- file/workspace browser.
- model instance/settings view.
- compute view.
- creative view.
- assets view.
- analytics.
- approval flows.
- accessibility audit passes target.

## TUI

- Uses API, not direct database/runtime shortcuts.
- Chat, mentions, graph/status, contacts, hosts, files, model settings, approvals.
- Keyboard-first.
- Works concurrently with WebUI against same Harness server.

## Phone

A user on the same secure private network can:
1. open WebUI,
2. authenticate,
3. select a remote SSH host,
4. create/select a folder,
5. start a session,
6. assign a Contact/model,
7. create/edit files on that machine,
8. run commands/tests,
9. view results/artifacts,
10. switch model/host without restarting session.

## Demo/marketing

- deterministic seeded demo mode,
- screenshot generation script,
- required screenshots generated,
- no personal data.

## Repository

- README with install/use/security/architecture.
- CONTRIBUTING.
- LICENSE placeholder decision documented.
- tests/lint/typecheck.
- CI.
- Git initialized.
- clean working tree after final commit.
- remote pushed if credentials/remote are available.
- GitHub Pages deployment workflow.
- marketing markdown files.

## No-placeholder audit

Search repository for:
- TODO
- FIXME
- placeholder
- mock-only production code
- creator-specific names
- example API keys

Every hit must be justified or removed.
