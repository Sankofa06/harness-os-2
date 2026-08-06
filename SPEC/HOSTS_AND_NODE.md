# Hosts, SSH, and Optional Harness Node

## Host capability model

A Host can expose any subset:

- ssh_execution
- filesystem
- git
- process_control
- language_runtime
- creative_runtime
- basic_telemetry
- full_telemetry
- gpu_telemetry
- workspace_watch
- artifact_transfer

## Agentless SSH mode

Required operations:
- test connection,
- enumerate allowed roots,
- create workspace directory,
- list/read/write/move/delete files subject to permissions,
- execute commands,
- stream stdout/stderr,
- cancel process,
- git operations,
- upload/download artifacts.

Security:
- key/password via secret store,
- known-host verification,
- configurable workspace roots,
- path canonicalization,
- command permission policy,
- no implicit sudo.

## Optional Node mode

Node is a minimal separately runnable component, not the full application.

Advertise:
- host identity,
- OS/arch,
- CPU/RAM/disk pressure,
- GPU inventory,
- GPU utilization,
- VRAM used/total/pressure,
- temperatures when safely supported,
- running configured engines,
- LM runtime health and loaded model state,
- creative runtime health,
- optional process lifecycle,
- heartbeat.

Suggested platform probes:
- generic: psutil
- NVIDIA: NVML/nvidia-smi adapter
- Apple: supported OS APIs / best-effort pressure metrics
- AMD: adapter when stable platform APIs are available

Node must degrade gracefully when a sensor is unavailable.

## Registration/auth

Node registration uses a generated one-time pairing token and persistent per-node credential. Do not trust network location alone.

## Scheduling

Host capacity score considers:
- online/degraded,
- model already loaded,
- available RAM/VRAM,
- historical throughput,
- active jobs,
- user placement policy.

Automatic model unloading requires an explicit global/session policy.
