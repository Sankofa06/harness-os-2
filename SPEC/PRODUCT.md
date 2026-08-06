# Product Specification

## Product statement

Harness OS is a local-first agent operating system and AI compute control plane. It lets a user open a conversation, include named AI "Contacts", dynamically bind those contacts to local or cloud models and machines, delegate work, execute against remote workspaces, generate creative assets, observe resource state, and benchmark everything from a single lightweight interface.

## Primary user experience

A user opens the TUI or WebUI, creates or opens a Workspace, adds one or more Contacts, and types:

> @planner and @alternate make independent plans. Have @reviewer reconcile them. If approved, @builder implement it and @tester run the checks.

The UI displays the orchestration graph, messages, tool calls, model loading/unloading state, remote workspace activity, host pressure, token speed, artifacts, and approvals.

## Core entities

- **Contact**: stable human-facing identity/handle.
- **Role**: responsibility and default operational policy.
- **Persona**: small behavioral/domain modifier.
- **Binding**: model/provider/host/runtime settings attached at global/contact/session/turn scope.
- **Agent Run**: execution of a Contact under a binding snapshot.
- **Workspace**: bounded project root on an execution host.
- **Host**: machine capable of inference, execution, creative compute, telemetry, or some subset.
- **Language Engine**: model provider/runtime.
- **Creative Engine**: image/video/training runtime.
- **Skill**: methodology/instructions activated lazily.
- **Tool**: callable capability.
- **MCP Server**: external tool provider.
- **Artifact**: typed output referenced by ID, not automatically injected into context.
- **Job**: tracked unit of work.
- **Benchmark Suite/Run**: reproducible evaluation using normalized telemetry.

## Product modes

### Harness Mode
Full server, API, orchestration, persistence, WebUI, TUI client support.

### Agentless Host Mode
No Harness install remotely. Use:
- SSH for filesystem/shell/git/process execution.
- existing provider APIs such as LM Studio/Ollama/etc for inference.
- existing creative APIs for generation.

### Node Mode
Optional lightweight service installed on a host to provide:
- normalized host telemetry,
- richer GPU/VRAM pressure,
- process discovery/control,
- model/engine discovery,
- model load state,
- creative engine health,
- workspace watches,
- heartbeats,
- capability advertisement.

Node Mode MUST NOT be required for remote coding.

## User-facing navigation

- Chats
- Agents
- Workspaces
- Compute
- Models
- Creative
- Assets
- Skills
- MCP
- Analytics
- Settings

## Design keywords

Dense but legible, technical, modern, cinematic without being gimmicky, "mission control", responsive, inspectable, graph-centric, fast.

## Out of scope for v1

- multi-user SaaS accounts,
- mandatory cloud backend,
- billing,
- proprietary telemetry collection,
- arbitrary internet exposure without authentication,
- mobile-native implementation (specified separately in the mobile kit),
- replacing Stability Matrix as a package manager.
