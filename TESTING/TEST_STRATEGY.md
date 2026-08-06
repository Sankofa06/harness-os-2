# Test Strategy

## Unit
- context budgeting
- precedence/binding snapshots
- permission resolution
- capability negotiation
- settings-schema validation
- path safety
- mention/team parsing
- artifact references
- analytics calculations

## Contract
Each adapter uses recorded/synthetic fixtures and optional live tests.

## Integration
- fake OpenAI-compatible server
- fake LM Studio v1 server
- fake Ollama server
- fake ComfyUI server
- fake A1111-compatible server
- local SSH container/server fixture where practical
- WebSocket event replay

## End-to-end
Playwright:
- onboarding
- add host/provider
- create workspace
- start chat
- @mentions
- switch binding
- approve tool
- creative generation
- analytics
- portrait/landscape layouts

TUI:
- API connection
- navigation
- chat
- approval
- binding switch

## Context regression test
Compile representative sessions and assert limits.

## Security
- traversal
- unauthorized API
- secret redaction
- malicious rendered markdown/tool output
- command injection
- websocket auth
