"""Add / replace storyboard panel images (Undo-friendly)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from ..db import SessionLocal
from ..script_storyboard import (
    ScriptSegmentRow,
    StoryboardPanelRow,
    ensure_script_tables,
    get_or_create_script_doc,
)
from .documents import append_panel, ensure_document, next_free_slot


def _meta(row: StoryboardPanelRow) -> dict[str, Any]:
    try:
        data = json.loads(row.meta_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_scriptwriter_scene_id(project_id: str, scene_id: str | None) -> str | None:
    if not scene_id:
        return None
    try:
        from ..scriptwriter import store as sw_store

        db = SessionLocal()
        try:
            docs = sw_store.list_documents(db, project_id) or []
        finally:
            db.close()
        for doc in docs:
            sync = getattr(doc, "sceneSync", None) or getattr(doc, "scene_sync", None) or {}
            if isinstance(sync, str):
                try:
                    sync = json.loads(sync)
                except Exception:
                    sync = {}
            if not isinstance(sync, dict):
                continue
            for key, val in sync.items():
                if key == scene_id:
                    return str(key)
                if isinstance(val, dict) and (
                    val.get("sceneId") == scene_id or val.get("productionSceneId") == scene_id
                ):
                    return str(key)
                if val == scene_id:
                    return str(key)
    except Exception:
        pass
    return scene_id


def add_image_to_next_panel(
    project_id: str,
    *,
    asset_id: str,
    prompt: str = "",
    label: str = "",
    lens: str = "",
    shot_size: str = "",
    continuity_session_id: str | None = None,
    spatial_map_id: str | None = None,
    spatial_map_version: str | None = None,
    scene_id: str | None = None,
    document_id: str | None = None,
    scriptwriter_scene_id: str | None = None,
) -> dict[str, Any]:
    ensure_script_tables()
    doc_layout = ensure_document(project_id)
    target_doc_id = document_id or doc_layout.id
    slot = next_free_slot(project_id, target_doc_id)
    sw_scene = scriptwriter_scene_id or _resolve_scriptwriter_scene_id(project_id, scene_id)

    with SessionLocal() as db:
        script_doc = get_or_create_script_doc(db, project_id)
        segment = (
            db.query(ScriptSegmentRow)
            .filter(ScriptSegmentRow.project_id == project_id)
            .order_by(ScriptSegmentRow.index.asc())
            .first()
        )
        if not segment:
            segment = ScriptSegmentRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                doc_id=script_doc.id,
                scene_id=scene_id,
                index=0,
                segment_number=1,
                segment_type="action",
                text=prompt or "Storyboard beat",
                action=prompt or "Storyboard beat",
            )
            db.add(segment)
            db.flush()
        elif scene_id and not segment.scene_id:
            segment.scene_id = scene_id

        count = (
            db.query(StoryboardPanelRow)
            .filter(StoryboardPanelRow.segment_id == segment.id)
            .count()
        )
        meta = {
            "continuitySessionId": continuity_session_id,
            "spatialMapId": spatial_map_id,
            "spatialMapVersion": spatial_map_version,
            "fromCinematicImageStudio": True,
            "sceneId": scene_id,
            "scriptwriterSceneId": sw_scene,
        }
        panel = StoryboardPanelRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=script_doc.id,
            segment_id=segment.id,
            panel_index=count,
            label=label or f"Panel {chr(65 + (count % 26))}",
            asset_id=asset_id,
            lens=lens or "",
            shot_size=shot_size or "",
            prompt=prompt or "",
            status="complete",
            approval="draft",
            script_sync_status="ok" if (scene_id or sw_scene) else "ok",
            meta_json=json.dumps(meta),
        )
        db.add(panel)
        db.commit()
        db.refresh(panel)
        panel_id = panel.id

    layout = append_panel(project_id, target_doc_id, panel_id)
    return {
        "panelId": panel_id,
        "documentId": layout.id if layout else target_doc_id,
        "slot": slot,
        "assetId": asset_id,
        "scriptwriterSceneId": sw_scene,
        "undo": {"clearAsset": True, "panelId": panel_id},
    }


def replace_panel_image(
    project_id: str,
    *,
    panel_id: str,
    asset_id: str,
    prompt: str = "",
    label: str = "",
    lens: str = "",
    shot_size: str = "",
    continuity_session_id: str | None = None,
    spatial_map_id: str | None = None,
    spatial_map_version: str | None = None,
    scene_id: str | None = None,
    scriptwriter_scene_id: str | None = None,
) -> dict[str, Any]:
    ensure_script_tables()
    sw_scene = scriptwriter_scene_id or _resolve_scriptwriter_scene_id(project_id, scene_id)
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        meta = _meta(row)
        previous = {
            "assetId": row.asset_id,
            "prompt": row.prompt,
            "label": row.label,
            "lens": row.lens,
            "shotSize": row.shot_size,
            "status": row.status,
            "continuitySessionId": meta.get("continuitySessionId"),
            "spatialMapId": meta.get("spatialMapId"),
            "spatialMapVersion": meta.get("spatialMapVersion"),
        }
        meta["previousAsset"] = previous
        meta["continuitySessionId"] = continuity_session_id or meta.get("continuitySessionId")
        meta["spatialMapId"] = spatial_map_id or meta.get("spatialMapId")
        meta["spatialMapVersion"] = spatial_map_version or meta.get("spatialMapVersion")
        if scene_id:
            meta["sceneId"] = scene_id
        if sw_scene:
            meta["scriptwriterSceneId"] = sw_scene
        meta["fromCinematicImageStudio"] = True
        row.asset_id = asset_id
        if prompt:
            row.prompt = prompt
        if label:
            row.label = label
        if lens:
            row.lens = lens
        if shot_size:
            row.shot_size = shot_size
        row.status = "complete"
        row.script_sync_status = "ok"
        row.meta_json = json.dumps(meta)
        row.updated_at = datetime.utcnow()
        db.commit()
    return {
        "ok": True,
        "panelId": panel_id,
        "assetId": asset_id,
        "scriptwriterSceneId": sw_scene,
        "undo": {"restorePrevious": True, "panelId": panel_id, "previous": previous},
    }


def undo_replace_panel(project_id: str, panel_id: str) -> dict[str, Any]:
    ensure_script_tables()
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        meta = _meta(row)
        previous = meta.get("previousAsset")
        if not isinstance(previous, dict):
            # Fall back to clear (undo add semantics)
            row.asset_id = None
            row.status = "missing"
            row.updated_at = datetime.utcnow()
            db.commit()
            return {"ok": True, "panelId": panel_id, "mode": "cleared"}
        row.asset_id = previous.get("assetId")
        row.prompt = previous.get("prompt") or row.prompt
        row.label = previous.get("label") or row.label
        row.lens = previous.get("lens") or row.lens
        row.shot_size = previous.get("shotSize") or row.shot_size
        row.status = previous.get("status") or ("complete" if row.asset_id else "missing")
        meta.pop("previousAsset", None)
        if previous.get("continuitySessionId") is not None:
            meta["continuitySessionId"] = previous.get("continuitySessionId")
        if previous.get("spatialMapId") is not None:
            meta["spatialMapId"] = previous.get("spatialMapId")
        if previous.get("spatialMapVersion") is not None:
            meta["spatialMapVersion"] = previous.get("spatialMapVersion")
        row.meta_json = json.dumps(meta)
        row.updated_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "panelId": panel_id, "mode": "restored", "assetId": previous.get("assetId")}


def undo_add_image(project_id: str, panel_id: str) -> dict[str, Any]:
    """Prefer restore-previous when replace undo available; else clear asset."""
    ensure_script_tables()
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        meta = _meta(row)
        if isinstance(meta.get("previousAsset"), dict):
            return undo_replace_panel(project_id, panel_id)
        row.asset_id = None
        row.status = "missing"
        row.updated_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "panelId": panel_id, "mode": "cleared"}


def create_empty_panel(project_id: str, *, document_id: str | None = None, label: str = "") -> dict[str, Any]:
    """Create an empty production slot (no Library asset)."""
    ensure_script_tables()
    doc_layout = ensure_document(project_id)
    target_doc_id = document_id or doc_layout.id
    slot = next_free_slot(project_id, target_doc_id)
    with SessionLocal() as db:
        script_doc = get_or_create_script_doc(db, project_id)
        segment = (
            db.query(ScriptSegmentRow)
            .filter(ScriptSegmentRow.project_id == project_id)
            .order_by(ScriptSegmentRow.index.asc())
            .first()
        )
        if not segment:
            segment = ScriptSegmentRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                doc_id=script_doc.id,
                index=0,
                segment_number=1,
                segment_type="action",
                text="Storyboard beat",
                action="Storyboard beat",
            )
            db.add(segment)
            db.flush()
        count = (
            db.query(StoryboardPanelRow)
            .filter(StoryboardPanelRow.project_id == project_id)
            .count()
        )
        panel = StoryboardPanelRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=script_doc.id,
            segment_id=segment.id,
            panel_index=count,
            label=label or "",
            asset_id=None,
            prompt="",
            status="missing",
            approval="draft",
            script_sync_status="ok",
            meta_json=json.dumps({"emptySlot": True}),
        )
        db.add(panel)
        db.commit()
        db.refresh(panel)
        panel_id = panel.id
    layout = append_panel(project_id, target_doc_id, panel_id)
    return {
        "panelId": panel_id,
        "documentId": layout.id if layout else target_doc_id,
        "slot": slot,
        "assetId": None,
    }


def patch_panel(
    project_id: str,
    panel_id: str,
    *,
    label: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    from .contracts import CAPTION_MAX

    ensure_script_tables()
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        if label is not None:
            row.label = str(label)[:CAPTION_MAX]
        if prompt is not None:
            row.prompt = str(prompt)
        row.updated_at = datetime.utcnow()
        db.commit()
        return {
            "ok": True,
            "panelId": panel_id,
            "label": row.label or "",
            "prompt": row.prompt or "",
            "assetId": row.asset_id,
        }


def assign_panel_asset(project_id: str, panel_id: str, asset_id: str) -> dict[str, Any]:
    from ..db import Asset

    if not asset_id:
        return {"ok": False, "error": "assetId required"}
    ensure_script_tables()
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        asset = db.get(Asset, asset_id)
        if not asset or asset.project_id != project_id:
            return {"ok": False, "error": "library asset not found"}
        meta = _meta(row)
        previous = {
            "assetId": row.asset_id,
            "prompt": row.prompt,
            "label": row.label,
            "status": row.status,
        }
        meta["previousAsset"] = previous
        row.asset_id = asset_id
        row.status = "complete"
        row.meta_json = json.dumps(meta)
        row.updated_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "panelId": panel_id, "assetId": asset_id}


def clear_panel_asset(project_id: str, panel_id: str) -> dict[str, Any]:
    """Remove the image from the board. Never deletes the Library asset."""
    ensure_script_tables()
    with SessionLocal() as db:
        row = db.get(StoryboardPanelRow, panel_id)
        if not row or row.project_id != project_id:
            return {"ok": False, "error": "panel not found"}
        row.asset_id = None
        row.status = "missing"
        row.updated_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "panelId": panel_id, "assetId": None, "cleared": True}
