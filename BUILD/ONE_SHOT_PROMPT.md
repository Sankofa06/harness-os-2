# One-Shot Build Prompt

You are the lead architect and implementation team for Harness OS.

The current directory contains the complete authoritative product and architecture specification. Read **all** `.md`, `.yaml`, and schema files before writing code. Build the complete product in this repository.

Your goal is not to create a prototype. Your goal is to satisfy `SPEC/DEFINITION_OF_DONE.md`.

## Absolute rules

- Do not ask questions already answered by the specs.
- Do not replace requirements with placeholders or TODOs.
- Do not embed any creator-specific machine names, model names, paths, credentials, or personal data.
- Keep the core lightweight and context-budgeted.
- Remote execution must work agentlessly over SSH.
- Harness Node must remain optional.
- Both TUI and WebUI must consume the same API.
- Implement capability-aware adapters rather than fake parity.
- Creative compute is first-class, not a single ComfyUI textbox.
- Model runtime settings are first-class and schema-driven.
- Implement deterministic demo mode and create marketing screenshots.
- Treat security/permissions as product features.

## Work continuously

Create an internal checklist from Definition of Done and execute it to completion. Run tests frequently. Resolve failures. Inspect the final repository for unfinished work.

## Repository shape

You may choose the exact package layout, but keep clear boundaries for:
core, events, persistence, providers, hosts, agents, context, tools, MCP, skills, jobs, artifacts, analytics, API, node, TUI, WebUI, site.

## End state

At completion:
- API runs,
- TUI runs,
- WebUI runs,
- demo mode runs,
- screenshots exist,
- docs exist,
- GitHub Pages workflow exists,
- marketing files exist,
- tests/typecheck/lint pass,
- repository is initialized and committed,
- push if a configured remote and credentials are available,
- print concise exact startup commands and any integration prerequisites that cannot be automated.

Do not declare success until the Definition of Done audit passes.
