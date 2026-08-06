# Persistence/Data Model

Use normalized SQLite tables with migrations.

Minimum tables:

- settings
- secret_refs
- hosts
- host_capabilities
- host_samples
- providers
- models
- model_instances
- model_profiles
- roles
- personas
- contacts
- contact_personas
- teams
- team_members
- sessions
- session_members
- binding_snapshots
- messages
- runs
- run_metrics
- tools
- tool_runs
- mcp_servers
- mcp_tool_index
- skills
- skill_activations
- workspaces
- jobs
- artifacts
- creative_installations
- creative_engines
- creative_assets
- creative_profiles
- creative_runs
- benchmark_suites
- benchmark_runs
- events

Large blobs/workflow files/artifacts should live on disk/object store with DB metadata unless small.

All IDs use opaque prefixed IDs (e.g. `host_`, `run_`, `art_`).

Events are append-only and have retention/compaction policy.
