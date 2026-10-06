"""Canonical Character Creator media URL.

The browser-reachable route is GET /api/projects/{project_id}/assets/{asset_id}/file.
Unscoped /api/assets/{asset_id}/file is retired (403).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset
from ..project_security.asset_file import (
    canonical_project_asset_file_url,
    is_canonical_project_asset_file_url,
)

CANONICAL_ASSET_FILE_PREFIX = "/api/projects/"
CANONICAL_ASSET_FILE_MID = "/assets/"
CANONICAL_ASSET_FILE_SUFFIX = "/file"


def canonical_asset_file_url(asset_id: str | None, project_id: str | None = None) -> str:
    return canonical_project_asset_file_url(project_id, asset_id)


def is_canonical_asset_file_url(url: str | None) -> bool:
    return is_canonical_project_asset_file_url(url)


def resolve_character_asset(db: Session, project_id: str, asset_id: str | None) -> dict[str, Any] | None:
    """Return assetId + canonical URL only when the Library file is actually readable."""
    aid = str(asset_id or "").strip()
    if not aid:
        return None
    asset = db.get(Asset, aid)
    if asset is None or not asset.path:
        return None
    if str(asset.project_id or "") != str(project_id or ""):
        from ..creator_scope.service import resolve_readable_asset

        if resolve_readable_asset(db, str(project_id or ""), aid) is None:
            return None
    path = Path(asset.path)
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    return {
        "assetId": aid,
        "assetUrl": canonical_asset_file_url(aid, project_id),
        "filename": asset.filename,
        "kind": asset.kind,
        "bytes": path.stat().st_size,
    }
