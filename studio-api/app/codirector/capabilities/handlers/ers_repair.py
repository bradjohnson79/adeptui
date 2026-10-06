"""Capability handler: ers.repair

Repair / regenerate an Environment Reference Sheet without requiring Spatial Map.
Uses continuity repairStrategy when present; otherwise re-runs ers.generate for
the existing sheet (prompt/reference grounding). Approved views stay protected
unless the creator asks for rebuild_unapproved_views / full rebuild.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str = "",
    *,
    sheet_id: str = "",
    sheetId: str = "",
    spatial_map_id: str = "",
    spatialMapId: str = "",
    repair_strategy: str = "",
    repairStrategy: str = "",
    prompt: str = "",
    environmentPrompt: str = "",
    name: str = "",
    description: str = "",
    visual_style: str = "",
    scene_id: str = "",
    hosted_model_id: str = "",
    hostedModelId: str = "",
    model: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from ....environment_reference_sheet.store import list_sheets, load_sheet

    sid = str(sheet_id or sheetId or "").strip()
    map_id = str(spatial_map_id or spatialMapId or "").strip()
    strategy = str(repair_strategy or repairStrategy or "").strip() or "preserve_approved_views"

    sheet = None
    if sid:
        sheet = load_sheet(project_id, sid)
    if sheet is None:
        sheets = list_sheets(project_id) or []
        # Prefer a sheet that already has composite / approved status.
        with_composite = [
            s
            for s in sheets
            if str(getattr(s, "ers_composite_asset_id", "") or "").strip()
            or getattr(s, "status", "") in {"complete", "registered", "approved"}
        ]
        sheet = with_composite[0] if with_composite else (sheets[0] if sheets else None)

    if sheet is None:
        return {
            "job_ids": [],
            "child_jobs": [],
            "surface_type": "ers_generation",
            "status": "failed",
            "error": (
                "No Environment Reference Sheet found to repair. "
                "Create one in Environment Creator Express first (Spatial Map not required)."
            ),
            "creatorAck": "I need an existing ERS sheet before repair.",
        }

    # Continuity may recommend a strategy; never invent Spatial Map as a gate.
    try:
        from ....environment_reference_sheet.continuity import validate_sheet

        continuity = validate_sheet(sheet)
        if not str(repair_strategy or repairStrategy or "").strip():
            strategy = str(getattr(continuity, "repairStrategy", None) or strategy)
    except Exception:
        continuity = None

    if not map_id:
        spatial = getattr(sheet, "spatialMap", None)
        map_id = str(getattr(spatial, "mapId", "") or "") if spatial is not None else ""

    from . import ers_generate

    result = ers_generate.handle(
        db,
        project_id,
        execution_id,
        spatial_map_id=map_id,  # optional; empty is allowed (v1.1)
        sheet_id=str(getattr(sheet, "sheetId", "") or sid),
        sheetId=str(getattr(sheet, "sheetId", "") or sid),
        scene_id=scene_id or str(getattr(sheet, "sceneId", "") or ""),
        visual_style=visual_style,
        name=name or str(getattr(sheet, "name", "") or ""),
        description=description or str(getattr(sheet, "description", "") or ""),
        prompt=prompt,
        environmentPrompt=environmentPrompt,
        hosted_model_id=hosted_model_id,
        hostedModelId=hostedModelId,
        model=model,
    )
    if isinstance(result, dict):
        result = {
            **result,
            "repair_strategy": strategy,
            "repaired_sheet_id": str(getattr(sheet, "sheetId", "") or sid),
            "spatial_map_required": False,
            "surface_type": result.get("surface_type") or "ers_generation",
        }
        meta = ((result.get("child_jobs") or [{}])[0]).get("metadata") if result.get("child_jobs") else None
        if isinstance(meta, dict):
            meta["repairStrategy"] = strategy
    return result
