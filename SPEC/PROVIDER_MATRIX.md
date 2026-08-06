# Language Provider / Runtime Matrix

Harness OS must be provider-open. Adapters normalize common behavior while preserving provider-specific settings via schemas.

## Adapter levels

- **L0 Chat**: basic streaming text.
- **L1 Tools**: tool/function calls and structured output.
- **L2 Runtime**: model discovery and runtime settings.
- **L3 Lifecycle**: download/load/unload/keep-alive.
- **L4 Telemetry**: TTFT/tok-s/load status/usage.
- **L5 Native extras**: provider-specific capabilities exposed through typed extensions.

## Required v1 adapters

| Provider/runtime | Required level | Notes |
|---|---:|---|
| OpenAI-compatible generic | L1 | base URL + API key + model list when available |
| Anthropic-compatible generic | L1 | native message/tool semantics |
| LM Studio native v1 | L5 | preferred for lifecycle/settings; OpenAI-compatible fallback |
| Ollama | L4/L5 where exposed | list/pull/show/generate/chat/keep_alive/options |
| OpenRouter | L1/L4 | cloud model catalog, pricing/usage/routing metadata when available |
| OpenAI | L1/L4 | native provider adapter |
| Anthropic | L1/L4 | native provider adapter |
| Google Gemini | L1/L4 | native provider adapter |
| local custom endpoint | L0-L2 | user supplies schema/capabilities if autodetection fails |

Adapters for additional systems (including Bionic or future runtimes) MUST plug into the same contract without core changes.

## LM Studio settings

Expose actual supported settings from runtime schema, including where available:
- context length,
- model instance selection,
- load/unload/download,
- eval batch size,
- Flash Attention,
- KV cache/offload settings,
- MoE expert settings,
- TTL/auto-evict/JIT loading,
- authentication,
- loaded instance state,
- quantization,
- max context,
- tool/reasoning/model capabilities,
- TTFT and token throughput when exposed.

Do not hard-code settings that the installed LM Studio version does not advertise.

## Ollama

Use its native API where advantageous and retain OpenAI-compatible interoperability where appropriate. Support:
- model inventory,
- show metadata,
- pull progress,
- chat/generate,
- runtime options,
- context configuration where supported,
- keep-alive/unload semantics,
- embedding/capability metadata when available.

## Cloud-provider schema rule

Provider-specific fields live under namespaced settings:

```json
{
  "common": {
    "temperature": 0.2,
    "max_output_tokens": 4096
  },
  "provider": {
    "openrouter": {
      "routing": {}
    }
  }
}
```

Unknown settings are rejected unless the adapter explicitly supports passthrough.

## Model profile

A reusable Model Profile contains:
- provider/runtime,
- model ID,
- default inference settings,
- load policy,
- placement policy,
- tool/capability policy.

## Placement policy

At minimum:
- manual host,
- auto,
- prefer-loaded,
- prefer-local,
- prefer-fastest,
- prefer-lowest-pressure,
- prefer-lowest-cost.

Auto routing must remain opt-in in v1.
