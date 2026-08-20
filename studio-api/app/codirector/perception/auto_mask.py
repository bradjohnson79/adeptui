"""Auto-mask for Scene Creator region-edit. Brush remains the fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .contracts import PerceptionCapability
from .service import get_capability
from .spatial_draft import load_spatial_draft


def resolve_auto_mask(
    db: Session,
    project_id: str,
    map_id: str,
    label: str,
) -> dict[str, Any]:
    capability: PerceptionCapability = get_capability()
    if capability.autoMask == "unavailable":
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": "Automatic object select is unavailable. Paint the region instead.",
        }
    draft = load_spatial_draft(db, project_id, map_id)
    if draft is None:
        return {
            "ok": False,
            "maskAssetId": "",
            "status": capability.autoMask,
            "message": "Run CD Scene Review first, then try again — or paint the region.",
        }
    wanted = (label or "").strip().lower()
    for fill in draft.proposedFills:
        entity_id = fill.perceptionEntityId
        if not entity_id:
            continue
        if wanted and wanted not in fill.label.lower() and wanted not in fill.tag.lower():
            continue
        # Geometry worker currently returns boxes, not persisted mask assets.
        # Do not pretend a box is a mask.
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "testing",
            "fillId": fill.id,
            "label": fill.label,
            "message": "A box was found, but a paint-ready mask is not ready yet. Paint the region.",
        }
    return {
        "ok": False,
        "maskAssetId": "",
        "status": capability.autoMask,
        "message": f'Could not automatically select "{label or "that object"}". Paint the region.',
    }
