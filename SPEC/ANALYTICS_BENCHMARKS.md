# Analytics and Benchmarking

Analytics are local-first core infrastructure.

## Language run metrics

Capture when available:
- provider
- model
- model version/hash
- quantization
- resolved load/runtime settings
- inference host
- execution host
- contact/role/personas
- input/output tokens
- context compiled tokens
- cached tokens where reported
- TTFT
- prompt-processing throughput
- generation tokens/sec
- duration
- tool counts/durations/failures
- finish reason
- retries
- estimated/actual cloud cost when provider supplies pricing/usage
- user rating/tag
- artifact count
- outcome status

## Creative run metrics

Capture:
- engine/package/version
- checkpoint and auxiliary assets
- workflow/profile
- host
- generation settings
- queue time
- execution time
- GPU/VRAM snapshots when available
- output count
- failure/retry
- artifacts

## Host metrics

Time-series retention should be bounded/configurable:
- CPU
- RAM
- GPU
- VRAM
- disk
- process count
- jobs
- runtime state

## Dashboard

Required:
- active runs
- tokens/sec gauge
- TTFT
- context budget
- model usage
- provider cost
- host pressure
- failure rates
- tool latency
- creative generation performance

Avoid decorative gauges when a number/bar is clearer.

## Benchmarking

Benchmark suites are reusable definitions:
- prompts/tasks,
- contacts/models/profiles,
- scoring strategy,
- environment controls,
- repetition count,
- concurrency,
- seed policy.

Results capture complete binding/settings snapshots so they are reproducible.

Support "compare all selected models" and "compare all selected checkpoints" workflows.
