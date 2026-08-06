# UI / UX Specification

## Shared information architecture

TUI and WebUI MUST share:
- navigation names,
- resource states,
- keyboard/action concepts,
- color/status semantics,
- orchestration graph meaning,
- settings hierarchy.

They do not need pixel-identical rendering.

## Web layouts

### Desktop / landscape phone / tablet
Three-panel mission-control layout:

1. left rail: workspace, contacts, hosts
2. center: conversation + orchestration graph toggle/split
3. right inspector: selected contact/run/model/host/engine

Responsive breakpoints MUST allow landscape iPhone to retain at least two useful panes.

### Portrait phone
Single main pane with:
- compact top status,
- conversation,
- bottom composer,
- slide-over sheets for Contacts, Graph, Files, Inspector, Compute.

Portrait must not be a read-only mode.

## Primary views

### Chat
- streaming responses
- @mention autocomplete
- Contact identity chips
- tool cards
- approval cards
- artifacts
- inline progress
- context meter
- speed indicator

### Graph
Animated but efficient directed execution graph:
- user/orchestrator/contacts/jobs/tools
- edges show delegation/handoff
- statuses: queued, thinking, generating, tool-use, waiting, done, failed
- selecting node opens inspector
- show model load/unload and host move as infrastructure events

### Compute
Host cards:
- online/degraded/offline
- CPU/RAM/GPU/VRAM
- running models/engines
- active jobs
- inference speed/history

### Models
- provider/runtime grouping
- downloaded/available/loaded state
- instance controls
- context length
- runtime settings generated from schema
- historical tok/s and TTFT
- load/unload controls

### Creative
- Stability Matrix installations
- engines
- assets/checkpoints
- workflows/profiles
- generation queue
- batch compare

### Analytics
- restrained, information-dense dashboard
- model speed/TTFT
- context usage
- host pressure
- costs
- error/tool rates
- benchmark results

## Visual system

Direction: dark technical control room, not cyberpunk cliché.

Requirements:
- excellent typography
- strong spacing/grid
- high contrast
- subtle motion
- reduced-motion support
- WCAG AA minimum
- keyboard navigable
- touch targets >= 44px on mobile
- no essential information encoded by color alone

## Speedometer

A compact live throughput component may show:
- tok/s as primary numeric value,
- small arc/gauge only where space allows,
- TTFT secondary,
- no fake precision.

TUI renders numeric equivalent.

## Seeded screenshot mode

`HARNESS_DEMO_MODE=1` loads deterministic fictional data:
- generic hosts
- generic Contacts
- generic models
- generic project
- fake metrics
- fake generated assets

No real credentials/network calls.

Automated Playwright script captures:
- desktop chat/graph
- desktop compute
- desktop creative
- desktop analytics
- iPhone landscape chat/graph
- iPhone portrait chat
- TUI screenshot/recording-friendly fixture
