# Mobile Compute — Architectural Hook

The v1 WebUI treats phones primarily as clients. The data model MUST nevertheless support a future `mobile` Host/Compute Provider.

## Apple native direction

The native companion specification should support:
- Apple Foundation Models on-device model where available,
- Apple's generic LanguageModel protocol,
- Core AI / CoreAILanguageModel,
- MLXLanguageModel,
- future custom on-device models,
- Vision/OCR tools,
- on-device image/vision generation APIs where available,
- battery/thermal-aware capability advertisement.

A phone-hosted model must participate through the same language-provider contract as any other runtime.

## Model files

Do not make GGUF or Core ML/Core AI format assumptions in the server spec. The native app owns device-compatible model download/import/compilation and advertises the resulting models/capabilities.

## Mobile scheduling policy

Mobile compute is opt-in and defaults to:
- no background heavy generation,
- thermal/battery guardrails,
- only when charging toggle,
- Wi-Fi/secure-network policy,
- user confirmation for large downloads.

## Future mobile node

Native app may register with Harness as:
- UI client,
- language inference provider,
- vision provider,
- creative provider,
- telemetry node.

This hook MUST not complicate v1 server bootstrap or context.
