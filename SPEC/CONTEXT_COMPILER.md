# Context Compiler

The Context Compiler is a first-class subsystem.

## Goals

- Default bootstrap <= 4K tokens.
- Normal coding turn SHOULD remain <= 8K before user/workspace content.
- Full optional capabilities SHOULD remain <= 16K.
- Never inject every MCP/tool/skill schema.
- Prefer references + retrieval to transcript stuffing.

## Layers

1. immutable minimal Harness protocol
2. active Role
3. active Persona modifiers
4. current session objective/state summary
5. relevant recent conversation
6. selected workspace facts
7. activated skills
8. active tool schemas
9. active MCP schemas
10. requested artifact excerpts
11. task-specific memory

## Lazy capability mechanism

The always-visible tool surface should be tiny:

- `capabilities.search`
- `skills.activate`
- `tools.describe`
- `artifacts.get`
- `agents.delegate`
- minimal filesystem/shell tools only if permission allows

`capabilities.search("github pull requests")` returns concise candidates. Only selected schemas are compiled on the next model call.

## Skill format

Skill metadata is always cheap; body is lazy.

```yaml
id: swift-development
description: Build, debug and test Swift projects.
activation_hints: ["*.swift", "xcode", "swiftui"]
estimated_tokens: 700
required_capabilities: ["filesystem.read", "shell.exec"]
```

## Persona budget

Personas are modifiers, not giant prompts:
- target 50–200 tokens each,
- stackable,
- conflict-resolved by deterministic precedence.

## Transcript management

Use:
- recent-turn window,
- structured session state,
- rolling summaries,
- preserved tool outcomes,
- artifact references.

Never summarize away:
- unresolved user requirements,
- current plan,
- changed files,
- failing tests,
- permission decisions.

## Budget enforcement

Compiler outputs a budget report:

```json
{
  "max": 8192,
  "used": 5320,
  "sections": {
    "base": 420,
    "role": 185,
    "personas": 160,
    "history": 1700,
    "skills": 820,
    "tools": 980,
    "workspace": 740,
    "artifacts": 315
  }
}
```

UI exposes this report.
