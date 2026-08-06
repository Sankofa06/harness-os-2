# Harness OS — Spec-Driven Development Kit

Harness OS is a lightweight, extensible agent operating system that unifies:

- local and cloud language-model providers,
- role/persona based agent contacts,
- MCP and lazy-loaded skills/tools,
- agentless SSH workspace execution,
- optional lightweight node telemetry,
- model/engine runtime management,
- Stability Matrix and creative-generation backends,
- artifacts and project workspaces,
- analytics and benchmarking,
- a shared API powering both TUI and responsive WebUI,
- remote phone use over secure user-managed networking such as Tailscale.

This repository is a **build specification**, not the implementation.

A coding agent should be able to start in a blank directory containing these files and build the complete application without inventing architecture. Where a provider/engine exposes fewer capabilities than another, the implementation MUST use capability negotiation rather than fake parity.

## Non-negotiable product principles

1. **Context is expensive.** The default agent bootstrap must target <= 4K tokens and SHOULD remain <= 8K in normal coding sessions. Full optional capability expansion must remain <= 16K unless the user explicitly opts into more.
2. **Everything is lazy.** Tools, MCP schemas, skill bodies, asset metadata, and large histories are loaded only when required.
3. **Bindings are not identities.** A Contact persists while model, inference host, execution host, persona, and settings can change per global default, session, or turn.
4. **Agentless first.** Remote coding MUST work via standard SSH plus existing model/engine APIs. Installing Harness Node is optional.
5. **One control plane.** Hosts, language engines, creative engines, model instances, jobs, tools, artifacts, and agents all expose capability/state/settings/telemetry/history in a consistent vocabulary.
6. **API first.** CLI/TUI/WebUI are clients of the same versioned API/event stream.
7. **Public product.** Do not seed, hard-code, document, or ship any creator-specific hostnames, credentials, model names, file paths, or personal data.
8. **Local-first privacy.** Secrets remain local. Telemetry is local by default. No analytics leave the installation unless a future opt-in feature is explicitly added.
9. **Transparent autonomy.** Every tool action is observable, attributable, interruptible, and permission-gated.
10. **Beautiful is a requirement.** The TUI and WebUI use the same information architecture and visual grammar. Landscape is the power-user mobile layout; portrait is fully functional.

## Definition of Done

The implementation is done only when all acceptance criteria in `SPEC/DEFINITION_OF_DONE.md` pass.

Start with:

1. `AGENTS.md`
2. `SPEC/PRODUCT.md`
3. `SPEC/ARCHITECTURE.md`
4. `SPEC/API_CONTRACT.md`
5. `SPEC/DEFINITION_OF_DONE.md`
6. `BUILD/ONE_SHOT_PROMPT.md`

Do not skip the decision records in `ADR/`.
