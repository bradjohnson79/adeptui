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


@router.post("/environment-canon")
async def analyze_environment_canon(
    project_id: str = Query(..., description="Project ID"),
    map_id: str = Query(..., description="Spatial Map ID"),
    source_asset_id: str = Query(..., description="Authoritative environment image asset ID"),
    model_id: str = Query("gemini-3-pro"),
) -> dict[str, Any]:
    """Co-Director Vision: analyze the authoritative environment image into an
    Environment Visual Canon (identity/geometry/fixed architecture/furniture/
    spatial relationships/hard invariants/uncertainty) and persist it through
    the canonical trait store.

    Advisory inference only — creator corrections outrank it. Honest degrade:
    when no vision provider is configured the canon is persisted with
    availability="unavailable" and a reason; nothing is invented.
    """
    from ...db import SessionLocal, Asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, source_asset_id)
        if asset is None or asset.project_id != project_id:
            raise HTTPException(status_code=404, detail={"error": "ASSET_NOT_FOUND", "assetId": source_asset_id})
        if not asset.path:
            raise HTTPException(status_code=404, detail={"error": "ASSET_FILE_MISSING", "assetId": source_asset_id})

        from ...spatial_map.scene_intent import lineage_fingerprint
        from ...spatial_map.service import get_document
        from .visual_canon import (
            analyze_environment_visual_canon,
            load_visual_canon,
            save_visual_canon,
        )

        document = get_document(db, project_id, map_id)
        atlas_id = str(getattr(document, "backgroundAssetId", None) or "") if document else ""
        original_id = (
            str(getattr(document, "originalEnvironmentReferenceAssetId", None) or "")
            if document
            else ""
        )
        pixel_authority = original_id or atlas_id
        if pixel_authority and source_asset_id != pixel_authority:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "SOURCE_MISMATCH",
                    "message": (
                        "This environment description must use the same source photo "
                        "the Environment Reference Sheet uses."
                    ),
                },
            )
        intent = None
        try:
            from ...spatial_map.scene_intent import coerce_scene_intent

            intent = coerce_scene_intent(getattr(document, "sceneIntent", None))
        except Exception:
            intent = None
        fingerprint = lineage_fingerprint(
            intent,
            background_asset_id=atlas_id or source_asset_id,
            original_reference_asset_id=source_asset_id,
        )
        existing = load_visual_canon(db, project_id, map_id)
        if (
            existing is not None
            and existing.availability == "available"
            and str(existing.groundingFingerprint or "") == fingerprint
            and str(existing.sourceAssetId or "") == source_asset_id
        ):
            return {"ok": True, "canon": existing.model_dump(mode="json"), "reused": True, "advisory": True}

        canon = await analyze_environment_visual_canon(
            project_id=project_id,
            source_asset_id=source_asset_id,
            asset_path=asset.path,
            map_id=map_id,
            scene_intent_version=intent.version if intent is not None else None,
            grounding_fingerprint=fingerprint,
            model_id=model_id,
        )
        save_visual_canon(db, project_id, map_id, canon)
        db.commit()
        return {"ok": True, "canon": canon.model_dump(mode="json"), "reused": False, "advisory": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "error": "VISUAL_CANON_FAILED",
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
