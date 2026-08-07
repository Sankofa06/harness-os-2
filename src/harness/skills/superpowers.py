"""Superpower bundles (SKL-002, SPEC/MCP_SKILLS_TOOLS.md): "user-facing
toggle that activates a bounded bundle of tools/skills/MCP/provider
permissions." Bundle membership is fixed, declarative data — which real
native-tool names each seed bundle exposes — not a runtime-configurable set,
matching the SPEC's "seed bundles" framing.

"Bundles are convenience UI only; underlying permissions remain explicit"
(SPEC/MCP_SKILLS_TOOLS.md): toggling a bundle changes the model-facing
discovery surface only (`capabilities.search`'s candidates) — it never
touches PERM-001's permission policies, and a gated tool remains directly
callable via `POST /tools/{name}/run`, and fully visible in the admin-facing
`GET /tools` listing, regardless of whether its bundle is enabled.

Several bundles are currently empty — Browser, Creative, Research, and
Benchmarking have no native tools yet (those subsystems are later
milestones) — declared honestly rather than populated with placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.tools.registry import ToolRegistry


@dataclass(frozen=True)
class SuperpowerBundle:
    id: str
    display_name: str
    description: str
    tool_names: tuple[str, ...] = field(default_factory=tuple)
    skill_names: tuple[str, ...] = field(default_factory=tuple)


BUNDLES: tuple[SuperpowerBundle, ...] = (
    SuperpowerBundle(
        id="coding",
        display_name="Coding",
        description="Read/write files and run shell commands in a workspace.",
        tool_names=("fs_read_file", "fs_write_file", "fs_list_dir", "shell_exec"),
    ),
    SuperpowerBundle(
        id="git_github",
        display_name="Git/GitHub",
        description="Inspect and modify a workspace's git repository.",
        tool_names=(
            "git_init",
            "git_status",
            "git_diff",
            "git_add",
            "git_commit",
            "git_branch_list",
            "git_branch_create",
            "git_log",
        ),
    ),
    SuperpowerBundle(
        id="browser",
        display_name="Browser",
        description="Drive a web browser to navigate and inspect pages.",
    ),
    SuperpowerBundle(
        id="creative",
        display_name="Creative",
        description="Generate images/video/audio via a creative-compute engine.",
    ),
    SuperpowerBundle(
        id="research",
        display_name="Research",
        description="Search and fetch web content.",
    ),
    SuperpowerBundle(
        id="remote_host",
        display_name="Remote Host",
        description="Run commands against a remote SSH-connected host.",
        tool_names=("shell_exec",),
    ),
    SuperpowerBundle(
        id="benchmarking",
        display_name="Benchmarking",
        description="Run and record model/engine benchmark suites.",
    ),
)

BUNDLES_BY_ID: dict[str, SuperpowerBundle] = {b.id: b for b in BUNDLES}


def gated_tool_names() -> frozenset[str]:
    """Every tool name that belongs to at least one bundle — the set whose
    exposure depends on a toggle. A tool that isn't in any bundle (echo, the
    capabilities.search/tools.describe/skills.activate/agents.delegate
    meta-tools) is always exposed regardless of toggle state.
    """
    return frozenset(name for bundle in BUNDLES for name in bundle.tool_names)


def exposed_tool_names(tools: ToolRegistry, enabled_bundle_ids: set[str]) -> set[str]:
    gated = gated_tool_names()
    enabled_names: set[str] = set()
    for bundle_id in enabled_bundle_ids:
        bundle = BUNDLES_BY_ID.get(bundle_id)
        if bundle is not None:
            enabled_names.update(bundle.tool_names)
    return {t.name for t in tools.list() if t.name not in gated or t.name in enabled_names}
