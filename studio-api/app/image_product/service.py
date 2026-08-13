"""Enqueue compiled ImageIntent through generation_tools / QueueWorker (M42 W3)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job
from .compile import compile_image_request
from .history import append_history


def generate_images(
    db: Session,
    *,
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Compile + enqueue one or more image jobs (batch via body.batchCount)."""
    from fastapi import HTTPException

    # Production Dock → resolver → family injection + early degraded-mode block.
    try:
        from ..production_control.runtime_map import apply_image_dock_preference

        body = apply_image_dock_preference(project_id, dict(body or {}))
    except HTTPException:
        raise
    except Exception:
        body = dict(body or {})

    batch = max(1, min(int(body.get("batchCount") or body.get("batch") or 1), 8))
    jobs: list[dict[str, Any]] = []
    compiled_first = None
    dock_meta = body.get("productionDock") if isinstance(body.get("productionDock"), dict) else None

    for i in range(batch):
        b = dict(body)
        b["batchIndex"] = i
        if batch > 1 and b.get("seed") is not None:
            b["seed"] = int(b["seed"]) + i
        compiled = compile_image_request(project_id, b)
        if compiled_first is None:
            compiled_first = compiled
        intent = compiled["imageIntent"]
        pinned = compiled["imageRuntime"]
        params = {
            "prompt": intent.get("prompt"),
            "negative": intent.get("negativePrompt"),
            "model": intent.get("enginePreference") or "zimage",
            "width": intent.get("width"),
            "height": intent.get("height"),
            "seed": intent.get("seed"),
            "aspect": (intent.get("metadata") or {}).get("aspect"),
            "source_asset_id": intent.get("sourceAssetId"),
            "edit": intent.get("operation") in {"image.edit", "image.reference"},
            "edit_op": (intent.get("metadata") or {}).get("edit_op") or "edit",
            "imageIntent": intent,
            "imageRuntime": pinned,
            "recommendation": compiled.get("recommendation"),
            "promptIntel": compiled.get("promptIntel"),
            "compatibility": {"legacyInputUsed": False, "normalizedBy": "m42-wave3-image-product"},
            "allow_draft_cert_harness": bool(compiled.get("allowDraft")),
            "panel_id": (intent.get("metadata") or {}).get("panelId"),
            "spatialMapId": (intent.get("metadata") or {}).get("spatialMapId"),
            "spatialMapVersion": (intent.get("metadata") or {}).get("spatialMapVersion"),
            "spatialCameraId": (intent.get("metadata") or {}).get("spatialCameraId"),
            "spatialReferenceBundle": body.get("spatialReferenceBundle"),
            "refs": body.get("refs") or [],
            "cloudPaid": intent.get("providerPreference") == "cloud",
            "tag": body.get("tag") or "imagegen",
            # Reference-fidelity strength (img2img / ref_edit). Lower denoise =
            # more of the reference latent preserved. Character Creator passes a
            # fidelity-first value when a Character Reference is attached.
            "denoise": body.get("denoise"),
            "productionDock": dock_meta,
            "preferenceProvenance": (dock_meta or {}).get("provenance"),
        }
        kind = "imagegen_edit" if params["edit"] else "imagegen"
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=body.get("sceneId"),
            kind=kind,
            status="queued",
            progress=0.0,
            stage="Queued",
            message=f"ImageProduct {pinned.get('workflowKey')}",
            params_json=json.dumps(params),
        )
        db.add(job)
        db.commit()
        try:
            from ..codirector.executive.imagegen_adapter import schedule_job_queue_enqueue

            schedule_job_queue_enqueue(job.id)
        except Exception:
            pass
        jobs.append({"jobId": job.id, "workflowKey": pinned.get("workflowKey"), "kind": kind})
        append_history(
            project_id,
            {
                "jobId": job.id,
                "intentId": intent.get("intentId"),
                "prompt": intent.get("prompt"),
                "workflowKey": pinned.get("workflowKey"),
                "modelFamily": intent.get("enginePreference"),
                "seed": intent.get("seed"),
                "recommendation": compiled.get("recommendation"),
                "promptIntel": compiled.get("promptIntel"),
                "referenceIds": intent.get("referenceIds"),
                "purpose": intent.get("purpose"),
            },
        )

    return {
        "ok": True,
        "queued": True,
        "jobId": jobs[0]["jobId"] if jobs else None,
        "jobs": jobs,
        "recommendation": (compiled_first or {}).get("recommendation"),
        "promptIntel": (compiled_first or {}).get("promptIntel"),
        "imageRuntime": (compiled_first or {}).get("imageRuntime"),
        "imageIntent": (compiled_first or {}).get("imageIntent"),
        "productionDock": dock_meta,
        "disclosure": "Enqueued via ImageIntent → certified Workflow Resolver. No product graph build.",
    }
