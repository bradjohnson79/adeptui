"""Enqueue ImageEditIntent jobs (M42 W4)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job
from .edit_compile import compile_edit_request
from .history import append_history


def _enqueue_compiled(
    db: Session,
    *,
    project_id: str,
    compiled: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    intent = compiled["imageIntent"]
    edit_intent = compiled["imageEditIntent"]
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
        "edit": True,
        "edit_op": (intent.get("metadata") or {}).get("edit_op") or "edit",
        "imageIntent": intent,
        "imageEditIntent": edit_intent,
        "imageRuntime": pinned,
        "recommendation": compiled.get("recommendation"),
        "promptIntel": compiled.get("promptIntel"),
        "compatibility": {"legacyInputUsed": False, "normalizedBy": "m42-wave4-image-edit"},
        "allow_draft_cert_harness": False,
        "refs": body.get("refs") or [],
        "masks": edit_intent.get("masks") or [],
        "tag": body.get("tag") or "imageedit",
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=body.get("sceneId") or (edit_intent.get("continuity") or {}).get("sceneId"),
        kind="imagegen_edit",
        status="queued",
        progress=0.0,
        stage="Queued",
        message=f"ImageEdit {pinned.get('workflowKey')} ({edit_intent.get('operation')})",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    try:
        from ..codirector.executive.imagegen_adapter import schedule_job_queue_enqueue

        schedule_job_queue_enqueue(job.id)
    except Exception:
        pass
    append_history(
        project_id,
        {
            "jobId": job.id,
            "intentId": edit_intent.get("intentId"),
            "imageEditIntentId": edit_intent.get("intentId"),
            "operation": edit_intent.get("operation"),
            "prompt": intent.get("prompt"),
            "workflowKey": pinned.get("workflowKey"),
            "modelFamily": intent.get("enginePreference"),
            "seed": intent.get("seed"),
            "recommendation": compiled.get("recommendation"),
            "promptIntel": compiled.get("promptIntel"),
            "referenceIds": intent.get("referenceIds"),
            "sourceAssetIds": edit_intent.get("sourceAssetIds"),
            "purpose": intent.get("purpose"),
            "kind": "edit",
        },
    )
    return {
        "jobId": job.id,
        "workflowKey": pinned.get("workflowKey"),
        "kind": "imagegen_edit",
        "operation": edit_intent.get("operation"),
    }


def enqueue_edit(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Compile + enqueue a single edit job."""
    compiled = compile_edit_request(project_id, body)
    job_info = _enqueue_compiled(db, project_id=project_id, compiled=compiled, body=body)
    return {
        "ok": True,
        "queued": True,
        **job_info,
        "imageEditIntent": compiled["imageEditIntent"],
        "imageIntent": compiled["imageIntent"],
        "imageRuntime": compiled["imageRuntime"],
        "recommendation": compiled.get("recommendation"),
        "promptIntel": compiled.get("promptIntel"),
        "disclosure": "Enqueued via ImageEditIntent → ImageIntent → certified Workflow Resolver.",
    }


def enqueue_edit_batch(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """
    Clone edit intent across targetAssetIds.
    body: { templateIntentId | ImageEditIntent fields, targetAssetIds[], maxBatch? }
    """
    targets = list(body.get("targetAssetIds") or [])
    max_batch = max(1, min(int(body.get("maxBatch") or 32), 32))
    if not targets:
        raise ValueError("targetAssetIds required for batch edit")
    targets = targets[:max_batch]

    template = dict(body)
    jobs: list[dict[str, Any]] = []
    compiled_first = None

    for i, asset_id in enumerate(targets):
        b = dict(template)
        b["sourceAssetIds"] = [asset_id]
        b["sourceAssetId"] = asset_id
        b["batchIndex"] = i
        b["batchParentId"] = body.get("batchParentId") or body.get("templateIntentId")
        if b.get("seed") is not None:
            b["seed"] = int(b["seed"]) + i
        compiled = compile_edit_request(project_id, b)
        if compiled_first is None:
            compiled_first = compiled
        job_info = _enqueue_compiled(db, project_id=project_id, compiled=compiled, body=b)
        jobs.append(job_info)

    return {
        "ok": True,
        "queued": True,
        "batchCount": len(jobs),
        "jobs": jobs,
        "jobId": jobs[0]["jobId"] if jobs else None,
        "imageEditIntent": (compiled_first or {}).get("imageEditIntent"),
        "imageIntent": (compiled_first or {}).get("imageIntent"),
        "imageRuntime": (compiled_first or {}).get("imageRuntime"),
        "recommendation": (compiled_first or {}).get("recommendation"),
        "disclosure": f"Batch edit: {len(jobs)} jobs enqueued with shared workflow contract pattern.",
    }
