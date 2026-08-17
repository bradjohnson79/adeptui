"""StoryboardDocument persistence — page layout over existing storyboard_panels."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..script_storyboard import PanelOut, StoryboardPanelRow, ensure_script_tables
from ..db import SessionLocal
from .contracts import StoryboardDocument, StoryboardPage, StoryboardPageSize
from .script_sync import map_legacy_panel_sync, unify_status


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root(project_id: str) -> Path:
    base = Path(settings.data_dir) / "storyboard_studio" / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def _docs_path(project_id: str) -> Path:
    return _root(project_id) / "documents.json"


def _read_docs(project_id: str) -> list[dict[str, Any]]:
    path = _docs_path(project_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_docs(project_id: str, items: list[dict[str, Any]]) -> None:
    _docs_path(project_id).write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _pages_from_order(panel_order: list[str], page_size: StoryboardPageSize) -> list[StoryboardPage]:
    pages: list[StoryboardPage] = []
    if not panel_order:
        return [StoryboardPage(pageIndex=0, pageSize=page_size, panelIds=[])]
    for i in range(0, len(panel_order), page_size):
        chunk = panel_order[i : i + page_size]
        pages.append(
            StoryboardPage(
                pageIndex=len(pages),
                pageSize=page_size,
                panelIds=chunk,
                title=f"Page {len(pages) + 1}",
            )
        )
    return pages


def list_documents(project_id: str) -> list[StoryboardDocument]:
    out: list[StoryboardDocument] = []
    for raw in _read_docs(project_id):
        try:
            out.append(StoryboardDocument.model_validate(raw))
        except Exception:
            continue
    return out


def get_document(project_id: str, document_id: str) -> StoryboardDocument | None:
    for d in list_documents(project_id):
        if d.id == document_id:
            return d
    return None


def save_document(doc: StoryboardDocument) -> StoryboardDocument:
    items = _read_docs(doc.projectId)
    payload = doc.model_dump()
    items = [i for i in items if i.get("id") != doc.id]
    items.insert(0, payload)
    _write_docs(doc.projectId, items[:50])
    return doc


def _legacy_panel_ids(project_id: str) -> tuple[list[str], str | None]:
    ensure_script_tables()
    with SessionLocal() as db:
        rows = (
            db.query(StoryboardPanelRow)
            .filter(StoryboardPanelRow.project_id == project_id)
            .order_by(StoryboardPanelRow.panel_index.asc(), StoryboardPanelRow.created_at.asc())
            .all()
        )
        if not rows:
            return [], None
        return [r.id for r in rows], rows[0].doc_id


def ensure_document(project_id: str, *, page_size: StoryboardPageSize = 9) -> StoryboardDocument:
    existing = list_documents(project_id)
    if existing:
        return existing[0]
    panel_ids, legacy_doc_id = _legacy_panel_ids(project_id)
    now = _now()
    doc = StoryboardDocument(
        id=str(uuid.uuid4()),
        projectId=project_id,
        title="Storyboard",
        pageSize=page_size,
        panelOrder=panel_ids,
        pages=_pages_from_order(panel_ids, page_size),
        legacyDocId=legacy_doc_id,
        createdAt=now,
        updatedAt=now,
    )
    return save_document(doc)


def set_page_size(project_id: str, document_id: str, page_size: StoryboardPageSize) -> StoryboardDocument | None:
    doc = get_document(project_id, document_id)
    if not doc:
        return None
    data = doc.model_dump()
    data["pageSize"] = page_size
    data["pages"] = [p.model_dump() for p in _pages_from_order(doc.panelOrder, page_size)]
    data["updatedAt"] = _now()
    return save_document(StoryboardDocument.model_validate(data))


def reorder_panels(
    project_id: str,
    document_id: str,
    panel_order: list[str],
) -> StoryboardDocument | None:
    doc = get_document(project_id, document_id)
    if not doc:
        return None
    data = doc.model_dump()
    data["panelOrder"] = list(panel_order)
    data["pages"] = [p.model_dump() for p in _pages_from_order(list(panel_order), doc.pageSize)]
    data["updatedAt"] = _now()
    return save_document(StoryboardDocument.model_validate(data))


def append_panel(
    project_id: str,
    document_id: str,
    panel_id: str,
) -> StoryboardDocument | None:
    doc = get_document(project_id, document_id) or ensure_document(project_id)
    if doc.id != document_id and document_id:
        doc = get_document(project_id, document_id) or doc
    order = list(doc.panelOrder)
    if panel_id not in order:
        order.append(panel_id)
    return reorder_panels(project_id, doc.id, order)


def next_free_slot(project_id: str, document_id: str | None = None) -> dict[str, Any]:
    doc = get_document(project_id, document_id) if document_id else ensure_document(project_id)
    if not doc:
        doc = ensure_document(project_id)
    page_size = int(doc.pageSize)
    idx = len(doc.panelOrder)
    return {
        "documentId": doc.id,
        "pageIndex": idx // page_size,
        "slotIndex": idx % page_size,
        "nextPanelOrdinal": idx,
    }


def pad_empty_slots(project_id: str, document_id: str | None = None) -> StoryboardDocument:
    """Ensure the last page has a full page of slots (empty panels allowed)."""
    doc = get_document(project_id, document_id) if document_id else ensure_document(project_id)
    if not doc:
        doc = ensure_document(project_id)
    page_size = int(doc.pageSize)
    order = list(doc.panelOrder or [])
    if not order:
        needed = page_size
    else:
        remainder = len(order) % page_size
        needed = 0 if remainder == 0 else page_size - remainder
    if needed <= 0:
        return doc
    from .add_from_image import create_empty_panel

    for _ in range(needed):
        create_empty_panel(project_id, document_id=doc.id)
    return get_document(project_id, doc.id) or ensure_document(project_id)


def hydrate_panels(project_id: str, document_id: str | None = None) -> dict[str, Any]:
    """Return document + panel link rows for FE StoryboardStudio."""
    pad_empty_slots(project_id, document_id)
    doc = get_document(project_id, document_id) if document_id else ensure_document(project_id)
    if not doc:
        doc = ensure_document(project_id)
    ensure_script_tables()
    panels: list[dict[str, Any]] = []
    with SessionLocal() as db:
        rows = (
            db.query(StoryboardPanelRow)
            .filter(StoryboardPanelRow.project_id == project_id)
            .all()
        )
        by_id = {r.id: r for r in rows}
        order = doc.panelOrder or [r.id for r in sorted(rows, key=lambda x: x.panel_index)]
        for ordinal, pid in enumerate(order):
            row = by_id.get(pid)
            if not row:
                continue
            out = PanelOut.from_row(row)
            meta = out.meta if isinstance(out.meta, dict) else {}
            panels.append(
                {
                    "panelId": out.id,
                    "pageIndex": ordinal // int(doc.pageSize),
                    "slotIndex": ordinal % int(doc.pageSize),
                    "assetId": out.asset_id,
                    "label": out.label,
                    "prompt": out.prompt,
                    "lens": out.lens,
                    "shotSize": out.shot_size,
                    "approval": out.approval,
                    "status": out.status,
                    "scriptLinkStatus": unify_status(
                        panel_sync=out.script_sync_status,
                        has_segment_link=bool(out.segment_id),
                        has_scene_link=bool(meta.get("scriptwriterSceneId") or meta.get("sceneId")),
                        creator_override=bool(meta.get("override")),
                    ),
                    "segmentId": out.segment_id,
                    "scriptwriterSceneId": meta.get("scriptwriterSceneId") or meta.get("sceneId"),
                    "scriptwriterActionId": meta.get("scriptwriterActionId"),
                    "scriptwriterDialogueId": meta.get("scriptwriterDialogueId"),
                    "continuitySessionId": meta.get("continuitySessionId") or doc.continuitySessionId,
                    "spatialMapId": meta.get("spatialMapId"),
                    "spatialMapVersion": meta.get("spatialMapVersion"),
                    "durationEst": out.duration_est,
                    "meta": meta,
                    "legacySync": map_legacy_panel_sync(out.script_sync_status),
                }
            )
    return {"document": doc.model_dump(), "panels": panels}
