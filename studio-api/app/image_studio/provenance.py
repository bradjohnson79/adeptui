"""Re-open cinematic generation provenance (prompt + refs + controls)."""

from __future__ import annotations

import json
from typing import Any

from ..db import Asset, Job, SessionLocal


def reopen_from_asset(project_id: str, asset_id: str) -> dict[str, Any] | None:
    """Build a reopen payload from asset prompt_meta / parent job — no DB hand-edits."""
    with SessionLocal() as db:
        asset = db.get(Asset, asset_id)
        if not asset or getattr(asset, "project_id", None) not in {project_id, None}:
            # Some schemas always have project_id
            if not asset:
                return None
            if getattr(asset, "project_id", project_id) != project_id:
                return None
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(asset.prompt_meta_json or "{}")
        except Exception:
            meta = {}

        intent = meta.get("imageIntent") if isinstance(meta.get("imageIntent"), dict) else {}
        if not intent and isinstance(meta.get("intent"), dict):
            intent = meta["intent"]
        recommendation = meta.get("recommendation") if isinstance(meta.get("recommendation"), dict) else {}
        cinematic = meta.get("cinematic") if isinstance(meta.get("cinematic"), dict) else {}
        creative = meta.get("creativeContext") if isinstance(meta.get("creativeContext"), dict) else {}
        spatial = creative.get("spatial") if isinstance(creative.get("spatial"), dict) else {}
        md = intent.get("metadata") if isinstance(intent.get("metadata"), dict) else {}

        # Merge job params — find by job id or by output_asset_id match
        job_params: dict[str, Any] = {}
        job_id = meta.get("jobId") or meta.get("job_id") or getattr(asset, "job_id", None)
        job = db.get(Job, str(job_id)) if job_id else None
        if job is None:
            try:
                candidates = (
                    db.query(Job)
                    .filter(Job.project_id == project_id)
                    .order_by(Job.created_at.desc())
                    .limit(40)
                    .all()
                )
                for cand in candidates:
                    try:
                        jp = json.loads(cand.params_json or "{}")
                    except Exception:
                        continue
                    if jp.get("output_asset_id") == asset_id or jp.get("outputAssetId") == asset_id:
                        job = cand
                        job_params = jp
                        job_id = cand.id
                        break
            except Exception:
                pass
        elif job is not None:
            try:
                job_params = json.loads(job.params_json or "{}")
            except Exception:
                job_params = {}

        if job_params:
            if isinstance(job_params.get("imageIntent"), dict):
                job_intent = job_params["imageIntent"]
                if not intent:
                    intent = job_intent
                job_md = job_intent.get("metadata") if isinstance(job_intent.get("metadata"), dict) else {}
                md = {**job_md, **md}
            if not cinematic and isinstance(job_params.get("cinematic"), dict):
                cinematic = job_params["cinematic"]
            if not creative and isinstance(job_params.get("creativeContext"), dict):
                creative = job_params["creativeContext"]
            if not recommendation and isinstance(job_params.get("recommendation"), dict):
                recommendation = job_params["recommendation"]

        prompt = (
            intent.get("prompt")
            or meta.get("prompt")
            or job_params.get("prompt")
            or ""
        )
        negative = (
            intent.get("negativePrompt")
            or meta.get("negative")
            or job_params.get("negative")
            or job_params.get("negativePrompt")
            or ""
        )
        refs = (
            intent.get("referenceIds")
            or job_params.get("referenceAssetIds")
            or meta.get("referenceAssetIds")
            or []
        )
        if not isinstance(refs, list):
            refs = []

        continuity_session_id = (
            md.get("continuitySessionId")
            or job_params.get("continuitySessionId")
            or creative.get("continuitySessionId")
            or meta.get("continuitySessionId")
        )
        scene_id = md.get("sceneId") or job_params.get("sceneId") or creative.get("sceneId")
        spatial_map_id = (
            md.get("spatialMapId")
            or job_params.get("spatialMapId")
            or creative.get("spatialMapId")
            or spatial.get("mapId")
        )
        spatial_map_version = (
            md.get("spatialMapVersion")
            or job_params.get("spatialMapVersion")
            or spatial.get("mapVersion")
            or meta.get("spatialMapVersion")
        )
        spatial_camera_id = (
            md.get("spatialCameraId")
            or job_params.get("spatialCameraId")
            or spatial.get("cameraId")
            or meta.get("spatialCameraId")
        )
        family = (
            intent.get("enginePreference")
            or recommendation.get("executionFamily")
            or job_params.get("modelFamilyPreference")
        )
        aspect = md.get("aspect") or cinematic.get("aspectRatio") or job_params.get("aspect") or "16:9"
        controls = {
            "lens": cinematic.get("lens") or (creative.get("cinematography") or {}).get("lens"),
            "lighting": cinematic.get("lighting")
            or (creative.get("lighting") or {}).get("setup")
            or (creative.get("lighting") or {}).get("direction"),
            "colorTreatment": cinematic.get("colorTreatment")
            or (creative.get("visualLanguage") or {}).get("colorTreatment"),
            "visualEra": cinematic.get("visualEra")
            or (creative.get("visualLanguage") or {}).get("visualEra"),
            "productionStyle": cinematic.get("productionStyle")
            or (creative.get("visualLanguage") or {}).get("productionStyle"),
            "aspectRatio": aspect,
            "shotIntent": cinematic.get("shotIntent") or "medium",
            "category": cinematic.get("category") or job_params.get("purpose") or "storyboard",
        }

        return {
            "assetId": asset_id,
            "projectId": project_id,
            "prompt": prompt,
            "negativePrompt": negative,
            "referenceAssetIds": [str(r) for r in refs if r],
            "continuitySessionId": continuity_session_id,
            "sceneId": scene_id,
            "spatialMapId": spatial_map_id,
            "spatialMapVersion": spatial_map_version,
            "spatialCameraId": spatial_camera_id,
            "modelFamilyPreference": family,
            "controls": controls,
            "panelId": md.get("panelId") or job_params.get("panelId"),
            "jobId": job_id,
            "provenance": {
                "creativeContextDigest": intent.get("creativeContextDigest") or meta.get("creativeContextDigest"),
                "recommendation": recommendation,
                "spatialSummary": spatial.get("summary"),
                "source": "asset.prompt_meta_json",
            },
        }
