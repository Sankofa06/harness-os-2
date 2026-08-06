# ADR 0001 — API-first, event-driven

Status: Accepted

All clients use a versioned API. Runtime state transitions publish events. This prevents TUI/Web coupling and supports future native/mobile clients.
