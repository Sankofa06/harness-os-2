# TEST_MATRIX.md — Definition of Done → validation mapping

Every DoD requirement maps to at least one test (or scripted audit). Test IDs are stable
names; file paths may evolve. Status: PLANNED / IMPLEMENTED / PASSING.

## API
| DoD requirement | Test | Status |
|---|---|---|
| Server starts from clean install with one command | `tests/integration/test_serve_smoke.py::test_clean_boot` | PASSING |
| /health, OpenAPI, REST, WS work | `tests/api/test_system.py`, `tests/api/test_events_ws.py` | PASSING |
| API versioned under /api/v1 | `tests/api/test_system.py::test_versioned_prefix` | PASSING |
| Bind localhost or chosen interface/port | `tests/unit/test_config.py`, `test_serve_smoke.py` (custom port) | PASSING |
| Auth protects remote access | `tests/api/test_auth.py` (REST), `tests/api/test_events_ws.py` (WS) — both loopback vs remote+token | PASSING |
| API contract tests pass | `tests/api/` suite + OpenAPI schema snapshot | IMPLEMENTED (no frozen snapshot yet) |
| Long actions create cancelable Jobs with a persisted state machine and event trail | `tests/unit/test_jobs.py`, `tests/api/test_jobs.py` | PASSING |
| Concurrent DB access (background Job racing live HTTP polling) doesn't hang or corrupt state (D-030) | `tests/persistence/test_db_concurrency.py`, `tests/api/test_permissions.py` ask/deny flows | PASSING |

## Context
| Bootstrap ≤ 4K tokens | `tests/context/test_compiler.py::test_bootstrap_budget_under_4k` | PASSING |
| Coding-session overhead ≤ 8K | `tests/context/test_compiler.py::test_history_is_trimmed_to_budget` | PASSING |
| Full expansion ≤ 16K | `tests/context/test_compiler.py::test_full_expansion_soft_limit` | PASSING |
| Tool/MCP/skill bodies lazy | `tests/context/test_compiler.py::test_activated_skill_adds_cost_only_when_activated` | PASSING |
| Budget report works | `tests/context/test_compiler.py` (`BudgetReport` shape) | PASSING |
| Regression on eager injection | `tests/context/test_compiler.py::test_no_tools_or_skills_means_zero_cost_sections` | PASSING |
| Long-session compile keeps protected facts (unresolved reqs/plan/changed files/failing tests/permission decisions) even when history is fully squeezed out | `tests/context/test_transcript_state.py::test_protected_facts_survive_a_budget_too_small_for_any_history` | PASSING |
| Structured session state + rolling summary persisted per session; run loop compiles it in | `tests/api/test_transcript_state.py` | PASSING |
| Representative sessions at real production budgets (4K bootstrap/8K normal/16K expanded), run in CI | `tests/context/test_regression_budgets.py` | PASSING |
| Real ToolRegistry (production tool catalog) contributes zero cost unless explicitly activated | `tests/context/test_regression_budgets.py::test_real_tool_registry_is_not_eagerly_injected` | PASSING |

## Providers
| Generic OpenAI-compatible works | `tests/providers/test_openai_compat.py` vs fake server | PASSING |
| LM Studio native discovery/lifecycle/settings | `tests/providers/test_lmstudio.py` vs fixture | PASSING |
| Ollama adapter | `tests/providers/test_ollama.py` vs fixture | PASSING |
| OpenRouter adapter (catalog + pricing + authoritative cost) | `tests/providers/test_openrouter.py`, `tests/unit/test_runloop_cost.py` | PASSING |
| OpenAI native adapter | `tests/providers/test_openai_native.py` | PASSING |
| Anthropic native adapter (system field, max_tokens, SSE event stream) | `tests/providers/test_anthropic.py` | PASSING |
| Gemini native adapter (role mapping, usageMetadata) | `tests/providers/test_gemini.py` | PASSING |
| Adapters constructed from persisted ProviderConfig, secrets resolved just-in-time | `tests/unit/test_provider_factory.py` | PASSING |
| /language/models, /language/instances load/unload as Jobs, settings-schema/settings | `tests/api/test_instances.py` | PASSING |
| Model profile resolves to provider+model+settings | `tests/persistence/test_control_plane_repos.py`, `tests/api/test_model_profiles.py` | PASSING |
| Placement policy respects manual/auto/prefer-*/telemetry-required semantics | `tests/unit/test_placement.py` | PASSING |
| Settings-schema validation (namespaced common/provider.*, passthrough opt-in) | `tests/unit/test_settings_schema.py` | PASSING |
| Settings schemas render in UI | `web` Playwright `models-settings.spec.ts` | PLANNED |
| Uniform control-plane descriptor (identity/capabilities/state/settings/health/events) | `tests/unit/test_control_plane.py`, `tests/api/test_system.py::test_capabilities_lists_fake_provider` | PASSING |
| Persisted provider config CRUD (secret refs, not raw values) | `tests/persistence/test_control_plane_repos.py`, `tests/api/test_control_plane.py` | PASSING |
| Host registry CRUD + capability model | `tests/persistence/test_control_plane_repos.py`, `tests/api/test_control_plane.py` | PASSING |
| Unknown provider fails gracefully | `tests/providers/test_registry.py::test_unknown_provider` | PLANNED |
| Adapter contract (all) | `tests/providers/conformance/` shared suite | PLANNED |

## Hosts / workspaces
| Add host / test connection (real fingerprint check) | `tests/api/test_host_ssh.py` vs real local SSH server | PASSING |
| SSH exec streams stdout/stderr, reports exit status, cancelable | `tests/hosts/test_ssh.py` vs real local SSH server | PASSING |
| SFTP read/write/list/move/delete/mkdir | `tests/hosts/test_ssh.py` | PASSING |
| Argv quoted, not shell-concatenated (injection resistance) | `tests/hosts/test_ssh.py::test_exec_stream_quotes_arguments_safely` | PASSING |
| Workspace browse / mkdir / rw files / diff | `tests/api/test_workspaces.py` (WSP-001) | PASSING |
| Workspace-level containment narrower than Host's own workspace_roots | `tests/api/test_workspaces.py::test_workspace_file_path_cannot_escape_workspace_root` | PASSING |
| Git init/status/add/commit/branch/log via structured exec | `tests/api/test_workspaces_git.py` (WSP-002) vs real local SSH server + real git | PASSING |
| Works without Node on remote | HOST-001/WSP-* suites never depend on a node component | PASSING (structural — no Node dependency exists anywhere in the SSH path) |
| Path traversal rejected (lexical `..`, prefix-sibling, relative, no-roots-fail-closed) | `tests/security/test_path_safety.py` | PASSING |
| Symlink inside an allowed root resolving outside it is rejected | `tests/hosts/test_ssh.py::test_read_file_via_symlink_escaping_root_rejected`, `tests/security/test_path_safety.py::test_resolve_and_check_rejects_symlink_resolving_outside_root` | PASSING |

## Artifacts
| Typed catalog; content-addressed blob store; content lazy (metadata vs `/content`) | `tests/unit/test_artifact_store.py`, `tests/api/test_artifacts.py` | PASSING |
| Transfers checksummed (sha256) and evented (`artifact.created`/`artifact.transferred`) | `tests/api/test_artifacts.py::test_pull_artifact_from_workspace_host`, `::test_push_artifact_to_workspace_host` vs real local SSH server | PASSING |
| Push/pull path containment matches Workspace rules | `tests/api/test_artifacts.py::test_pull_artifact_rejects_path_outside_workspace` | PASSING |

## Node
| Registers + authenticates (pairing) | `tests/node/test_pairing.py` | PLANNED |
| CPU/RAM/disk telemetry | `tests/node/test_telemetry.py` | PLANNED |
| GPU telemetry where supported / sensor degradation | `tests/node/test_telemetry.py::test_missing_sensor_ok` | PLANNED |

## Agents
| Create Role/Persona/Contact/Team | `tests/api/test_agents_crud.py` | PASSING |
| Mention one/many/team | `tests/unit/test_mentions.py`, `tests/api/test_run_loop.py` | PASSING |
| Rebind global/session/turn + snapshots | `tests/unit/test_binding.py`, `tests/api/test_run_loop.py::test_session_binding_override_...` | PASSING |
| Parallel plan→review→implement; agents.delegate tool; agent.spawned/completed events; session graph reflects delegation | `tests/api/test_delegation.py` | PASSING |
| Stop/cancel | `tests/api/test_stop.py`, `tests/unit/test_run_registry.py` | PASSING |

## MCP / skills / tools
| Tool lifecycle (validate→permission→execute→capture→events); runs recorded in tool_runs | `tests/unit/test_tool_lifecycle.py`, `tests/api/test_tools.py` | PASSING |
| Add MCP server; compact index; lazy schema; bearer-token auth via secret_ref_id (SEC-001) | `tests/mcp/test_client.py`, `tests/api/test_mcp.py` vs real local fixture server | PASSING |
| capabilities.search across native tools + MCP index; tools.describe activates a schema; budget stays 0 until activation, then carries into the next compile only | `tests/api/test_capabilities.py` vs real local fixture MCP server + real run loop | PASSING |
| Skill metadata w/o body load; activation (REST + skills.activate tool) adds body to next compile only; capabilities.search finds skills | `tests/api/test_skills.py` | PASSING |
| Superpower toggles gate capabilities.search only; GET /tools + execution + permission policy unaffected | `tests/api/test_superpowers.py` | PASSING |
| Permission ask/allow/deny; ask flow blocks until approval; decisions logged | `tests/api/test_permissions.py` | PASSING |
| Workspace-scoped file/shell/git tools (TOOL-002) behind permission classes; injection resistance; traversal rejection | `tests/api/test_workspace_tools.py` vs real local SSH server | PASSING |

## Creative
| SM installation discovery (Data layout: settings.json InstalledPackages); unknown packages → unknown/custom with detected metadata | `tests/creative/test_discovery.py` vs fixture settings.json; `tests/api/test_creative.py` vs real local SSH server | PASSING |
| Installed package catalog shows package type/platform (family_id/family_group/platform_supported per installation) | `tests/creative/test_discovery.py`, `tests/api/test_creative.py` | PASSING |
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
| Secret values never returned by any endpoint or persisted in plaintext | `tests/unit/test_secrets.py`, `tests/api/test_secrets.py` | PASSING |
