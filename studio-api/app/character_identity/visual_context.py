"""Canonical Character visual context for Co-Director and generation consumers.

Preferred order for inspection / Co-Director:

1. approved identity VIEW (never the composed multi-panel CRS)
2. approved CRS sheet (authority document ? inspection only)
3. approved / canonical hero_identity (if it is not the composed sheet)
4. uploaded reference_image

Scene generation (purpose="scene") never returns the composed CRS document
as identity pixels / sourceAssetId. It selects a canonical identity VIEW
matching the camera, or a clearly marked derived-crop request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset


@dataclass(frozen=True)
class CharacterVisualContext:
    asset_id: str
    source: str
    character_id: str
    character_name: str | None = None
    crs_revision: int = 0
    approval_status: str | None = None
    reference_type: str | None = None
    crs_sheet_asset_id: str | None = None
    camera_role: str | None = None
    lineage: dict[str, Any] = field(default_factory=dict)
    derived_crop_request: dict[str, Any] | None = None


@dataclass(frozen=True)
class SceneIdentityView:
    """Scene-generation identity selection. Never the composed CRS sheet."""

    asset_id: str | None
    sourceAssetId: str | None
    reference_role: str | None
    camera_role: str
    source: str
    character_id: str
    character_name: str | None
    crs_sheet_asset_id: str | None
    crs_revision: int
    lineage: dict[str, Any]
    derived_crop_request: dict[str, Any] | None = None
    approval_status: str | None = None


def _usable_image_asset(db: Session, project_id: str, asset_id: str | None) -> Asset | None:
    if not asset_id or not project_id:
        return None
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        return None
    if not (asset.kind or "").startswith("image"):
        return None
    path = Path(asset.path) if asset.path else None
    if path is None or not path.is_file():
        return None
    return asset


def _lineage_from_row(row: Any) -> dict[str, Any]:
    raw = getattr(row, "generation_lineage_json", None) or "{}"
    try:
        import json

        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_scene_identity_view(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    camera: str | None = None,
    framing: str | None = None,
) -> SceneIdentityView | None:
    """Pick the identity VIEW for SCENE_GENERATION.

    Never returns the composed CRS sheet as asset_id / sourceAssetId.
    If derived views are missing, returns a marked derived-crop request
    (hero close-up region on a 2x2 sheet) instead of the full document.
    """
    if not project_id or not character_id:
        return None

    try:
        from .crs_identity_views import (
            derived_crop_request,
            normalize_camera_role,
            pick_identity_view_row,
            scene_identity_source_asset_id,
        )
        from .crs_service import get_crs_summary
        from .models import CharacterProfileRow
    except Exception:
        return None

    profile = db.get(CharacterProfileRow, character_id)
    if profile is None or str(profile.project_id) != str(project_id):
        return None
    name = str(profile.name or "").strip() or None
    approval = str(profile.approval_status or "candidate").lower()
    camera_role = normalize_camera_role(camera, framing)

    summary = None
    try:
        summary = get_crs_summary(db, project_id, character_id)
    except Exception:
        summary = None
    crs_revision = int(getattr(summary, "crs_revision", 0) or 0)
    sheet_id = str(getattr(summary, "approved_reference_asset_id", None) or "") or None
    sheet_asset = _usable_image_asset(db, project_id, sheet_id) if sheet_id else None
    if sheet_asset is None:
        sheet_id = None

    row = pick_identity_view_row(
        db,
        character_id,
        camera=camera,
        framing=framing,
        sheet_asset_id=sheet_id,
    )
    if row is not None:
        asset = _usable_image_asset(db, project_id, str(row.asset_id))
        if asset is not None and str(asset.id) != str(sheet_id or ""):
            source_id = scene_identity_source_asset_id(
                view_asset_id=str(asset.id),
                sheet_asset_id=sheet_id,
            )
            lineage = _lineage_from_row(row)
            if sheet_id and not lineage.get("sourceCrsAssetId"):
                lineage = {
                    **lineage,
                    "sourceCrsAssetId": sheet_id,
                    "sourceCrsRevision": crs_revision,
                }
            return SceneIdentityView(
                asset_id=str(asset.id),
                sourceAssetId=source_id,
                reference_role=str(row.reference_role or ""),
                camera_role=camera_role,
                source="identity_view",
                character_id=character_id,
                character_name=name,
                crs_sheet_asset_id=sheet_id,
                crs_revision=crs_revision,
                lineage=lineage,
                approval_status=str(row.approval_status or approval).lower(),
            )

    request = None
    if sheet_id:
        request = derived_crop_request(
            sheet_asset_id=sheet_id,
            sheet_path=sheet_asset.path if sheet_asset is not None else None,
            camera=camera,
            framing=framing,
            crs_revision=crs_revision,
        )
    return SceneIdentityView(
        asset_id=None,
        sourceAssetId=None,
        reference_role=(request or {}).get("requestedRole"),
        camera_role=camera_role,
        source="derived_crop_request",
        character_id=character_id,
        character_name=name,
        crs_sheet_asset_id=sheet_id,
        crs_revision=crs_revision,
        lineage={
            "sourceCrsAssetId": sheet_id,
            "sourceCrsRevision": crs_revision,
            "kind": "derived_crop_request",
        },
        derived_crop_request=request,
        approval_status=approval,
    )


def resolve_character_visual_context(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    camera: str | None = None,
    framing: str | None = None,
    purpose: str = "inspection",
) -> CharacterVisualContext | None:
    """Return the current production visual reference for a character, if any.

    purpose="scene": never the composed CRS sheet (identity VIEW or crop request).
    purpose="inspection": may fall back to the approved sheet document.
    """
    if not project_id or not character_id:
        return None

    try:
        from .crs_identity_views import normalize_camera_role
        from .crs_service import get_crs_summary
        from .models import CharacterProfileRow
        from .service import list_references, resolve_approved_reference
    except Exception:
        return None

    profile = db.get(CharacterProfileRow, character_id)
    if profile is None or str(profile.project_id) != str(project_id):
        return None
    name = str(profile.name or "").strip() or None
    approval = str(profile.approval_status or "candidate").lower()
    camera_role = normalize_camera_role(camera, framing) if (camera or framing) else None

    summary = None
    try:
        summary = get_crs_summary(db, project_id, character_id)
    except Exception:
        summary = None
    crs_revision = int(getattr(summary, "crs_revision", 0) or 0)
    crs_asset_id = getattr(summary, "approved_reference_asset_id", None) if summary else None
    sheet_id = str(crs_asset_id) if crs_asset_id else None

    if purpose == "scene":
        view = resolve_scene_identity_view(
            db, project_id, character_id, camera=camera, framing=framing
        )
        if view is None:
            return None
        return CharacterVisualContext(
            asset_id=str(view.asset_id or ""),
            source=view.source,
            character_id=character_id,
            character_name=name,
            crs_revision=crs_revision,
            approval_status=view.approval_status or approval,
            reference_type=view.reference_role,
            crs_sheet_asset_id=view.crs_sheet_asset_id,
            camera_role=view.camera_role,
            lineage=dict(view.lineage or {}),
            derived_crop_request=view.derived_crop_request,
        )

    view = resolve_scene_identity_view(
        db, project_id, character_id, camera=camera, framing=framing
    )
    if view is not None and view.source == "identity_view" and view.asset_id:
        if _usable_image_asset(db, project_id, str(view.asset_id)):
            return CharacterVisualContext(
                asset_id=str(view.asset_id),
                source="identity_view",
                character_id=character_id,
                character_name=name,
                crs_revision=crs_revision,
                approval_status=view.approval_status or approval,
                reference_type=view.reference_role,
                crs_sheet_asset_id=sheet_id,
                camera_role=view.camera_role,
                lineage=dict(view.lineage or {}),
            )

    if sheet_id and _usable_image_asset(db, project_id, sheet_id):
        return CharacterVisualContext(
            asset_id=sheet_id,
            source="crs_sheet",
            character_id=character_id,
            character_name=name,
            crs_revision=crs_revision,
            approval_status=approval,
            reference_type="crs_sheet",
            crs_sheet_asset_id=sheet_id,
            camera_role=camera_role,
        )

    try:
        hero_id = resolve_approved_reference(db, character_id, "hero_identity")
    except Exception:
        hero_id = None
    if hero_id and str(hero_id) != str(sheet_id or "") and _usable_image_asset(db, project_id, str(hero_id)):
        return CharacterVisualContext(
            asset_id=str(hero_id),
            source="hero_identity",
            character_id=character_id,
            character_name=name,
            crs_revision=crs_revision,
            approval_status=approval,
            reference_type="hero_identity",
            crs_sheet_asset_id=sheet_id,
            camera_role=camera_role,
        )

    refs: list[dict[str, Any]] = []
    try:
        refs = list_references(db, project_id, character_id)
    except Exception:
        refs = []
    for role in ("reference_image", "hero_portrait"):
        for row in refs:
            if str(row.get("reference_role") or "").lower() != role:
                continue
            asset_id = row.get("asset_id")
            if asset_id and str(asset_id) == str(sheet_id or ""):
                continue
            if asset_id and _usable_image_asset(db, project_id, str(asset_id)):
                return CharacterVisualContext(
                    asset_id=str(asset_id),
                    source="reference_image",
                    character_id=character_id,
                    character_name=name,
                    crs_revision=crs_revision,
                    approval_status=str(row.get("approval_status") or approval).lower(),
                    reference_type=role,
                    crs_sheet_asset_id=sheet_id,
                    camera_role=camera_role,
                )
    return None


def resolve_character_visual_asset_id(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    camera: str | None = None,
    framing: str | None = None,
    purpose: str = "inspection",
) -> str | None:
    ctx = resolve_character_visual_context(
        db,
        project_id,
        character_id,
        camera=camera,
        framing=framing,
        purpose=purpose,
    )
    if ctx is None:
        return None
    asset_id = str(ctx.asset_id or "").strip()
    return asset_id or None
