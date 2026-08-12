"""Visual Continuity Session — optional batch continuity for Image→Storyboard sequences."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..config import settings


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root(project_id: str) -> Path:
    base = Path(settings.data_dir) / "visual_continuity" / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def _index_path(project_id: str) -> Path:
    return _root(project_id) / "sessions.json"


def _read_index(project_id: str) -> list[dict[str, Any]]:
    path = _index_path(project_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_index(project_id: str, items: list[dict[str, Any]]) -> None:
    path = _index_path(project_id)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


class VisualContinuitySession(BaseModel):
    id: str
    projectId: str
    sceneId: Optional[str] = None
    characterIds: list[str] = Field(default_factory=list)
    locationIds: list[str] = Field(default_factory=list)
    costumeIds: list[str] = Field(default_factory=list)
    projectStyleVersion: Optional[str] = None
    referenceAssetIds: list[str] = Field(default_factory=list)
    approvedImageIds: list[str] = Field(default_factory=list)
    # Session-level cinematic locks (compiled into creative context; not a creator dashboard)
    lightingDirection: Optional[str] = None
    colorTreatment: Optional[str] = None
    lensLanguage: Optional[str] = None
    aspectRatio: Optional[str] = None
    visualEra: Optional[str] = None
    productionStyle: Optional[str] = None
    createdAt: str = ""
    updatedAt: str = ""


def list_sessions(project_id: str) -> list[VisualContinuitySession]:
    out: list[VisualContinuitySession] = []
    for raw in _read_index(project_id):
        try:
            out.append(VisualContinuitySession.model_validate(raw))
        except Exception:
            continue
    return out


def get_session(project_id: str, session_id: str) -> VisualContinuitySession | None:
    for s in list_sessions(project_id):
        if s.id == session_id:
            return s
    return None


def save_session(session: VisualContinuitySession) -> VisualContinuitySession:
    items = _read_index(session.projectId)
    payload = session.model_dump()
    items = [i for i in items if i.get("id") != session.id]
    items.insert(0, payload)
    _write_index(session.projectId, items[:200])
    return session


def create_session(
    project_id: str,
    *,
    scene_id: str | None = None,
    character_ids: list[str] | None = None,
    location_ids: list[str] | None = None,
    costume_ids: list[str] | None = None,
    project_style_version: str | None = None,
    reference_asset_ids: list[str] | None = None,
    lighting_direction: str | None = None,
    color_treatment: str | None = None,
    lens_language: str | None = None,
    aspect_ratio: str | None = None,
    visual_era: str | None = None,
    production_style: str | None = None,
) -> VisualContinuitySession:
    now = _now()
    session = VisualContinuitySession(
        id=str(uuid.uuid4()),
        projectId=project_id,
        sceneId=scene_id,
        characterIds=list(character_ids or []),
        locationIds=list(location_ids or []),
        costumeIds=list(costume_ids or []),
        projectStyleVersion=project_style_version,
        referenceAssetIds=list(reference_asset_ids or []),
        approvedImageIds=[],
        lightingDirection=lighting_direction,
        colorTreatment=color_treatment,
        lensLanguage=lens_language,
        aspectRatio=aspect_ratio,
        visualEra=visual_era,
        productionStyle=production_style,
        createdAt=now,
        updatedAt=now,
    )
    return save_session(session)


def patch_session(
    project_id: str,
    session_id: str,
    patch: dict[str, Any],
) -> VisualContinuitySession | None:
    session = get_session(project_id, session_id)
    if not session:
        return None
    data = session.model_dump()
    allowed = {
        "sceneId",
        "characterIds",
        "locationIds",
        "costumeIds",
        "projectStyleVersion",
        "referenceAssetIds",
        "approvedImageIds",
        "lightingDirection",
        "colorTreatment",
        "lensLanguage",
        "aspectRatio",
        "visualEra",
        "productionStyle",
    }
    for k, v in (patch or {}).items():
        if k in allowed:
            data[k] = v
    data["updatedAt"] = _now()
    return save_session(VisualContinuitySession.model_validate(data))


def approve_image(
    project_id: str,
    session_id: str,
    asset_id: str,
) -> VisualContinuitySession | None:
    session = get_session(project_id, session_id)
    if not session:
        return None
    ids = list(session.approvedImageIds)
    if asset_id not in ids:
        ids.append(asset_id)
    return patch_session(project_id, session_id, {"approvedImageIds": ids})


def inherit_from_scene(project_id: str, scene_id: str) -> VisualContinuitySession:
    """
    Create (or refresh) a continuity session from scene / bible / identity context.
    Creator-facing: Continuity → [ Inherit from scene ].
    """
    character_ids: list[str] = []
    location_ids: list[str] = []
    costume_ids: list[str] = []
    reference_asset_ids: list[str] = []
    project_style_version: str | None = None
    lighting: str | None = None
    color: str | None = None
    lens: str | None = None
    aspect: str | None = "16:9"
    era: str | None = None
    style: str | None = None

    try:
        from ..codirector.production_intent.compiler import compile_creative_context

        packaged = compile_creative_context(
            project_id=project_id,
            scene_id=scene_id,
            objective="visual_continuity_inherit",
            extra={"sceneId": scene_id},
        )
        ctx = packaged.model_dump() if hasattr(packaged, "model_dump") else dict(packaged or {})
        chars = ctx.get("characters") or ctx.get("characterIds") or []
        if isinstance(chars, list):
            character_ids = [str(c.get("id") if isinstance(c, dict) else c) for c in chars if c]
        locs = ctx.get("locations") or ctx.get("locationIds") or []
        if isinstance(locs, list):
            location_ids = [str(l.get("id") if isinstance(l, dict) else l) for l in locs if l]
        refs = ctx.get("approvedReferences") or ctx.get("referenceAssetIds") or []
        if isinstance(refs, list):
            reference_asset_ids = [
                str(r.get("assetId") or r.get("id") if isinstance(r, dict) else r) for r in refs if r
            ]
        vl = ctx.get("visualLanguage") if isinstance(ctx.get("visualLanguage"), dict) else {}
        cine = ctx.get("cinematography") if isinstance(ctx.get("cinematography"), dict) else {}
        light = ctx.get("lighting") if isinstance(ctx.get("lighting"), dict) else {}
        color = vl.get("colorTreatment") or color
        era = vl.get("visualEra") or era
        style = vl.get("productionStyle") or style
        lens = cine.get("lens") or lens
        aspect = cine.get("aspectRatio") or aspect
        lighting = light.get("setup") or light.get("direction") or lighting
        project_style_version = (
            str(ctx.get("projectStyleVersion") or ctx.get("styleVersion") or "") or None
        )
    except Exception:
        pass

    # Reuse most recent session for same scene when present
    for existing in list_sessions(project_id):
        if existing.sceneId == scene_id:
            return patch_session(
                project_id,
                existing.id,
                {
                    "characterIds": character_ids or existing.characterIds,
                    "locationIds": location_ids or existing.locationIds,
                    "costumeIds": costume_ids or existing.costumeIds,
                    "referenceAssetIds": reference_asset_ids or existing.referenceAssetIds,
                    "projectStyleVersion": project_style_version or existing.projectStyleVersion,
                    "lightingDirection": lighting or existing.lightingDirection,
                    "colorTreatment": color or existing.colorTreatment,
                    "lensLanguage": lens or existing.lensLanguage,
                    "aspectRatio": aspect or existing.aspectRatio,
                    "visualEra": era or existing.visualEra,
                    "productionStyle": style or existing.productionStyle,
                },
            ) or existing

    return create_session(
        project_id,
        scene_id=scene_id,
        character_ids=character_ids,
        location_ids=location_ids,
        costume_ids=costume_ids,
        project_style_version=project_style_version,
        reference_asset_ids=reference_asset_ids,
        lighting_direction=lighting,
        color_treatment=color,
        lens_language=lens,
        aspect_ratio=aspect,
        visual_era=era,
        production_style=style,
    )


def session_to_creative_extras(session: VisualContinuitySession) -> dict[str, Any]:
    """Compile session into creativeContext extras for image_product.compile."""
    return {
        "sceneId": session.sceneId,
        "continuitySessionId": session.id,
        "continuity": {
            "sessionId": session.id,
            "characterIds": session.characterIds,
            "locationIds": session.locationIds,
            "costumeIds": session.costumeIds,
            "approvedImageIds": session.approvedImageIds,
        },
        "approvedReferences": [
            {"assetId": aid, "role": "continuity"} for aid in session.referenceAssetIds
        ]
        + [{"assetId": aid, "role": "approved_frame"} for aid in session.approvedImageIds[-4:]],
        "cinematography": {
            "lens": session.lensLanguage,
            "aspectRatio": session.aspectRatio or "16:9",
        },
        "lighting": {"direction": session.lightingDirection} if session.lightingDirection else {},
        "visualLanguage": {
            "colorTreatment": session.colorTreatment,
            "visualEra": session.visualEra,
            "productionStyle": session.productionStyle,
            "projectStyleVersion": session.projectStyleVersion,
        },
    }
