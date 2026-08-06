# Contacts, Roles, Personas, Teams

## Contact

A Contact is the stable human-facing identity.

```yaml
handle: builder
display_name: Builder
role: coder
personas: [pragmatic, test-first]
binding:
  language_profile: local-coder
  execution_host: auto
```

Changing the underlying model MUST NOT change the Contact identity/history.

## Role

Defines responsibility, permissions defaults, and operational expectations.

Built-in seed roles:
- orchestrator
- architect
- researcher
- coder
- reviewer
- tester
- designer
- operator

Users can create arbitrary custom roles.

## Persona

Small stackable modifiers:
- behavioral,
- domain,
- style,
- quality bar.

Examples in demo fixtures:
- concise
- skeptical-reviewer
- systems-thinker
- accessibility-first
- test-first
- minimal-dependencies

## Team

Named Contact group:

```yaml
handle: dev-team
members: [architect, builder, tester, reviewer]
```

## Mentions

Parser supports:
- `@contact`
- multiple contacts
- `@team`
- `@everyone`
- direct delegation syntax inferred from natural language.

Explicit mention bypasses orchestrator unless orchestration is required by the request or configured room policy.

## Session overrides

A contact can change model, provider, host, runtime settings, personas, or capabilities for:
- one turn,
- current session,
- persistent default.

Every run records the resolved snapshot.
