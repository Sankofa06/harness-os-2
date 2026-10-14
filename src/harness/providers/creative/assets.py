"""Creative asset discovery under Stability Matrix's shared Models directory
(CRE-006, SPEC/CREATIVE_COMPUTE.md "Creative assets").

Stability Matrix keeps one shared ``<DataDir>/Models/<SharedFolderType>``
tree that every installed package's own ``models/...`` folder links/
junctions into, so cataloging *that* tree (rather than each package's own
per-install copy) is what actually lets a checkpoint shared across multiple
engines be recognized as one asset rather than N unrelated files. The
folder-name -> canonical-category mapping and the root ``Models`` directory
name are both verified directly from LykosAI/StabilityMatrix source, not
guessed:

- ``StabilityMatrix.Core/Models/SharedFolderType.cs`` (the enum): each
  member's on-disk folder name is exactly its C# member name -- this enum
  has no ``[StringValue]`` override, confirmed via
  ``StabilityMatrix.Core/Extensions/EnumAttributes.cs``'s
  ``GetStringValue()`` falling back to ``Enum.GetName`` when none is
  present.
- ``StabilityMatrix.Core/Services/SettingsManager.cs``'s ``ModelsDirectory``:
  ``Settings.ModelDirectoryOverride ?? Path.Combine(LibraryDir, "Models")``.
  Harness does not read Stability Matrix's own settings for a configured
  override, so callers supply ``models_root`` explicitly rather than Harness
  silently assuming the un-overridden default is correct for every host
  (AGENTS.md: declare the limitation, don't guess past it).
- ``StabilityMatrix.Core/Models/Database/LocalModelFile.cs``'s
  ``SupportedCheckpointExtensions``.

Only the nine canonical asset kinds (SPEC) that actually correspond to a
shared Models subfolder are produced here: checkpoint, diffusion_model,
lora, vae, embedding, controlnet, upscaler, text_encoder, clip. The other
four canonical kinds (workflow, training_output, image, video) are already
represented elsewhere as Artifacts -- CRE-002's workflow storage and the
generation-output capture CRE-003/CRE-004 already do that -- and have no
corresponding Models-folder source to scan here.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.core.errors import ProviderError
from harness.hosts.ssh import SSHHost

ASSET_EXTENSIONS = frozenset({".safetensors", ".pt", ".ckpt", ".pth", ".bin", ".sft", ".gguf"})

# SharedFolderType enum member name (= on-disk folder name) -> SPEC canonical
# asset kind. `LyCORIS`/`ApproxVAE` fold into `lora`/`vae` (recognized
# variants of the same canonical category, not separate SPEC kinds); the six
# upscaler-architecture folders all fold into `upscaler`.
FOLDER_TO_ASSET_KIND: dict[str, str] = {
    "StableDiffusion": "checkpoint",
    "Diffusers": "checkpoint",
    "Lora": "lora",
    "LyCORIS": "lora",
    "VAE": "vae",
    "ApproxVAE": "vae",
    "Embeddings": "embedding",
    "ControlNet": "controlnet",
    "ESRGAN": "upscaler",
    "RealESRGAN": "upscaler",
    "SwinIR": "upscaler",
    "ScuNET": "upscaler",
    "LDSR": "upscaler",
    "BSRGAN": "upscaler",
    "TextEncoders": "text_encoder",
    "ClipVision": "clip",
    "DiffusionModels": "diffusion_model",
}


@dataclass(frozen=True)
class ScannedAssetFile:
    path: str
    asset_kind: str
    filename: str
    size_bytes: int
    content_hash: str


async def scan_models_directory(ssh_host: SSHHost, models_root: str) -> list[ScannedAssetFile]:
    """Recursively scan every known shared-folder subtree under
    ``models_root``, hashing each recognized model file remotely
    (`SSHHost.sha256_file` -- a ``sha256sum`` run over SSH, never
    transferring multi-gigabyte checkpoint bytes to this process) so
    identical content at different paths/hosts can later be recognized as
    the same asset (`CreativeAssetRepo.record_scan`). A folder that doesn't
    exist on this host is skipped, not an error -- not every install has
    every shared-folder type populated.
    """
    found: list[ScannedAssetFile] = []
    for folder_name, asset_kind in FOLDER_TO_ASSET_KIND.items():
        root = f"{models_root.rstrip('/')}/{folder_name}"
        found.extend(await _walk(ssh_host, root, asset_kind))
    return found


async def _walk(ssh_host: SSHHost, directory: str, asset_kind: str) -> list[ScannedAssetFile]:
    try:
        entries = await ssh_host.list_dir(directory)
    except ProviderError:
        return []  # this shared-folder type isn't populated on this host
    found: list[ScannedAssetFile] = []
    for entry in entries:
        entry_path = f"{directory}/{entry.name}"
        if entry.is_dir:
            found.extend(await _walk(ssh_host, entry_path, asset_kind))
            continue
        if not any(entry.name.lower().endswith(ext) for ext in ASSET_EXTENSIONS):
            continue
        content_hash = await ssh_host.sha256_file(entry_path)
        found.append(
            ScannedAssetFile(
                path=entry_path,
                asset_kind=asset_kind,
                filename=entry.name,
                size_bytes=entry.size,
                content_hash=content_hash,
            )
        )
    return found
