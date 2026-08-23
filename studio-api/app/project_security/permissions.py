"""Path helpers for project lock enforcement."""

from __future__ import annotations

import re
from pathlib import Path
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

# Media static mount (/media serves settings.data_dir). Project-scoped media
# lives under data/projects/{id}/... and data/assets/{id}/...; renders,
# lipsync outputs, thumbnails and job previews are served from those trees via
# mediaUrl() -> /media/projects/{id}/... (see CDX-069).
_MEDIA_PROJECT_PATH = re.compile(
    r"^/media/(?:projects|assets)/([0-9a-fA-F-]{36})(/.*)?$"
)

# A media URL shaped like project media whose id segment cannot be resolved to
# a project (e.g. a non-UUID segment). Fail closed on these.
_MEDIA_AMBIGUOUS_PATH = re.compile(
    r"^/media/(?:projects|assets)/[^/]+(?:/.*)?$"
)

# Project-id segment inside an arbitrary file path (/api/file?path=...).
_FILE_PROJECT_SEGMENT = re.compile(
    r"(?:^|/)(?:projects|assets)/([0-9a-fA-F-]{36})(?:/|$)"
)

# A file path that mentions a project scope but cannot resolve the id segment.
_FILE_AMBIGUOUS_SEGMENT = re.compile(
    r"(?:^|/)(?:projects|assets)/[^/]+(?:/|$)"
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


def project_id_from_media_path(path: str) -> Optional[str]:
    """Derive the owning project id from a /media URL.

    The static mount serves ``settings.data_dir``; project-scoped media is
    ``/media/projects/{id}/...`` or ``/media/assets/{id}/...`` (renders,
    lipsync outputs, thumbnails, job previews, project assets). Returns None
    for URLs that are not project-scoped.
    """
    m = _MEDIA_PROJECT_PATH.match(path or "")
    if not m:
        return None
    return m.group(1)


def media_path_is_ambiguous(path: str) -> bool:
    """True when the URL is shaped like project media but its id segment does
    not resolve to a project (non-UUID). These fail closed - we cannot verify
    the lock for an unknown project scope.
    """
    if _MEDIA_PROJECT_PATH.match(path or ""):
        return False
    return bool(_MEDIA_AMBIGUOUS_PATH.match(path or ""))


def project_id_from_file_path(raw_path: str) -> Optional[str]:
    """Derive the owning project id from a file path (/api/file?path=...).

    Accepts absolute Windows/posix paths or data-relative paths; the id is the
    first ``projects/{id}/`` or ``assets/{id}/`` segment. Returns None when the
    path is not project-scoped.
    """
    norm = (raw_path or "").replace("\\", "/")
    m = _FILE_PROJECT_SEGMENT.search(norm)
    if not m:
        return None
    return m.group(1)


def path_has_dotdot(raw_path: str) -> bool:
    """True when the caller supplied a parent-directory segment."""
    try:
        parts = Path(raw_path or "").parts
    except Exception:
        return True
    return any(part == ".." for part in parts)


def resolve_data_file_path(raw_path: str, data_dir: Path) -> Optional[Path]:
    """Resolve a /api/file path inside data_dir. None if traversal or escape."""
    if not raw_path or path_has_dotdot(raw_path):
        return None
    root = data_dir.resolve()
    p = Path(raw_path)
    try:
        resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
        resolved.relative_to(root)
    except Exception:
        return None
    return resolved


SCHNICK_PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278"
KORRI_CHARACTER_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b"
OWNER_WRITE_DENY_HEADER = "x-adept-deny-owner-writes"


def owner_write_denied(method: str, path: str, raw_file_path: str = "") -> bool:
    """True when a mutating request targets the owner Schnick/Korri fixtures."""
    if str(method or "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    blob = f"{path or ''} {raw_file_path or ''}"
    return SCHNICK_PROJECT_ID in blob or KORRI_CHARACTER_ID in blob


def file_path_is_ambiguous(raw_path: str) -> bool:
    """True when the file path mentions a project scope but the id segment is
    not resolvable (non-UUID). Fail closed - same rationale as
    ``media_path_is_ambiguous``.
    """
    norm = (raw_path or "").replace("\\", "/")
    if _FILE_PROJECT_SEGMENT.search(norm):
        return False
    return bool(_FILE_AMBIGUOUS_SEGMENT.search(norm))
