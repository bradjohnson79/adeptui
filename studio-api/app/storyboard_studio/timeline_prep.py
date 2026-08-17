"""Proposal-first storyboard → Timeline prep + confirm apply (no silent clip generation)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Project, Scene, SessionLocal
from ..script_storyboard import ScriptSegmentRow, StoryboardPanelRow, ensure_script_tables
from .contracts import TimelinePrepProposal, TimelinePrepShotProposal
from .documents import get_document, ensure_document


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _proposals_path(project_id: str) -> Path:
    base = Path(settings.data_dir) / "storyboard_studio" / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base / "timeline_proposals.json"


def _read_proposals(project_id: str) -> list[dict[str, Any]]:
    path = _proposals_path(project_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_proposals(project_id: str, items: list[dict[str, Any]]) -> None:
    _proposals_path(project_id).write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_proposal(proposal: TimelinePrepProposal) -> TimelinePrepProposal:
    items = _read_proposals(proposal.projectId)
    payload = proposal.model_dump()
    items = [i for i in items if i.get("id") != proposal.id]
    items.insert(0, payload)
    _write_proposals(proposal.projectId, items[:50])
    return proposal


def _v2_scene_readouts(db: Session, project_id: str) -> dict[str, dict[str, Any]]:
    """Map Script Writer scene element id -> canonical v2 scene readout (CDX-052).

    Only scene headings (the ids panels store in meta.scriptwriterSceneId) are
    indexed; empty documents produce an empty map so callers fall back to the
    legacy script_segments snapshot. Pure read — never writes.
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        from ..scriptwriter.service import project_segments, scene_segment_readout
        from ..scriptwriter.store import list_documents

        for doc in list_documents(db, project_id) or []:
            for seg in project_segments(doc):
                if seg.get("segmentType") == "scene_heading" and seg.get("sceneId"):
                    readout = scene_segment_readout(doc, str(seg["sceneId"]))
                    if readout:
                        out[str(seg["sceneId"])] = readout
    except Exception:
        pass
    return out


def prepare_timeline_from_storyboard(
    project_id: str,
    *,
    document_id: str | None = None,
    panel_ids: list[str] | None = None,
    approved_only: bool = True,
) -> TimelinePrepProposal:
    doc = get_document(project_id, document_id) if document_id else ensure_document(project_id)
    if not doc:
        doc = ensure_document(project_id)
    ensure_script_tables()
    shots: list[TimelinePrepShotProposal] = []
    with SessionLocal() as db:
        q = db.query(StoryboardPanelRow).filter(StoryboardPanelRow.project_id == project_id)
        rows = q.all()
        # CDX-052: canonical v2 scene readouts (typed Script Writer content)
        # keyed by the Script Writer scene element id panels link via
        # meta.scriptwriterSceneId; the legacy script_segments snapshot remains
        # the fallback when no v2 scene is linked.
        v2_by_scene = _v2_scene_readouts(db, project_id)
        by_id = {r.id: r for r in rows}
        order = panel_ids or doc.panelOrder or [r.id for r in rows]
        for pid in order:
            row = by_id.get(pid)
            if not row:
                continue
            if approved_only and (row.approval or "").lower() not in {"approved", "final", "ok"}:
                if any((r.approval or "").lower() in {"approved", "final", "ok"} for r in rows):
                    continue
            try:
                meta = json.loads(row.meta_json or "{}")
            except Exception:
                meta = {}
            dialogue = ""
            scene_id = None
            v2seg = v2_by_scene.get(str(meta.get("scriptwriterSceneId") or ""))
            if v2seg:
                dialogue = v2seg.get("dialogue") or ""
                # sceneId field semantics are unchanged: the project scene id
                # from the legacy link / meta, never the v2 element id.
                if row.segment_id:
                    seg = db.get(ScriptSegmentRow, row.segment_id)
                    if seg and seg.scene_id:
                        scene_id = seg.scene_id
            elif row.segment_id:
                seg = db.get(ScriptSegmentRow, row.segment_id)
                if seg:
                    dialogue = seg.dialogue or ""
                    scene_id = seg.scene_id
            camera = " / ".join(
                x for x in [row.shot_size or "", row.lens or ""] if x
            )
            explicit_dialogue = bool(meta.get("scriptwriterDialogueId"))
            if not explicit_dialogue and v2seg:
                explicit_dialogue = bool(v2seg.get("dialogue"))
            elif not explicit_dialogue and row.segment_id:
                seg = db.get(ScriptSegmentRow, row.segment_id)
                explicit_dialogue = bool(seg and (seg.dialogue or "").strip())
            if not explicit_dialogue:
                dialogue = ""
            shots.append(
                TimelinePrepShotProposal(
                    panelId=row.id,
                    assetId=row.asset_id,
                    label=row.label or f"Panel {row.panel_index + 1}",
                    prompt=row.prompt or "",
                    dialogue=dialogue,
                    cameraNote=camera,
                    durationEst=float(row.duration_est or 3.0),
                    sceneId=scene_id or meta.get("sceneId"),
                    continuitySessionId=meta.get("continuitySessionId") or doc.continuitySessionId,
                    spatialMapId=meta.get("spatialMapId"),
                    spatialMapVersion=meta.get("spatialMapVersion"),
                )
            )

    proposal = TimelinePrepProposal(
        id=str(uuid.uuid4()),
        projectId=project_id,
        documentId=doc.id,
        shots=shots,
        status="draft",
        createdAt=_now(),
    )
    return _save_proposal(proposal)


def get_proposal(project_id: str, proposal_id: str) -> TimelinePrepProposal | None:
    for raw in _read_proposals(project_id):
        if raw.get("id") == proposal_id:
            try:
                return TimelinePrepProposal.model_validate(raw)
            except Exception:
                return None
    return None


def confirm_timeline_proposal(
    project_id: str,
    proposal_id: str,
    *,
    panel_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Apply a reviewable proposal into Director Timeline as Scene rows.
    Proposal-gated — does not generate clips.
    """
    proposal = get_proposal(project_id, proposal_id)
    if not proposal:
        return {"ok": False, "error": "proposal not found"}
    ensure_script_tables()
    created: list[dict[str, Any]] = []
    shots = proposal.shots
    if panel_ids:
        allow = set(panel_ids)
        shots = [s for s in shots if s.panelId in allow]

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            return {"ok": False, "error": "project not found"}
        for shot in shots:
            if not shot.assetId:
                continue
            panel = db.get(StoryboardPanelRow, shot.panelId)
            count = db.query(Scene).filter(Scene.project_id == project_id).count()
            scene = Scene(
                id=str(uuid.uuid4()),
                project_id=project_id,
                index=count,
                name=shot.label or "Storyboard",
                engine=project.engine_default,
                prompt=(shot.prompt or "")[:4000],
                duration_sec=float(shot.durationEst or 3.0),
                start_asset_id=shot.assetId,
                camera_note=(
                    f"storyboard:{shot.panelId}; continuity:{shot.continuitySessionId or ''}; "
                    f"{shot.cameraNote or ''}"
                )[:1000],
            )
            db.add(scene)
            if panel:
                panel.status = "in_director"
                try:
                    meta = json.loads(panel.meta_json or "{}")
                except Exception:
                    meta = {}
                meta["timelineSceneId"] = scene.id
                meta["timelineProposalId"] = proposal_id
                panel.meta_json = json.dumps(meta)
            try:
                from ..asset_graph import add_edge

                nested = db.begin_nested()
                try:
                    add_edge(
                        db,
                        shot.assetId,
                        scene.id,
                        "used_in_director",
                        {
                            "panel_id": shot.panelId,
                            "proposal_id": proposal_id,
                            "continuitySessionId": shot.continuitySessionId,
                            "spatialMapId": shot.spatialMapId,
                            "spatialMapVersion": shot.spatialMapVersion,
                        },
                    )
                    nested.commit()
                except Exception:
                    nested.rollback()
            except Exception:
                pass
            created.append(
                {
                    "sceneId": scene.id,
                    "panelId": shot.panelId,
                    "assetId": shot.assetId,
                    "durationEst": shot.durationEst,
                    "cameraNote": shot.cameraNote,
                    "dialogue": shot.dialogue,
                    "continuitySessionId": shot.continuitySessionId,
                    "spatialMapId": shot.spatialMapId,
                    "spatialMapVersion": shot.spatialMapVersion,
                    "label": shot.label,
                    "prompt": shot.prompt,
                }
            )
        project.updated_at = datetime.utcnow()
        db.commit()

    data = proposal.model_dump()
    data["status"] = "applied"
    data["appliedAt"] = _now()
    data["appliedSceneIds"] = [c["sceneId"] for c in created]
    data["timelinePayload"] = created
    items = _read_proposals(project_id)
    items = [i for i in items if i.get("id") != proposal_id]
    items.insert(0, data)
    _write_proposals(project_id, items[:50])

    return {
        "ok": True,
        "proposal": data,
        "timelinePayload": created,
        "createdSceneIds": [c["sceneId"] for c in created],
        "note": "Proposal applied to Director Timeline scenes — no clips generated.",
    }
