# MCP, Skills, Tools, Superpowers

## Principle

- Tool = capability.
- Skill = methodology.
- MCP = capability provider.
- "Superpower" = user-facing toggle that activates a bounded bundle of tools/skills/MCP/provider permissions.

## MCP

MCP is first-class but lazy.

Store server definitions and a compact tool index:
- server ID
- tool name
- one-line description
- estimated schema tokens
- trust/permission class

Do not send all MCP schemas to every model.

The model can request discovery:
`capabilities.search("GitHub pull requests")`

The runtime may activate only the chosen tool schemas.

## Skills

Skill package:
- metadata,
- SKILL.md body,
- optional scripts,
- references,
- activation rules,
- tool requirements,
- context cost estimate.

## Tool lifecycle

1. model requests tool
2. validate schema
3. resolve permission
4. request approval if needed
5. execute
6. capture stdout/result/error
7. create artifact if applicable
8. emit events
9. return compact result to model

## Superpower bundles

Seed bundles:
- Coding
- Git/GitHub
- Browser
- Creative
- Research
- Remote Host
- Benchmarking

Bundles are convenience UI only; underlying permissions remain explicit.

## Frontier-model extensibility

Cloud/frontier models can be granted:
- capability discovery,
- skill activation,
- agent/contact delegation,
- tool use,
- artifact retrieval.

They may not mutate Harness configuration or grant themselves permissions unless a human explicitly allows that action.
