"""Applies a Checkpoint Profile bundle (checkpoint/VAE/sampler/scheduler/
LoRAs) as real AUTOMATIC1111 txt2img/img2img request fields (CRE-007,
shared by `POST /creative/jobs`'s single-generation path and CRE-008's
batch comparison), verified directly from AUTOMATIC1111/stable-diffusion-
webui source (`modules/processing.py`/`extensions-builtin/Lora/
extra_networks_lora.py`), not guessed: checkpoint/VAE go in
`override_settings` (A1111 itself restores the prior values after the
request), sampler/scheduler are top-level fields, and LoRAs have no
structured field at all in this API -- they are applied by appending
`<lora:name:1.0>` tokens to the prompt string, the built-in Lora
extension's only mechanism.
"""

from __future__ import annotations

from typing import Any


def merge_profile_params(
    params: dict[str, Any],
    *,
    checkpoint: str | None = None,
    vae: str | None = None,
    sampler: str | None = None,
    scheduler: str | None = None,
    loras: list[str] | None = None,
) -> dict[str, Any]:
    """Explicit ``params`` always win over the profile fields' defaults;
    ``override_settings`` merges at the inner-dict level so a request can
    override just one piece of the bundle (e.g. the checkpoint) without
    having to restate the rest (e.g. the VAE).
    """
    override_settings: dict[str, Any] = {}
    if checkpoint is not None:
        override_settings["sd_model_checkpoint"] = checkpoint
    if vae is not None:
        override_settings["sd_vae"] = vae

    merged: dict[str, Any] = {}
    if override_settings:
        merged["override_settings"] = override_settings
    if sampler is not None:
        merged["sampler_name"] = sampler
    if scheduler is not None:
        merged["scheduler"] = scheduler

    for key, value in params.items():
        if key == "override_settings" and isinstance(value, dict) and merged.get(key):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    if loras:
        lora_tags = "".join(f"<lora:{name}:1.0>" for name in loras)
        merged["prompt"] = merged.get("prompt", "") + lora_tags

    return merged
