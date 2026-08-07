"""Stability Matrix installation discovery (CRE-001, SPEC/CREATIVE_COMPUTE.md).

Stability Matrix persists exactly one metadata file for all installed
packages: ``<DataDir>/settings.json``, whose ``InstalledPackages`` array has
one entry per install (verified via source inspection — see
`harness.providers.creative.families`'s docstring for provenance; there is no
per-package folder metadata file). This module is a pure function over that
JSON text — decoupled from *how* the bytes were fetched (local read, SFTP over
an SSH Host, ...) so it can be exercised directly against fixture text without
any Host/network machinery, matching this codebase's fixture-testing rule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from harness.providers.creative.families import (
    UNKNOWN_FAMILY_DISPLAY_NAME,
    UNKNOWN_FAMILY_GROUP,
    UNKNOWN_FAMILY_ID,
    match_family,
)


@dataclass(frozen=True)
class DiscoveredInstallation:
    package_name: str
    display_name: str
    library_path: str
    launch_command: str | None
    python_version: str | None
    family_id: str
    family_display_name: str
    family_group: str
    supported_platforms: tuple[str, ...]
    platform_supported: bool
    raw: dict[str, Any] = field(default_factory=dict)


def parse_installed_packages(
    settings_json_text: str, platform: str
) -> list[DiscoveredInstallation]:
    """``platform`` is the OS of the host being scanned (``"windows"``,
    ``"macos"``, or ``"linux"``) — Stability Matrix's `settings.json` doesn't
    record it, so the caller (who knows which Host it read this file from)
    supplies it, and each entry's `platform_supported` is computed against
    the matched family's declared `supported_platforms`
    (SPEC: "The app MUST read what is actually installed and report
    unsupported combinations clearly").

    An entry whose `PackageName`/`DisplayName` matches no known family is
    still returned — classified `unknown/custom` with its detected raw
    metadata intact — rather than dropped or raising, per SPEC's data-driven
    discovery requirement.
    """
    data = json.loads(settings_json_text)
    entries = data.get("InstalledPackages", [])

    results = []
    for entry in entries:
        package_name = str(entry.get("PackageName", ""))
        display_name = str(entry.get("DisplayName", package_name))
        family = match_family(package_name, display_name)

        if family is not None:
            family_id = family.id
            family_display_name = family.display_name
            family_group = family.group
            supported_platforms = family.supported_platforms
        else:
            family_id = UNKNOWN_FAMILY_ID
            family_display_name = UNKNOWN_FAMILY_DISPLAY_NAME
            family_group = UNKNOWN_FAMILY_GROUP
            supported_platforms = ()

        results.append(
            DiscoveredInstallation(
                package_name=package_name,
                display_name=display_name,
                library_path=str(entry.get("LibraryPath", "")),
                launch_command=entry.get("LaunchCommand"),
                python_version=entry.get("PythonVersion"),
                family_id=family_id,
                family_display_name=family_display_name,
                family_group=family_group,
                supported_platforms=supported_platforms,
                platform_supported=platform in supported_platforms,
                raw=dict(entry),
            )
        )
    return results
