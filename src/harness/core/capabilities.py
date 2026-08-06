"""Shared capability vocabulary for the control plane."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class AdapterLevel(IntEnum):
    """Language-provider capability levels per SPEC/PROVIDER_MATRIX.md."""

    L0_CHAT = 0
    L1_TOOLS = 1
    L2_RUNTIME = 2
    L3_LIFECYCLE = 3
    L4_TELEMETRY = 4
    L5_NATIVE_EXTRAS = 5


class HostCapability(StrEnum):
    """What a Host can expose, per SPEC/HOSTS_AND_NODE.md."""

    SSH_EXECUTION = "ssh_execution"
    FILESYSTEM = "filesystem"
    GIT = "git"
    PROCESS_CONTROL = "process_control"
    LANGUAGE_RUNTIME = "language_runtime"
    CREATIVE_RUNTIME = "creative_runtime"
    BASIC_TELEMETRY = "basic_telemetry"
    FULL_TELEMETRY = "full_telemetry"
    GPU_TELEMETRY = "gpu_telemetry"
    WORKSPACE_WATCH = "workspace_watch"
    ARTIFACT_TRANSFER = "artifact_transfer"


class PermissionClass(StrEnum):
    """Permissioned operation classes per SPEC/SECURITY_PRIVACY.md."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    GIT = "git"
    PROCESS = "process"
    MODEL_LIFECYCLE = "model_lifecycle"
    CREATIVE_GENERATION = "creative_generation"
    TRAINING = "training"
    DESTRUCTIVE = "destructive"


class PermissionPolicy(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"
