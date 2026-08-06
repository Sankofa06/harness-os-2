# Creative Compute and Stability Matrix

Creative compute is a first-class control-plane domain.

## Goals

- discover existing Stability Matrix installations without replacing them,
- normalize packages/engines and assets,
- generate and persist artifacts,
- expose engine-specific controls through capability/settings schemas,
- support local image/video/training workflows where the underlying package supports them,
- preserve provenance.

## Stability Matrix package families

The implementation MUST model at least the package families currently advertised by Stability Matrix:

### Stable Diffusion WebUI family
- Stable Diffusion WebUI reForge
- Stable Diffusion WebUI Forge
- Stable Diffusion WebUI AMDGPU Forge
- AUTOMATIC1111
- AUTOMATIC1111 DirectML
- SD Web UI-UX
- SD.Next

### Fooocus family
- Fooocus
- Fooocus MRE
- Fooocus ControlNet SDXL
- Ruined Fooocus
- Fooocus 1-Up Edition
- SimpleSDXL

### Node/workflow and orchestration
- ComfyUI
- StableSwarmUI / SwarmUI
- SDFX

### Other inference
- VoltaML
- InvokeAI

### Training / fine-tuning
- Kohya GUI
- OneTrainer
- FluxGym

### Video / multimodal
- CogVideo via CogStudio

Stability Matrix evolves. Package discovery MUST be data-driven so newly installed package types can appear as `unknown/custom` with detectable launch/API metadata rather than crashing.

## Platform behavior

Do not assume the same engine/package is available or functional on macOS and Windows.

Represent compatibility as:

```text
engine/package
  supported_platforms[]
  acceleration_backends[]
  api_strategy
  launch_strategy
  asset_types[]
  capability_set[]
```

Examples of acceleration backends:
- Apple Metal/MPS
- NVIDIA CUDA
- AMD ROCm/HIP
- DirectML
- CPU

The app MUST read what is actually installed and report unsupported combinations clearly.

## Integration strategy hierarchy

For each engine:
1. native documented API adapter,
2. stable community/API compatibility layer,
3. engine-specific HTTP/WebSocket adapter,
4. launch/process + filesystem integration,
5. read-only discovery if safe control is unavailable.

Never automate a GUI with brittle screen scraping.

## Required deep integration

### ComfyUI
First-class:
- endpoint health,
- object/node metadata discovery,
- queue,
- prompt/workflow submission,
- progress events,
- interrupt/cancel if supported,
- history/results,
- image upload/input,
- workflow JSON storage by reference,
- output artifact capture,
- model/checkpoint/LoRA/VAE/control-related assets where discoverable.

ComfyUI workflow JSON MUST NOT be injected into LLM context by default.

### A1111/Forge/reForge/SD.Next compatible APIs
Where the active engine exposes the common web API:
- txt2img,
- img2img,
- options,
- samplers/schedulers when exposed,
- models/checkpoints,
- VAEs,
- LoRAs where exposed,
- progress,
- interrupt,
- extras/upscale when exposed.

### InvokeAI
Use its native API if detected. Capabilities are discovered and mapped; do not assume A1111 compatibility.

### Fooocus family / packages without a stable control API
Prefer launch/health/read-only asset integration unless a reliable local API is explicitly detected. UI must show exact level.

### Training engines
Treat training as Jobs with explicit user approval, resource estimates, logs, outputs and stop controls. They are not implicitly available to LLM agents.

## Creative assets

Canonical asset types:
- checkpoint
- diffusion_model
- lora
- vae
- embedding
- controlnet
- upscaler
- text_encoder
- clip
- workflow
- training_output
- image
- video

Deduplicate by content hash/path identity where possible.

## Creative Profile

Equivalent to a reusable preset, not a Persona:

```yaml
name: app-icon
engine_selector: comfyui
workflow_ref: workflow/app-icon-v1
settings:
  width: 1024
  height: 1024
placement:
  prefer_loaded_asset: true
```

A "Checkpoint Profile" MAY bundle checkpoint + VAE + LoRAs + sampler/scheduler defaults. Do not call these Personas in the data model; the UI may present them with friendly names.

## Batch comparison

Support:
- one prompt across N checkpoints/profiles,
- controlled seeds,
- sequential or parallel scheduling,
- capacity-aware host placement,
- grid/result artifact,
- run metrics.

## Provenance

Every generation artifact records:
- engine/package/version,
- host,
- workflow/profile,
- checkpoint + hash,
- LoRAs/VAEs/etc,
- prompt/negative prompt,
- seed,
- sampler/scheduler,
- dimensions,
- steps/CFG as applicable,
- duration,
- resource metrics,
- timestamp.
