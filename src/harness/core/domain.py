"""Pure domain models shared across subsystems (SPEC/PRODUCT.md core entities)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SecretRef(BaseModel):
    """Metadata only — never carries the secret value (SPEC/SECURITY_PRIVACY.md)."""

    id: str
    name: str
    kind: Literal["keyring", "file", "env"]
    target: str


class Role(BaseModel):
    id: str
    name: str
    description: str = ""
    system_prompt: str = ""
    builtin: bool = False


class Persona(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt: str = ""
    # Lower precedence wins conflicts when personas stack (SPEC/CONTEXT_COMPILER.md).
    precedence: int = 100
    builtin: bool = False


class Binding(BaseModel):
    """Partial binding; unset fields fall through to the next precedence level."""

    provider: str | None = None
    model: str | None = None
    inference_host: str | None = None
    execution_host: str | None = None
    personas: list[str] | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ResolvedBinding(BaseModel):
    """Fully resolved binding snapshot persisted with every run (ADR 0005)."""

    provider: str
    model: str
    inference_host: str = "local"
    execution_host: str = "local"
    personas: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    # Which precedence level supplied each field, e.g. {"model": "turn"}.
    sources: dict[str, str] = Field(default_factory=dict)


class Contact(BaseModel):
    id: str
    handle: str
    display_name: str
    role_id: str | None = None
    persona_ids: list[str] = Field(default_factory=list)
    binding: Binding = Field(default_factory=Binding)


class Team(BaseModel):
    id: str
    handle: str
    display_name: str
    member_ids: list[str] = Field(default_factory=list)


class Session(BaseModel):
    id: str
    title: str = ""
    state: str = "active"
    workspace_id: str | None = None
    contact_ids: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


MessageRole = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    contact_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


RunStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]


class Run(BaseModel):
    id: str
    session_id: str
    contact_id: str
    message_id: str | None = None
    status: RunStatus = "queued"
    binding_snapshot_id: str | None = None
    correlation_id: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class RunMetrics(BaseModel):
    run_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    context_tokens: int | None = None
    ttft_ms: float | None = None
    tokens_per_second: float | None = None
    duration_ms: float | None = None
    finish_reason: str | None = None
    retries: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    cost_estimate: float | None = None
    outcome: str | None = None
    budget: dict[str, Any] | None = None
