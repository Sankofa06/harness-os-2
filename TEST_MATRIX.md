# TEST_MATRIX.md — Definition of Done → validation mapping

Every DoD requirement maps to at least one test (or scripted audit). Test IDs are stable
names; file paths may evolve. Status: PLANNED / IMPLEMENTED / PASSING.

## API
| DoD requirement | Test | Status |
|---|---|---|
| Server starts from clean install with one command | `tests/integration/test_serve_smoke.py::test_clean_boot` | PLANNED |
| /health, OpenAPI, REST, WS work | `tests/api/test_system.py`, `tests/api/test_events_ws.py` | PLANNED |
| API versioned under /api/v1 | `tests/api/test_system.py::test_versioned_prefix` | PLANNED |
| Bind localhost or chosen interface/port | `tests/unit/test_config.py::test_bind_config` | PLANNED |
| Auth protects remote access | `tests/api/test_auth.py` (REST + WS, loopback vs remote) | PLANNED |
| API contract tests pass | `tests/api/` suite + OpenAPI schema snapshot | PLANNED |

## Context
| Bootstrap ≤ 4K tokens | `tests/context/test_budget_regression.py::test_bootstrap_budget` | PLANNED |
| Coding-session overhead ≤ 8K | `tests/context/test_budget_regression.py::test_session_overhead` | PLANNED |
| Full expansion ≤ 16K | `tests/context/test_budget_regression.py::test_expanded_budget` | PLANNED |
| Tool/MCP/skill bodies lazy | `tests/context/test_lazy_loading.py` | PLANNED |
| Budget report works | `tests/context/test_compiler.py::test_budget_report_shape` | PLANNED |
| Regression on eager injection | `test_budget_regression.py` fails on eager schema injection | PLANNED |

## Providers
| Generic OpenAI-compatible works | `tests/providers/test_openai_compat.py` vs fake server | PLANNED |
| LM Studio native discovery/lifecycle/settings | `tests/providers/test_lmstudio.py` vs fixture | PLANNED |
| Ollama adapter | `tests/providers/test_ollama.py` vs fixture | PLANNED |
| OpenRouter + OpenAI/Anthropic/Gemini w/ secret refs | `tests/providers/test_cloud_adapters.py` | PLANNED |
| Settings schemas render in UI | `web` Playwright `models-settings.spec.ts` | PLANNED |
| Unknown provider fails gracefully | `tests/providers/test_registry.py::test_unknown_provider` | PLANNED |
| Adapter contract (all) | `tests/providers/conformance/` shared suite | PLANNED |

## Hosts / workspaces
| Add host / test / browse / mkdir / workspace / rw files / shell stream / git / cancel | `tests/hosts/test_ssh_agentless.py` vs local sshd fixture | PLANNED |
| Works without Node on remote | same suite runs with no node component | PLANNED |
| Path traversal rejected | `tests/security/test_path_safety.py` | PLANNED |

## Node
| Registers + authenticates (pairing) | `tests/node/test_pairing.py` | PLANNED |
| CPU/RAM/disk telemetry | `tests/node/test_telemetry.py` | PLANNED |
| GPU telemetry where supported / sensor degradation | `tests/node/test_telemetry.py::test_missing_sensor_ok` | PLANNED |

## Agents
| Create Role/Persona/Contact/Team | `tests/api/test_agents_crud.py` | PLANNED |
| Mention one/many/team | `tests/unit/test_mentions.py`, `tests/api/test_run_loop.py` | PLANNED |
| Rebind global/session/turn + snapshots | `tests/unit/test_binding_precedence.py`, `tests/api/test_binding_overrides.py` | PLANNED |
| Parallel plan→review→implement | `tests/integration/test_orchestration.py` | PLANNED |
| Stop/cancel | `tests/api/test_stop.py` | PLANNED |

## MCP / skills / tools
| Add MCP server; compact index; lazy schema | `tests/mcp/test_lazy_index.py` | PLANNED |
| Skill metadata w/o body load | `tests/skills/test_lazy_skills.py` | PLANNED |
| Superpower toggles | `tests/skills/test_superpowers.py` | PLANNED |
| Permission ask/allow/deny | `tests/unit/test_permissions.py`, `tests/api/test_approvals.py` | PLANNED |

## Creative
| SM installation discovery (Data layout) | `tests/creative/test_discovery.py` vs fixture tree | PLANNED |
| Package catalog w/ type/platform | `tests/creative/test_catalog.py` | PLANNED |
| ComfyUI submit + capture | `tests/creative/test_comfyui.py` vs fake server | PLANNED |
| A1111-style capability negotiation | `tests/creative/test_a1111.py` | PLANNED |
| Honest capability levels for other families | `tests/creative/test_capability_levels.py` | PLANNED |
| Asset dedupe | `tests/creative/test_assets.py` | PLANNED |
| Creative Profile works | `tests/creative/test_profiles.py` | PLANNED |
| Batch comparison deterministic | `tests/creative/test_batch.py` | PLANNED |
| Artifact provenance | `tests/creative/test_provenance.py` | PLANNED |

## Analytics
| Run persists tokens/duration/model/contact/binding | `tests/analytics/test_run_metrics.py` | PLANNED |
| tok/s + TTFT stored | same | PLANNED |
| Tool metrics stored | `tests/analytics/test_tool_metrics.py` | PLANNED |
| Host telemetry visualized | Playwright `compute.spec.ts` | PLANNED |
| Creative metrics stored | `tests/analytics/test_creative_metrics.py` | PLANNED |
| Benchmark compares contacts/models/profiles | `tests/analytics/test_benchmarks.py` | PLANNED |
| No telemetry leaves machine | `tests/security/test_no_egress.py` (socket audit in demo mode) | PLANNED |

## WebUI
| Three-panel desktop | Playwright `layout.spec.ts` | PLANNED |
| iPhone landscape / portrait useful | Playwright viewport specs | PLANNED |
| Streaming, graph, files, models, compute, creative, assets, analytics, approvals | one Playwright spec per view | PLANNED |
| Accessibility target | axe audit spec | PLANNED |

## TUI
| Uses API only | code audit + `tests/tui/` pilot tests (no DB import in tui package) | PLANNED |
| Chat/mentions/graph/contacts/hosts/files/settings/approvals | Textual pilot tests | PLANNED |
| Concurrent with WebUI | `tests/integration/test_concurrent_clients.py` | PLANNED |

## Phone workflow
| 10-step phone flow | Playwright mobile e2e `phone-workflow.spec.ts` vs SSH fixture | PLANNED |

## Demo / marketing
| Deterministic seeded demo mode | `tests/integration/test_demo_mode.py` | PLANNED |
| Screenshot script + required screenshots | `scripts/screenshots` run check in CI | PLANNED |

## Repository
| README/CONTRIBUTING/LICENSE decision | REL-001 review checklist | PLANNED |
| tests/lint/typecheck/CI | GitHub Actions workflow | PLANNED |
| Pages workflow | `.github/workflows/pages.yml` presence + build | PLANNED |
| No-placeholder audit | `scripts/audit_placeholders.py` (grep TODO/FIXME/placeholder/keys) | PLANNED |

## Security (TESTING/TEST_STRATEGY.md)
| Traversal / unauthorized API / secret redaction / malicious markdown / command injection / WS auth | `tests/security/` suite | PLANNED |
