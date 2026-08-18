"""Production State Snapshot - compact read-through of authoritative stores.

Mission Part 1: Co-Director receives the relevant current production state
automatically (scene, Spatial Map saved/dirty/version, ERS, cameras,
candidates, library, timeline, batches, jobs, recent events) without
dumping media. Composes on demand; never persists; every read is
best-effort against the authoritative store (Build Law #5 - reuse, no
duplicate stores). Bounded output for prompt injection (Part 55).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

_CANDIDATE_LIMIT = 12
_EVENT_LIMIT = 10
_JOB_LIMIT = 8


def _json_ok(raw: Any) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _active_scene(db: Session, project_id: str, scene_id: Optional[str]) -> Optional[dict[str, Any]]:
    """Resolve the active scene: explicit scene_id, else the first scene."""
    from ...db import Scene

    scene = None
    if scene_id:
        scene = db.get(Scene, scene_id)
        if scene is not None and scene.project_id != project_id:
            scene = None
    if scene is None:
        scene = (
            db.query(Scene)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.index.asc())
            .first()
        )
    if scene is None:
        return None
    return {
        "id": scene.id,
        "name": scene.name,
        "index": scene.index,
    }


def _spatial_map_state(db: Session, project_id: str, scene_id: Optional[str]) -> dict[str, Any]:
    """Saved/current version + dirty state + cameras from the authoritative spatial store."""
    try:
        from ...spatial_map.service import list_documents

        docs = list_documents(db, project_id) or []
        if not docs:
            return {"hasMap": False}
        payloads: list[dict[str, Any]] = []
        for doc in docs:
            if hasattr(doc, "model_dump"):
                try:
                    payloads.append(doc.model_dump())
                except Exception:
                    payloads.append(dict(doc))
            elif isinstance(doc, dict):
                payloads.append(doc)
            else:
                raw = _json_ok(getattr(doc, "document_json", None))
                if raw is not None:
                    payloads.append(raw)
        if not payloads:
            return {"hasMap": False}
        selected = None
        for payload in payloads:
            doc_scene = payload.get("sceneId")
            if scene_id and doc_scene == scene_id:
                selected = payload
                break
        if selected is None:
            payloads.sort(key=lambda d: str(d.get("updatedAt") or ""), reverse=True)
            selected = next((d for d in payloads if d.get("sceneId")), payloads[0])
        version = str(selected.get("version") or "1")
        saved_version = str(selected.get("savedVersion") or "") or None
        cameras = selected.get("cameras") or []
        return {
            "hasMap": True,
            "documentId": selected.get("id"),
            "savedVersion": saved_version,
            "currentVersion": version,
            "dirty": bool(saved_version and saved_version != version),
            "cameraCount": len(cameras),
            "cameras": [
                {
                    "id": str(c.get("id") or ""),
                    "label": str(c.get("label") or "Camera"),
                    "hero": bool(c.get("hero")),
                }
                for c in cameras[:10]
            ],
        }
    except Exception:
        return {"hasMap": False}


def _ers_state(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Newest Environment Reference Sheet from the JSON store."""
    try:
        from ...environment_reference_sheet.store import list_sheets

        sheets = list_sheets(project_id)
        if not sheets:
            return None
        sheet = sheets[0]
        directions = getattr(sheet, "directions", None) or []
        return {
            "sheetId": getattr(sheet, "sheetId", "") or "",
            "name": getattr(sheet, "name", "") or "Environment Reference Sheet",
            "status": getattr(sheet, "status", "") or "unknown",
            "updatedAt": getattr(sheet, "updatedAt", "") or "",
            "directionCount": len(directions) if isinstance(directions, list) else 0,
            "hasReference": bool(getattr(sheet, "ers_composite_asset_id", None) or getattr(sheet, "ersCompositeAssetId", None)),
        }
    except Exception:
        return None


def _parse_candidate_tag(tag: str) -> dict[str, str]:
    """Parse candidate tags like scene_creator_mini_8_C2_B into camera/variant."""
    tag = tag or ""
    camera = ""
    variant = ""
    m = re.search(r"_[Cc](\d+)_([A-Za-z])", tag)
    if m:
        camera = "C" + m.group(1)
        variant = m.group(2).upper()
    return {"camera": camera, "variant": variant}


def _candidates(db: Session, project_id: str, scene_id: Optional[str]) -> list[dict[str, Any]]:
    """Recent candidate assets (scene creator / multi-shot / imagegen outputs).

    Candidates are authoritative assets: scene_creator_mini_* tags carry the
    C<camera>_<variant> naming from the certification scenario; multi_shot
    candidates live in multi_shot_candidates; generic imagegen outputs with
    candidate lineage are included when tagged. Bounded to _CANDIDATE_LIMIT.
    """
    try:
        from ...db import Asset

        rows = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.created_at.desc())
            .limit(80)
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            tag = str(row.tag or "")
            if not any(k in tag for k in ("scene_creator", "multi_shot", "imagegen", "shot", "ers")):
                continue
            parsed = _parse_candidate_tag(tag)
            if not parsed["camera"] and "multi_shot" not in tag and "imagegen" not in tag:
                continue
            out.append({
                "assetId": row.id,
                "tag": tag,
                "kind": row.kind,
                "camera": parsed["camera"],
                "variant": parsed["variant"],
                "approved": bool(row.production_approval),
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            })
            if len(out) >= _CANDIDATE_LIMIT:
                break
        return out
    except Exception:
        return []


def _timeline_state(db: Session, project_id: str, scene_id: Optional[str]) -> dict[str, Any]:
    """Timeline master (w46) - batches, clips, prompt segments, revision.

    Reads both representations: the w46 master batch blocks AND the legacy
    Visual/Prompt tracks (directorTimeline) that the Co-Director timeline
    tools edit, so CD can answer "what is on Timeline right now" (Part 43).
    """
    if not scene_id:
        scene = _active_scene(db, project_id, None)
        scene_id = scene["id"] if scene else None
    if not scene_id:
        return {"hasTimeline": False}
    try:
        from ...director_timeline_w46.service import load_timeline_bundle

        bundle = load_timeline_bundle(db, project_id, scene_id)
        if not bundle.get("ok"):
            return {"hasTimeline": False}
        master = bundle.get("master")
        if hasattr(master, "model_dump"):
            master = master.model_dump()
        master = master or {}
        batches = master.get("batchBlocks") or []
        workspace = bundle.get("workspace") or {}
        if hasattr(workspace, "model_dump"):
            workspace = workspace.model_dump()
        dtl = bundle.get("directorTimeline")
        if hasattr(dtl, "model_dump"):
            dtl = dtl.model_dump()
        dtl = dtl or {}
        clips = dtl.get("image_clips") or []
        segments = dtl.get("prompt_segments") or []
        return {
            "hasTimeline": True,
            "revision": int(workspace.get("timelineRevision") or 1),
            "batchCount": len(batches),
            "batches": [
                {
                    "id": str(b.get("id") or ""),
                    "label": str(b.get("label") or "Batch"),
                    "order": int(b.get("order") or 0),
                    "status": str(b.get("status") or "Draft"),
                    "generatorId": b.get("generatorId") or None,
                    "plannedDuration": float((b.get("duration") or {}).get("plannedDuration") or 0.0),
                    "approved": bool(b.get("approvedClip")),
                    "promptSegmentCount": len(b.get("promptSegments") or []),
                    "visualClipCount": len(b.get("visualClips") or []),
                }
                for b in batches[:12]
            ],
            "clips": [
                {
                    "id": str(c.get("id") or ""),
                    "kind": "image",
                    "start": float(c.get("start") or 0.0),
                    "length": float(c.get("length") or 0.0),
                    "label": str(c.get("label") or "Image clip"),
                    "assetId": c.get("asset_id"),
                }
                for c in clips[:20]
            ],
            "promptSegments": [
                {
                    "id": str(seg.get("id") or ""),
                    "start": float(seg.get("start") or 0.0),
                    "length": float(seg.get("length") or 0.0),
                    "textPreview": str(seg.get("text") or "")[:160],
                    "userDirection": seg.get("user_direction"),
                    "productionPrompt": seg.get("production_prompt"),
                    "dialogue": seg.get("dialogue"),
                }
                for seg in segments[:20]
            ],
        }
    except Exception:
        return {"hasTimeline": False}


def _jobs_state(db: Session, project_id: str) -> dict[str, Any]:
    """Active + recently completed studio jobs (bounded)."""
    try:
        from ...db import Job

        rows = (
            db.query(Job)
            .filter(Job.project_id == project_id)
            .order_by(Job.created_at.desc())
            .limit(20)
            .all()
        )
        active: list[dict[str, Any]] = []
        recent: list[dict[str, Any]] = []
        for row in rows:
            item = {
                "id": row.id,
                "kind": row.kind,
                "status": row.status,
            }
            if row.status in ("queued", "running", "processing", "pending"):
                if len(active) < _JOB_LIMIT:
                    active.append(item)
            else:
                if len(recent) < _JOB_LIMIT:
                    recent.append(item)
        return {"active": active, "recentCompleted": recent}
    except Exception:
        return {"active": [], "recentCompleted": []}


def build_production_snapshot(
    db: Session,
    project_id: str,
    scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Compose the compact production state snapshot (mission Part 1).

    All reads are best-effort; a failing subsystem degrades to its empty
    shape, never raising (a broken pillar must not break the chat turn).
    """
    from ...db import Project
    from ...production_events import recent_production_events

    project = db.get(Project, project_id)
    scene = _active_scene(db, project_id, scene_id)
    active_scene_id = scene["id"] if scene else scene_id
    snapshot: dict[str, Any] = {
        "project": {"id": project_id, "name": project.name if project else ""},
        "scene": scene,
        "spatialMap": _spatial_map_state(db, project_id, active_scene_id),
        "ers": _ers_state(db, project_id),
        "candidates": _candidates(db, project_id, active_scene_id),
        "timeline": _timeline_state(db, project_id, active_scene_id),
        "jobs": _jobs_state(db, project_id),
        "events": recent_production_events(db, project_id, scene_id=active_scene_id, limit=_EVENT_LIMIT),
    }
    return snapshot


def _fmt(v: Any) -> str:
    return "" if v is None else str(v)


def render_production_snapshot_block(
    db: Session,
    project_id: str,
    scene_id: Optional[str] = None,
    *,
    max_chars: int = 2400,
) -> str:
    """Render the snapshot as a bounded prompt block (empty when no project).

    The block is deliberately compact: it is the automatic production
    awareness feed for the model, not a dump (mission Parts 1, 55).
    """
    snap = build_production_snapshot(db, project_id, scene_id)
    out: list[str] = ["PROJECT PRODUCTION STATE"]
    scene = snap.get("scene") or {}
    if scene:
        out.append("- Scene: {name} (index {index})".format(**scene))
    sm = snap.get("spatialMap") or {}
    if sm.get("hasMap"):
        dirty = " (unsaved changes)" if sm.get("dirty") else ""
        out.append("- Spatial Map v{cur}, saved v{saved}{dirty}".format(cur=_fmt(sm.get("currentVersion")), saved=_fmt(sm.get("savedVersion")), dirty=dirty))
        cam_labels = ", ".join(f"{c['label']} ({c['id'][:8]})" for c in (sm.get("cameras") or [])[:6])
        out.append(f"- Cameras: {sm.get('cameraCount', 0)} - {cam_labels}")
    ers = snap.get("ers")
    if ers:
        out.append(f"- ERS: {_fmt(ers.get('name'))} [{ers.get('status')}] directions={ers.get('directionCount', 0)}")
    cands = snap.get("candidates") or []
    if cands:
        labels = [f"{c['tag']}({'approved' if c.get('approved') else 'pending'})" for c in cands]
        out.append("- Candidates: " + ", ".join(labels))
    tl = snap.get("timeline") or {}
    if tl.get("hasTimeline"):
        batch_labels = ", ".join(f"{b['label']}[{b['status']}]" for b in (tl.get("batches") or [])[:6])
        out.append(f"- Timeline revision {tl.get('revision')}, batches: {batch_labels}")
        clips = tl.get("clips") or []
        if clips:
            clip_labels = ", ".join(f"{c['label']} {round(c['start'], 2)}-{round(c['start'] + c['length'], 2)}s" for c in clips[:6])
            out.append(f"- Visual clips: {clip_labels}")
    jobs = snap.get("jobs") or {}
    act = jobs.get("active") or []
    if act:
        out.append("- Active jobs: " + ", ".join(f"{j['kind']}:{j['status']}" for j in act))
    events = snap.get("events") or []
    for ev in events[-5:]:
        out.append(f"- {ev.get('eventType')}: {str(ev.get('summary') or '')[:120]}")
    text = chr(10).join(out)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text