# API Contract

Base: `/api/v1`

All mutating endpoints return resource state plus correlation ID. Long actions create Jobs.

## Core REST resource groups

### System
- `GET /health`
- `GET /system/info`
- `GET /capabilities`

### Sessions / Chats
- `GET/POST /sessions`
- `GET/PATCH/DELETE /sessions/{id}`
- `POST /sessions/{id}/messages`
- `POST /sessions/{id}/stop`
- `GET /sessions/{id}/graph`

### Contacts / Roles / Personas / Teams
CRUD:
- `/contacts`
- `/roles`
- `/personas`
- `/teams`

Overrides:
- `PATCH /sessions/{id}/contacts/{contact_id}/binding`
- `POST /sessions/{id}/turn-overrides`

### Hosts
- `/hosts`
- `/hosts/{id}/test`
- `/hosts/{id}/capabilities`
- `/hosts/{id}/health`
- `/hosts/{id}/workspaces/browse`

### Workspaces
- `/workspaces`
- `/workspaces/{id}/tree`
- `/workspaces/{id}/file`
- `/workspaces/{id}/diff`
- `/workspaces/{id}/git/*`

### Language providers/models/instances
- `/language/providers`
- `/language/models`
- `/language/models/{id}`
- `/language/instances`
- `/language/instances/load`
- `/language/instances/{id}/unload`
- `/language/instances/{id}/settings-schema`
- `/language/instances/{id}/settings`

### Creative
- `/creative/installations`
- `/creative/engines`
- `/creative/engines/{id}/capabilities`
- `/creative/engines/{id}/settings-schema`
- `/creative/assets`
- `/creative/profiles`
- `/creative/jobs`
- `/creative/workflows`

### MCP / Skills / Tools
- `/mcp/servers`
- `/mcp/tools/index`
- `/skills`
- `/skills/{id}/activate`
- `/tools/index`

### Artifacts
- `/artifacts`
- `/artifacts/{id}`
- `/artifacts/{id}/content`
- `/artifacts/{id}/transfer`

### Analytics
- `/analytics/runs`
- `/analytics/models`
- `/analytics/hosts`
- `/analytics/agents`
- `/analytics/creative`
- `/benchmarks`

### Jobs
- `/jobs`
- `/jobs/{id}`
- `POST /jobs/{id}/cancel`

### Settings/secrets
- `/settings`
- `/secrets/metadata`
- `/secrets/{id}/test`

Never return secret values.

## Event transport

WebSocket: `/api/v1/events`

Client subscribes by filters:
- session IDs
- job IDs
- host IDs
- event types

Events:
```json
{
  "event_id": "evt_...",
  "type": "inference.first_token",
  "timestamp": "...",
  "correlation_id": "...",
  "resource": {"type": "run", "id": "run_..."},
  "payload": {}
}
```

Payloads are versioned.

## OpenAPI

The implementation MUST publish:
- `/openapi.json`
- human docs in development mode.

Generate typed TS client from OpenAPI; do not hand-maintain duplicate request types.
