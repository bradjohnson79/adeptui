"""Auto-mask for Scene Creator region-edit. Brush remains the fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .contracts import PerceptionCapability
from .service import get_capability
from .spatial_draft import load_spatial_draft

_SELECT_UNAVAILABLE = (
    "Intelligent selection is not installed. Paint the region, or open Setup "
    "and install the Adept UI Essentials Pack."
)


def resolve_auto_mask(
    db: Session,
    project_id: str,
    map_id: str,
    label: str,
    asset_id: str = "",
) -> dict[str, Any]:
    capability: PerceptionCapability = get_capability()
    if capability.autoMask == "unavailable" and capability.select == "unavailable":
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": _SELECT_UNAVAILABLE,
        }
    draft = load_spatial_draft(db, project_id, map_id) if map_id else None
    source_asset_id = asset_id or (draft.sourceAssetId if draft else "")
    entity_id = ""
    wanted = (label or "").strip().lower()
    if draft is not None:
        for fill in draft.proposedFills:
            if wanted and wanted not in fill.label.lower() and wanted not in fill.tag.lower():
                continue
            entity_id = fill.perceptionEntityId
            if entity_id:
                break
    if source_asset_id:
        from ...image_product.masks import get_mask
        from .cache import get_cached_selection
        from .paths import SAM21_REVISION

        # Never spawn the SAM/Comfy worker on this request. A 30–180s GPU
        # select holds SQLite and restarts Playwright workers, which drops
        # beforeAll state and looks like Accept deleted cameras.
        cached = get_cached_selection(
            project_id=project_id,
            asset_id=source_asset_id,
            frame_time_ms=0,
            entity=(label or "object").strip(),
            model_id="sam21-hiera-tiny",
            model_version=SAM21_REVISION,
            source="text" if label else "click",
        )
        if cached and cached.get("maskAssetId") and get_mask(project_id, str(cached["maskAssetId"])):
            return {
                "ok": True,
                "maskAssetId": str(cached["maskAssetId"]),
                "status": "available",
                "fillId": entity_id,
                "label": label,
                "selection": cached,
                "cached": True,
                "message": "Selected.",
            }
        return {
            "ok": False,
            "maskAssetId": "",
            "status": capability.autoMask,
            "message": (
                _SELECT_UNAVAILABLE
                if capability.autoMask == "unavailable"
                else "Could not select automatically. Paint the region."
            ),
        }
    if draft is None:
        return {
            "ok": False,
            "maskAssetId": "",
            "status": capability.autoMask,
            "message": "Run CD Scene Review first, then try again — or paint the region.",
        }
    return {
        "ok": False,
        "maskAssetId": "",
        "status": capability.autoMask,
        "message": f'Could not automatically select "{label or "that object"}". Paint the region.',
    }
