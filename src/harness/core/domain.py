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


class ProviderConfig(BaseModel):
    """A configured language-provider instance (endpoint + secret reference).

    Distinct from the in-memory adapter registry: this is the persisted
    configuration an adapter is constructed from (SPEC/PROVIDER_MATRIX.md).
    """

    id: str
    type: str
    display_name: str
    base_url: str | None = None
    secret_ref_id: str | None = None
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


HostKind = Literal["ssh", "node", "local"]


class Host(BaseModel):
    id: str
    display_name: str
    kind: HostKind
    hostname: str | None = None
    port: int | None = None
    username: str | None = None
    secret_ref_id: str | None = None
    workspace_roots: list[str] = Field(default_factory=list)
    known_host_fingerprint: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class Workspace(BaseModel):
    """A folder on a Host that filesystem/shell operations are scoped to
    (SPEC/WORKSPACES_ARTIFACTS.md). ``root_path`` must fall within its Host's
    ``workspace_roots`` (checked at creation time and re-checked on every
    path-taking operation via HOST-002's containment layer).
    """

    id: str
    host_id: str
    root_path: str
    display_name: str
    created_at: str = ""


LoadPolicy = Literal["manual", "always_loaded", "on_demand"]
PlacementPolicy = Literal[
    "manual",
    "auto",
    "prefer-loaded",
    "prefer-local",
    "prefer-fastest",
    "prefer-lowest-pressure",
    "prefer-lowest-cost",
]
ToolCapabilityPolicy = Literal["inherit", "disabled", "required"]


InstanceStatus = Literal["loading", "loaded", "unloading", "unloaded", "failed"]


class ModelInstanceRecord(BaseModel):
    """Persisted lifecycle record for a loaded model (LP-009).

    Distinct from ``providers.language.base.ModelInstance``, which is an adapter's
    raw load-call return value; this is Harness's durable view of it.
    """

    id: str
    provider_config_id: str
    model_id: str
    native_instance_id: str | None = None
    status: InstanceStatus = "loading"
    settings: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ModelProfile(BaseModel):
    """A reusable provider+model+settings+policy bundle (SPEC/PROVIDER_MATRIX.md)."""

    id: str
    name: str
    provider_config_id: str
    model_id: str
    settings: dict[str, Any] = Field(default_factory=dict)
    load_policy: LoadPolicy = "on_demand"
    placement_policy: PlacementPolicy = "manual"
    tool_capability_policy: ToolCapabilityPolicy = "inherit"


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


PermissionClass = Literal[
    "read",
    "write",
    "execute",
    "network",
    "git",
    "process",
    "model_lifecycle",
    "creative_generation",
    "training",
    "destructive",
]

ToolRunStatus = Literal["pending", "running", "succeeded", "failed", "denied", "pending_approval"]


class ToolRun(BaseModel):
    """Persisted record of one tool invocation (TOOL-001, SPEC/MCP_SKILLS_TOOLS.md
    lifecycle). Distinct from a `Job`: a tool run is always driven by the lifecycle
    in `harness.tools.lifecycle`, and its ``permission_class``/``status`` vocabulary
    is PERM-001's, not the generic Job state machine.
    """

    id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    permission_class: PermissionClass
    status: ToolRunStatus = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None
    workspace_id: str | None = None
    session_id: str | None = None
    created_at: str = ""
    finished_at: str | None = None


PermissionPolicy = Literal["allow", "ask", "deny"]
PermissionOutcome = Literal["allow", "deny"]


class PermissionPolicyRecord(BaseModel):
    """The effective policy for one permission class (PERM-001,
    SPEC/SECURITY_PRIVACY.md). Always present for all ten classes — an
    unconfigured class falls back to its default rather than being absent.
    """

    permission_class: PermissionClass
    policy: PermissionPolicy


class PermissionDecisionLog(BaseModel):
    """One resolved permission decision (PERM-001): "resolution is explicit and
    logged" (SPEC/SECURITY_PRIVACY.md). Covers both automatic allow/deny (from a
    non-"ask" policy) and the final outcome of an "ask" flow once a human decides.
    """

    id: str
    tool_run_id: str
    permission_class: PermissionClass
    policy: PermissionPolicy
    outcome: PermissionOutcome
    decided_by: str | None = None
    created_at: str = ""


ArtifactType = Literal[
    "code_file",
    "image",
    "video",
    "screenshot",
    "document",
    "diff",
    "patch",
    "log",
    "test_report",
    "plan",
    "benchmark_report",
    "arbitrary_file",
]


class Artifact(BaseModel):
    """Typed first-class content reference (ART-001, SPEC/WORKSPACES_ARTIFACTS.md).

    Agents reference an artifact as ``artifact://<id>``; only this metadata record
    is loaded by default, and full content is fetched separately (`GET /artifacts/
    {id}/content`) so referencing an artifact never implicitly pulls its bytes into
    context. Content itself lives in a content-addressed blob store keyed by
    ``sha256`` (`harness.artifacts.store.ArtifactBlobStore`), so two artifacts with
    identical bytes — e.g. the same screenshot referenced from two runs — share one
    file on disk.
    """

    id: str
    type: ArtifactType
    mime_type: str
    display_name: str
    size: int
    sha256: str
    run_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None
    source_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


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
