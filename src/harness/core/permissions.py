"""Default permission policies (PERM-001, SPEC/SECURITY_PRIVACY.md).

Conservative by default: only `read` and `model_lifecycle` (already gated by an
explicit user-initiated load/unload call, LP-009) are `allow`; `destructive` is
`deny` outright; everything else asks. An operator overrides any class via
`PUT /permissions/policies/{class}` — `PermissionPolicyRepo` persists the override
and these defaults apply only where no override exists.
"""

from __future__ import annotations

from harness.core.domain import PermissionClass, PermissionPolicy

ALL_PERMISSION_CLASSES: tuple[PermissionClass, ...] = (
    "read",
    "write",
    "execute",
    "network",
    "git",
    "process",
    "model_lifecycle",
    "creative_generation",
    "training",
    "destructive",
)

DEFAULT_POLICIES: dict[PermissionClass, PermissionPolicy] = {
    "read": "allow",
    "write": "ask",
    "execute": "ask",
    "network": "ask",
    "git": "ask",
    "process": "ask",
    "model_lifecycle": "allow",
    "creative_generation": "ask",
    "training": "ask",
    "destructive": "deny",
}
