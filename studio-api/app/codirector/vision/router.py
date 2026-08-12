"""Vision Validation API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .engine import get_engine

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/validate")
def validate_asset(
    asset_id: str = Query(..., description="Asset ID to validate"),
    project_id: Optional[str] = Query(None),
    asset_type: str = Query("image"),
    run_continuity: bool = Query(False),
    run_lipsync: bool = Query(False),
) -> dict[str, Any]:
    """Run the vision validation pipeline against a media asset.

    Results are advisory only — human authority is absolute.
    Returns a structured ValidationResult with per-category checks.
    """
    from ...db import SessionLocal, Asset

    engine = get_engine()
    if not engine.enabled:
        raise HTTPException(status_code=503, detail={
            "error": "VISION_VALIDATION_DISABLED",
            "reason": "Vision Validation feature flag (STUDIO_FEATURE_VISION_VALIDATION_V1) is off",
        })

    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail={"error": "ASSET_NOT_FOUND", "assetId": asset_id})
        if not asset.path:
            raise HTTPException(status_code=404, detail={"error": "ASSET_FILE_MISSING", "assetId": asset_id})

        result = engine.validate(
            asset_id=asset_id,
            asset_path=asset.path,
            project_id=project_id,
            asset_type=asset_type,
            run_continuity=run_continuity,
            run_lipsync=run_lipsync,
        )
        return {"ok": True, "result": result.model_dump(mode="json"), "advisory": True}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "error": "VALIDATION_FAILED",
            "type": type(exc).__name__,
            "message": str(exc)[:200],
        })
    finally:
        db.close()


@router.get("/status")
def vision_validation_status() -> dict[str, Any]:
    """Return Vision Validation feature status."""
    engine = get_engine()
    return {
        "enabled": engine.enabled,
        "state": "ONLINE" if engine.enabled else "DISABLED",
        "reason": "Feature flag STUDIO_FEATURE_VISION_VALIDATION_V1 is off" if not engine.enabled else None,
    }
