"""Timeline image-reference eligibility.

Persisted explicit classification stays ``Asset.prompt_meta_json.approvedAs``.
Creator commits (saved Character, Prop, Environment) are read at request time
and are not a second stored role. Consumers receive transient fields only:

- effectiveReferenceRole
- referenceRoleSource  (explicit | creator | override | media | none)
- creatorReferenceRole

Precedence for an image:

1. approvedAs in {character, prop, environment}
2. else a canonical creator commit
3. else no image-tab eligibility

``approvedAs = scene_frame`` does not grant Character, Prop, or Environment.
Video and audio keep their media identity. Filename is never consulted.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db import Asset

IMAGE_ROLES = frozenset({"character", "prop", "environment"})
HERO_REFERENCE_ROLES = frozenset({"hero_identity", "hero_portrait"})
_IMAGE_KINDS = frozenset({"image", "img", "still"})
_RANK = {"character": 3, "prop": 2, "environment": 1}


class ReferenceClassificationError(ValueError):
    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(detail)


def _meta(prompt_meta: Any) -> dict[str, Any]:
    if isinstance(prompt_meta, dict):
        return dict(prompt_meta)
    if isinstance(prompt_meta, str) and prompt_meta.strip():
        try:
            parsed = json.loads(prompt_meta)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def explicit_image_role(prompt_meta: Any) -> str | None:
    role = str(_meta(prompt_meta).get("approvedAs") or "").strip().lower()
    if role in IMAGE_ROLES:
        return role
    return None


def _prefer(found: dict[str, str], asset_id: Any, role: str) -> None:
    aid = str(asset_id or "").strip()
    if not aid or role not in IMAGE_ROLES:
        return
    current = found.get(aid)
    if current is None or _RANK[role] > _RANK[current]:
        found[aid] = role


def creator_roles_for_project(db: Session, project_id: str) -> dict[str, str]:
    """Asset id → intrinsic creator role. Character outranks prop, then environment."""
    from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
    from app.environment_reference_sheet.store import list_sheets
    from app.prop_creator.service import is_approved, list_props

    found: dict[str, str] = {}
    rows = (
        db.query(CharacterReferenceAssetRow)
        .join(
            CharacterProfileRow,
            CharacterProfileRow.id == CharacterReferenceAssetRow.character_profile_id,
        )
        .filter(CharacterProfileRow.project_id == project_id)
        .all()
    )
    for ref in rows:
        role_name = str(ref.reference_role or "")
        committed = bool(ref.canonical) or str(ref.approval_status or "") == "approved"
        if role_name in HERO_REFERENCE_ROLES and committed:
            _prefer(found, ref.asset_id, "character")

    for prop in list_props(db, project_id):
        if is_approved(prop):
            _prefer(found, prop.approved_asset_id, "prop")
        if str(getattr(prop, "primary_phase", "") or "") == "approved":
            _prefer(found, getattr(prop, "primary_approved_asset_id", None), "prop")

    for sheet in list_sheets(project_id):
        status = str(getattr(sheet, "status", "") or "")
        if status in {"approved", "registered"}:
            _prefer(found, getattr(sheet, "ers_composite_asset_id", None), "environment")
        for view in getattr(sheet, "directionalViews", None) or []:
            if str(getattr(view, "status", "") or "") == "approved":
                _prefer(found, getattr(view, "approvedAssetId", None), "environment")
    return found


def resolve_reference_role(
    *,
    kind: str | None,
    prompt_meta: Any,
    creator_role: str | None,
) -> dict[str, Any]:
    media = str(kind or "").strip().lower()
    creator = creator_role if creator_role in IMAGE_ROLES else None
    if media in {"video", "audio"}:
        return {
            "effectiveReferenceRole": media,
            "referenceRoleSource": "media",
            "creatorReferenceRole": creator,
        }
    if media not in _IMAGE_KINDS:
        return {
            "effectiveReferenceRole": None,
            "referenceRoleSource": "none",
            "creatorReferenceRole": creator,
        }
    explicit = explicit_image_role(prompt_meta)
    if explicit and creator and explicit != creator:
        source, role = "override", explicit
    elif explicit and creator:
        source, role = "creator", explicit
    elif explicit:
        source, role = "explicit", explicit
    elif creator:
        source, role = "creator", creator
    else:
        source, role = "none", None
    return {
        "effectiveReferenceRole": role,
        "referenceRoleSource": source,
        "creatorReferenceRole": creator,
    }


def annotate_library_items(db: Session, project_id: str, items: list[dict[str, Any]]) -> None:
    commits = creator_roles_for_project(db, project_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        aid = str(item.get("id") or "")
        item.update(
            resolve_reference_role(
                kind=str(item.get("kind") or ""),
                prompt_meta=item.get("prompt_meta_json"),
                creator_role=commits.get(aid),
            )
        )


def stamp_aligned_role(asset: Asset, role: str) -> bool:
    """Write approvedAs for a creator commit unless the creator already overrode it.

    A matching or empty classification is aligned. A different image role is an
    explicit override and is left alone. ``scene_frame`` is not an override.
    """
    if role not in IMAGE_ROLES:
        return False
    meta = _meta(asset.prompt_meta_json)
    current = str(meta.get("approvedAs") or "").strip().lower()
    if current in IMAGE_ROLES and current != role:
        return False
    if current == role:
        return False
    meta["approvedAs"] = role
    asset.prompt_meta_json = json.dumps(meta, ensure_ascii=False)
    return True


def set_explicit_reference_role(
    db: Session,
    project_id: str,
    asset_id: str,
    approved_as: str | None,
) -> dict[str, Any]:
    """Set or clear prompt_meta_json.approvedAs. Does not bind a shot or create a character."""
    asset = db.get(Asset, asset_id)
    if asset is None or str(asset.project_id or "") != project_id:
        raise ReferenceClassificationError(404, "Asset not found")
    kind = str(asset.kind or "").strip().lower()
    if kind in {"video", "audio"}:
        raise ReferenceClassificationError(400, "Video and audio keep their media role.")
    if kind not in _IMAGE_KINDS:
        raise ReferenceClassificationError(400, "Only images can be classified as Character, Prop, or Environment.")
    requested = None if approved_as is None else str(approved_as).strip().lower()
    if requested == "":
        requested = None
    if requested is not None and requested not in IMAGE_ROLES:
        raise ReferenceClassificationError(400, "Choose Character, Prop, or Environment.")
    meta = _meta(asset.prompt_meta_json)
    if requested is None:
        meta.pop("approvedAs", None)
    else:
        meta["approvedAs"] = requested
    asset.prompt_meta_json = json.dumps(meta, ensure_ascii=False)
    db.commit()
    db.refresh(asset)
    item = {
        "id": asset.id,
        "kind": asset.kind,
        "filename": asset.filename,
        "tag": asset.tag,
        "prompt_meta_json": asset.prompt_meta_json,
    }
    annotate_library_items(db, project_id, [item])
    return item
