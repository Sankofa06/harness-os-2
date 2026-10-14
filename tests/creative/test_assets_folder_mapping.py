"""Pure unit tests for `FOLDER_TO_ASSET_KIND`'s folder-name -> canonical
asset kind mapping (CRE-006), verified against Stability Matrix's actual
`SharedFolderType` enum (LykosAI/StabilityMatrix source) rather than
guessed names.
"""

from __future__ import annotations

from harness.providers.creative.assets import ASSET_EXTENSIONS, FOLDER_TO_ASSET_KIND

_SPEC_ASSET_KINDS_WITH_A_MODELS_FOLDER = {
    "checkpoint",
    "diffusion_model",
    "lora",
    "vae",
    "embedding",
    "controlnet",
    "upscaler",
    "text_encoder",
    "clip",
}


def test_every_mapped_kind_is_a_spec_canonical_kind() -> None:
    assert set(FOLDER_TO_ASSET_KIND.values()) == _SPEC_ASSET_KINDS_WITH_A_MODELS_FOLDER


def test_known_stability_matrix_folder_names_map_correctly() -> None:
    assert FOLDER_TO_ASSET_KIND["StableDiffusion"] == "checkpoint"
    assert FOLDER_TO_ASSET_KIND["Lora"] == "lora"
    assert FOLDER_TO_ASSET_KIND["LyCORIS"] == "lora"
    assert FOLDER_TO_ASSET_KIND["VAE"] == "vae"
    assert FOLDER_TO_ASSET_KIND["Embeddings"] == "embedding"
    assert FOLDER_TO_ASSET_KIND["ControlNet"] == "controlnet"
    assert FOLDER_TO_ASSET_KIND["ESRGAN"] == "upscaler"
    assert FOLDER_TO_ASSET_KIND["RealESRGAN"] == "upscaler"
    assert FOLDER_TO_ASSET_KIND["TextEncoders"] == "text_encoder"
    assert FOLDER_TO_ASSET_KIND["ClipVision"] == "clip"
    assert FOLDER_TO_ASSET_KIND["DiffusionModels"] == "diffusion_model"


def test_legacy_renamed_folder_names_are_not_used() -> None:
    """Stability Matrix renamed these folders (`SharedFolders.cs`'s
    `LegacySharedFolderMapping`); the current canonical names above must
    be what Harness scans, not the old ones.
    """
    assert "CLIP" not in FOLDER_TO_ASSET_KIND
    assert "Unet" not in FOLDER_TO_ASSET_KIND
    assert "TextualInversion" not in FOLDER_TO_ASSET_KIND


def test_asset_extensions_match_stability_matrix_supported_checkpoint_extensions() -> None:
    assert {".safetensors", ".pt", ".ckpt", ".pth", ".bin", ".sft", ".gguf"} == ASSET_EXTENSIONS
