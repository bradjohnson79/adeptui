"""Shared storyboard generate enqueue helpers (used by HTTP routes + Production Executive).

In-process callers use these with a Session — never self-HTTP.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from .db import Job, Project
from .script_storyboard import (
    ScriptSegmentRow,
    StoryboardPanelRow,
    get_or_create_script_doc,
    storyboard_style_prompt,
)


def ensure_scene_segment(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    prompt: str | None = None,
) -> ScriptSegmentRow:
    """Find or create a script segment bound to scene_id for executive closed-loops."""
    existing = (
        db.query(ScriptSegmentRow)
        .filter(
            ScriptSegmentRow.project_id == project_id,
            ScriptSegmentRow.scene_id == scene_id,
        )
        .order_by(ScriptSegmentRow.index.asc())
        .first()
    )
    if existing:
        return existing

    doc = get_or_create_script_doc(db, project_id)
    count = (
        db.query(ScriptSegmentRow)
        .filter(ScriptSegmentRow.project_id == project_id, ScriptSegmentRow.doc_id == doc.id)
        .count()
    )
    seg = ScriptSegmentRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        doc_id=doc.id,
        scene_id=scene_id,
        index=count,
        segment_number=count + 1,
        segment_type="action",
        action=prompt or f"Executive closed-loop storyboard for scene {scene_id}",
        text=prompt or "",
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def prepare_storyboard_generate(
    db: Session,
    project_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create/update panel + ImageGen Job row (queued). Does not call job_queue.enqueue.

    Returns dict with job_id, panel_id, segment_id, status, params.
    """
    body = dict(body or {})
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")

    panel_id = body.get("panel_id") or body.get("panelId")
    segment_id = body.get("segment_id") or body.get("segmentId")
    scene_id = body.get("scene_id") or body.get("sceneId")

    panel = db.get(StoryboardPanelRow, panel_id) if panel_id else None
    if not panel and not segment_id and scene_id:
        seg = ensure_scene_segment(
            db, project_id, scene_id, prompt=body.get("prompt")
        )
        segment_id = seg.id

    if not panel and segment_id:
        doc = get_or_create_script_doc(db, project_id)
        count = (
            db.query(StoryboardPanelRow)
            .filter(StoryboardPanelRow.segment_id == segment_id)
            .count()
        )
        panel = StoryboardPanelRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=doc.id,
            segment_id=segment_id,
            panel_index=count,
            label=body.get("label") or f"Panel {chr(65 + count)}",
            style=body.get("style") or "Pencil storyboard",
            status="generating",
        )
        db.add(panel)
        db.commit()
        db.refresh(panel)


    if not panel:
        raise ValueError("panel_id or segment_id (or sceneId) required")

    seg = db.get(ScriptSegmentRow, panel.segment_id)
    body_text = ""
    if seg:
        body_text = " ".join(
            x
            for x in [
                seg.action,
                seg.dialogue or seg.text,
                seg.speaker and f"Speaker: {seg.speaker}",
            ]
            if x
        )
    style = body.get("style") or panel.style or "Pencil storyboard"
    prompt = storyboard_style_prompt(style, body.get("prompt") or panel.prompt or body_text)
    panel.status = "generating"
    panel.style = style
    panel.prompt = prompt
    db.commit()

    from .image_product.service import generate_images

    result = generate_images(
        db,
        project_id=project_id,
        body={
            "prompt": prompt,
            "negative": project.negative_prompt,
            "purpose": "storyboard",
            "operation": "image.storyboard_frame",
            "presetId": body.get("presetId") or "builtin-storyboard",
            "modelFamilyPreference": body.get("modelFamilyPreference") or body.get("model") or "zimage",
            "width": int(body.get("width") or 1280),
            "height": int(body.get("height") or 720),
            "aspectRatio": body.get("aspectRatio") or "16:9",
            "tag": "storyboard",
            "labels": ["storyboard"],
            "panelId": panel.id,
            "segment_id": panel.segment_id,
            "sceneId": (seg.scene_id if seg else scene_id),
            "shotId": body.get("shotId"),
            "cameraId": body.get("cameraId"),
            "continuityId": body.get("continuityId"),
            "style": {"label": style} if isinstance(style, str) else (style or {}),
        },
    )
    job_id = result.get("jobId")
    job = db.get(Job, job_id) if job_id else None
    params = {
        "prompt": prompt,
        "panel_id": panel.id,
        "segment_id": panel.segment_id,
        "imageRuntime": result.get("imageRuntime"),
        "recommendation": result.get("recommendation"),
    }
    return {
        "job_id": job_id,
        "panel_id": panel.id,
        "segment_id": panel.segment_id,
        "status": "generating",
        "params": params,
        "job": job,
        "imageProduct": True,
    }


def enqueue_imagegen_job(
    db: Session,
    project_id: str,
    body: dict[str, Any] | None = None,
    *,
    scene_id: Optional[str] = None,
) -> Job:
    """Create a queued ImageGen Job via Image Product compiler (M42 W3)."""
    from .image_product.service import generate_images

    body = dict(body or {})
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    payload = {
        **body,
        "sceneId": scene_id or body.get("sceneId") or body.get("scene_id"),
        "modelFamilyPreference": body.get("modelFamilyPreference") or body.get("model") or "zimage",
    }
    if str(body.get("purpose") or "") == "environment_reference_sheet":
        payload["operation"] = "image.generate"
        payload.pop("edit", None)
        payload.pop("source_asset_id", None)
        payload.pop("sourceAssetId", None)
    elif body.get("edit") or body.get("source_asset_id"):
        current_op = str(body.get("operation") or payload.get("operation") or "").strip().lower()
        if current_op not in {"image.inpaint", "image.edit", "image.reference", "native_inpaint"}:
            payload["operation"] = "image.edit"
        payload.setdefault("sourceAssetId", body.get("source_asset_id") or body.get("sourceAssetId"))
    result = generate_images(db, project_id=project_id, body=payload)
    job = db.get(Job, result.get("jobId"))
    if not job:
        raise RuntimeError("Image Product enqueue failed to create job")
    return job
