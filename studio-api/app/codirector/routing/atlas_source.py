"""Project-scoped Atlas source resolution. Never cross projects."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...db import Asset

_UUID_RE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
_TAG_RE = re.compile(r"\b(codirector_[a-z0-9_]{4,80})\b", re.I)
_AT_TAG_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_-]{1,80})")
_SOURCE_HINT_RE = re.compile(
    r"\b(?:library|this image|that (?:corridor|image|still|shot)|uploaded|attachment)\b",
    re.I,
)


def source_was_requested(message: str, attachment_ids: list[str] | None = None) -> bool:
    if attachment_ids:
        return True
    text = message or ""
    return bool(_UUID_RE.search(text) or _TAG_RE.search(text) or _AT_TAG_RE.search(text) or _SOURCE_HINT_RE.search(text))


def _asset_in_project(db: Session, project_id: str, asset_id: str) -> Optional[Asset]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    if str(asset.project_id or "") != project_id:
        return None
    return asset


def resolve_project_asset(db: Session, project_id: str, token: str) -> Optional[Asset]:
    token = (token or "").strip()
    if not token or not project_id:
        return None
    by_id = _asset_in_project(db, project_id, token)
    if by_id is not None:
        return by_id
    matches = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .filter(
            or_(
                Asset.tag == token,
                Asset.filename == token,
                Asset.filename.ilike(f"{token}%"),
                Asset.tag.ilike(f"%{token}%"),
            )
        )
        .order_by(Asset.created_at.desc())
        .limit(4)
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        exact = [a for a in matches if (a.tag or "") == token or (a.filename or "") == token]
        return exact[0] if exact else matches[0]
    return None


def _recent_environment_asset(db: Session, project_id: str) -> Optional[Asset]:
    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.kind == "image")
        .order_by(Asset.created_at.desc())
        .limit(24)
        .all()
    )
    for asset in rows:
        tag = (asset.tag or "").lower()
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(asset.prompt_meta_json or "{}") if asset.prompt_meta_json else {}
        except Exception:
            meta = {}
        purpose = str(meta.get("purpose") or meta.get("objective") or "").lower()
        if "atlas" in tag or purpose == "atlas_shot":
            continue
        if "corridor" in tag or "image_generate" in tag or purpose in {"codirector_image_generate", "environment"}:
            return asset
    return rows[0] if rows else None


def resolve_atlas_source_asset(
    db: Session,
    project_id: str,
    user_text: str,
    attachment_ids: list[str] | None = None,
) -> Optional[str]:
    """Return a project-owned asset id or None. Never another project's asset."""

    for raw in attachment_ids or []:
        asset = _asset_in_project(db, project_id, str(raw).strip())
        if asset is not None:
            return asset.id

    text = user_text or ""
    for match in _UUID_RE.findall(text):
        asset = _asset_in_project(db, project_id, match)
        if asset is not None:
            return asset.id

    for match in (*_TAG_RE.findall(text), *_AT_TAG_RE.findall(text)):
        asset = resolve_project_asset(db, project_id, match)
        if asset is not None:
            return asset.id

    if re.search(r"\b(?:that|this|the)\s+corridor\b", text, re.I) or re.search(
        r"\bthat\s+(?:image|still|shot)\b", text, re.I
    ):
        recent = _recent_environment_asset(db, project_id)
        if recent is not None:
            return recent.id
    return None
