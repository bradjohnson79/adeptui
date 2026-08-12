"""Path helpers for project lock enforcement."""

from __future__ import annotations

import re
from typing import Optional

# /api/projects/{id}/... and /api/codirector/projects/{id}/...
_PROJECT_PATH = re.compile(
    r"^/api/(?:codirector/)?projects/([0-9a-fA-F-]{36})(/.*)?$"
)

# Security endpoints that remain reachable while locked
_EXEMPT_SUFFIXES = (
    "/security",
    "/security/unlock",
    "/security/password",
    "/security/reset",
    "/security/audit",
    # Duplicate may authorize via password in body when locked (see extra.duplicate_project).
    "/duplicate",
)


def project_id_from_path(path: str) -> Optional[str]:
    m = _PROJECT_PATH.match(path or "")
    if not m:
        return None
    return m.group(1)


def is_security_exempt(path: str) -> bool:
    m = _PROJECT_PATH.match(path or "")
    if not m:
        return False
    suffix = m.group(2) or ""
    if suffix in _EXEMPT_SUFFIXES:
        return True
    return False


def should_enforce_lock(path: str, method: str) -> bool:
    """True when this request must present a valid unlock grant if the project is protected."""
    pid = project_id_from_path(path)
    if not pid:
        return False
    if is_security_exempt(path):
        return False
    return True
