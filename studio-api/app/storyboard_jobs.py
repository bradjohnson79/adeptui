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

    params = {
        "prompt": prompt,
        "negative": project.negative_prompt,
        "style": style,
        "model": body.get("model") or "auto",
        "width": int(body.get("width") or 1280),
        "height": int(body.get("height") or 720),
        "tag": "storyboard",
        "labels": ["storyboard"],
        "panel_id": panel.id,
        "segment_id": panel.segment_id,
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=(seg.scene_id if seg else scene_id),
        kind="imagegen",
        status="queued",
        message="Queued storyboard ImageGen",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "panel_id": panel.id,
        "segment_id": panel.segment_id,
        "status": "generating",
        "params": params,
    }


def enqueue_imagegen_job(
    db: Session,
    project_id: str,
    body: dict[str, Any] | None = None,
    *,
    scene_id: Optional[str] = None,
) -> Job:
    """Create a queued ImageGen Job row. Does not call job_queue.enqueue."""
    body = dict(body or {})
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    edit = bool(body.get("edit"))
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        kind="imagegen_edit" if edit else "imagegen",
        status="queued",
        message="Queued ImageGen" + (" edit" if edit else ""),
        params_json=json.dumps(body),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
