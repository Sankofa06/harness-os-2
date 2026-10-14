"""Per-generation provenance (CRE-009, SPEC/CREATIVE_COMPUTE.md
"Provenance"), attached to every creative output Artifact's metadata.

Full parameter-level provenance (checkpoint+hash/LoRAs/prompt/seed/
sampler/dimensions/steps/CFG) is captured for the AUTOMATIC1111-compatible
family, whose request/response fields are flat and source-verified
(CRE-004/CRE-007/CRE-008) -- the same scope boundary CRE-008's batch
comparison already drew. ComfyUI's workflow graph is opaque to Harness by
design (an arbitrary graph of nodes with no assumed schema), so its
provenance records what Harness genuinely knows (engine/host/workflow
reference/duration/timestamp), not generation parameters guessed from
node inputs whose meaning varies per workflow.

`resource_metrics` and an engine version are both omitted rather than
faked: no GPU/VRAM telemetry exists yet for an arbitrary engine instance
(ANA-002/NODE-001's job), and neither engine exposes a verified version
endpoint this adapter calls.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.core.app import Application

_LORA_TAG = re.compile(r"<lora:([^:>]+):[^>]+>")


def extract_loras_from_prompt(prompt: str) -> list[str]:
    """Reverses `a1111.profiles.merge_profile_params`'s own
    ``<lora:name:weight>`` tag format -- Harness's own representation of
    a profile's LoRA bundle, not a guess about an external format.
    """
    return _LORA_TAG.findall(prompt)


def strip_lora_tags(prompt: str) -> str:
    return _LORA_TAG.sub("", prompt).strip()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def resolve_checkpoint_hash(app: Application, checkpoint: str | None) -> str | None:
    """Looks up ``checkpoint``'s content hash in the CRE-006 asset catalog
    by filename. Returns ``None`` -- not a guess -- whenever that's
    ambiguous: no cataloged file has this name, or (a real possibility)
    more than one *different* file does.
    """
    if checkpoint is None:
        return None
    candidates = await app.creative_assets.find_by_filename(checkpoint)
    distinct_hashes = {c.content_hash for c in candidates}
    return next(iter(distinct_hashes)) if len(distinct_hashes) == 1 else None


@dataclass(frozen=True)
class GenerationProvenance:
    engine_id: str
    host: str
    timestamp: str
    duration_ms: float | None = None
    profile_id: str | None = None
    workflow_artifact_id: str | None = None
    checkpoint: str | None = None
    checkpoint_hash: str | None = None
    vae: str | None = None
    loras: list[str] = field(default_factory=list)
    prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    sampler: str | None = None
    scheduler: str | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    cfg_scale: float | None = None
    resource_metrics: dict[str, Any] | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Drops empty/unset fields rather than cluttering every artifact's
        metadata with a wall of nulls for whatever this generation didn't
        use (e.g. ``vae``/``loras`` when the profile had none).
        """
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}
