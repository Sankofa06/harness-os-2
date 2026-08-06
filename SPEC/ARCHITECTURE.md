# Architecture

## Topology

```text
Clients
  ├─ CLI
  ├─ TUI
  ├─ WebUI
  └─ GitHub Pages static shell/site
          |
          v
Harness API + Event Stream
          |
  +-------+--------+------------------+
  |                |                  |
Agent Runtime   Control Plane      Persistence
  |                |                  |
  |       +--------+--------+         |
  |       |        |        |         |
Models   Hosts   Creative   MCP      SQLite
  |       |        |        |
local/   SSH/     APIs/     lazy
cloud    Node     adapters  discovery
```

## Modules

### `core`
Pure domain models, capability vocabulary, errors, IDs, config precedence.

### `events`
Append-only event model, local event bus, websocket fanout, replay cursor.

### `persistence`
SQLite repositories, migrations, run history, snapshots, benchmark records.

### `providers.language`
Adapters for language-model systems.

### `providers.creative`
Adapters for creative engines and Stability Matrix installations.

### `hosts`
SSH agentless host adapter and optional Node adapter.

### `tools`
Native tool registry, typed schemas, permissions, execution lifecycle.

### `mcp`
MCP discovery/indexing, lazy schema expansion, server lifecycle.

### `skills`
Metadata index, activation rules, lazy body load.

### `agents`
Roles, personas, Contacts, teams, delegation, routing.

### `context`
Context Compiler, compaction, summaries, artifact references, token budgets.

### `jobs`
Cancelable async jobs with state machine.

### `artifacts`
Typed artifact catalog and storage/reference abstraction.

### `analytics`
Normalized metrics, model/host/agent/creative performance aggregation.

### `api`
REST resource API + WebSocket event stream.

### `node`
Minimal optional node daemon.

## Binding precedence

Effective configuration MUST resolve in this order:

1. turn override
2. session/contact override
3. contact default
4. role default
5. system default

All resolved settings MUST be snapshot into each Agent Run before inference.

## Compute separation

Never conflate:

- **Inference Host** — where model execution happens.
- **Execution Host** — where workspace/file/shell/git operations happen.
- **Harness Host** — where orchestration/API/persistence runs.
- **Creative Host** — where image/video/training engine runs.
- **Client Device** — where UI is rendered.

They may all be different.

## Agentless execution

Remote coding requires only:
- network reachability,
- SSH credentials/key,
- configured safe workspace roots.

No Harness repository clone or Node daemon is required.

## Control plane vocabulary

Every manageable subsystem SHOULD expose as applicable:

- identity
- capabilities
- state
- settings schema
- current settings
- actions
- telemetry
- historical metrics
- health
- events

Adapters declare unsupported capabilities explicitly.

## Event-driven rule

Every important state transition emits an event. UI clients render the event stream and fetch resource state through REST.

Representative events:

- session.started
- session.updated
- run.started
- run.binding_snapshot
- context.compiled
- model.load.requested
- model.load.progress
- model.loaded
- model.unloaded
- inference.started
- inference.first_token
- inference.token_usage
- inference.completed
- tool.requested
- tool.approval_required
- tool.started
- tool.completed
- tool.failed
- agent.spawned
- agent.completed
- host.health
- creative.job.started
- artifact.created
- benchmark.completed
- run.failed

## Failure isolation

A failed provider, node, MCP server, or creative engine MUST NOT crash the Harness server. Adapters use circuit-breaker/backoff behavior and surface degraded state.
