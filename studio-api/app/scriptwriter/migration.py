"""Safe migration from legacy script_segments → ScriptDocument."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..script_storyboard import ScriptDocRow, ScriptSegmentRow, ensure_script_tables
from .errors import SCRIPT_PARSE_UNCERTAIN, ScriptwriterError
from .fountain import parse_fountain
from .models import ScriptDocument, ScriptElement
from .store import list_documents, save_document, save_migration_backup
from .transactions import commit_transaction


_TYPE_MAP = {
    "scene_heading": "scene_heading",
    "action": "action",
    "dialogue": "dialogue",
    "dialogue_exchange": "dialogue",
    "transition": "transition",
    "camera_beat": "shot",
    "story_beat": "section",
    "reaction": "action",
    "insert": "shot",
    "vfx": "shot",
    "sound_cue": "note",
}


def preview_migration(db: Session, project_id: str) -> dict[str, Any]:
    ensure_script_tables()
    existing = list_documents(db, project_id)
    if existing:
        return {
            "ok": True,
            "alreadyMigrated": True,
            "documents": [d.model_dump(mode="json") for d in existing],
        }
    legacy = (
        db.query(ScriptDocRow)
        .filter(ScriptDocRow.project_id == project_id)
        .order_by(ScriptDocRow.created_at.asc())
        .first()
    )
    if not legacy:
        return {"ok": True, "alreadyMigrated": False, "empty": True, "elements": []}
    segs = (
        db.query(ScriptSegmentRow)
        .filter(ScriptSegmentRow.doc_id == legacy.id)
        .order_by(ScriptSegmentRow.index.asc())
        .all()
    )
    elements, uncertain = _segments_to_elements(segs)
    return {
        "ok": True,
        "alreadyMigrated": False,
        "legacyDocId": legacy.id,
        "title": legacy.title,
        "elementCount": len(elements),
        "uncertainCount": uncertain,
        "elementsPreview": [e.model_dump(mode="json") for e in elements[:40]],
        "warning": SCRIPT_PARSE_UNCERTAIN if uncertain else None,
    }


def run_migration(db: Session, project_id: str) -> dict[str, Any]:
    preview = preview_migration(db, project_id)
    if preview.get("alreadyMigrated"):
        return preview
    if preview.get("empty"):
        doc = ScriptDocument(
            id=str(uuid.uuid4()),
            projectId=project_id,
            title="Untitled Script",
            elements=[
                ScriptElement(id=str(uuid.uuid4()), type="scene_heading", text="INT. LOCATION - DAY", order=0),
                ScriptElement(id=str(uuid.uuid4()), type="action", text="", order=1),
            ],
        )
        save_document(db, doc)
        return {"ok": True, "document": doc.model_dump(mode="json"), "createdEmpty": True}

    legacy_id = str(preview["legacyDocId"])
    legacy = db.get(ScriptDocRow, legacy_id)
    segs = (
        db.query(ScriptSegmentRow)
        .filter(ScriptSegmentRow.doc_id == legacy_id)
        .order_by(ScriptSegmentRow.index.asc())
        .all()
    )
    elements, uncertain = _segments_to_elements(segs)
    backup = {
        "legacyDoc": {
            "id": legacy.id if legacy else legacy_id,
            "title": legacy.title if legacy else "Untitled",
            "revision": legacy.revision if legacy else 1,
        },
        "segments": [
            {
                "id": s.id,
                "index": s.index,
                "segment_type": s.segment_type,
                "speaker": s.speaker,
                "text": s.text,
                "action": s.action,
                "dialogue": s.dialogue,
                "location": s.location,
                "scene_id": s.scene_id,
            }
            for s in segs
        ],
    }
    doc = ScriptDocument(
        id=str(uuid.uuid4()),
        projectId=project_id,
        title=(legacy.title if legacy else "Untitled Script") or "Untitled Script",
        elements=elements,
        legacyDocId=legacy_id,
    )
    save_document(db, doc)
    backup_id = save_migration_backup(db, project_id, doc.id, backup)

    def mutate(d: ScriptDocument) -> list[str]:
        # already saved; record migration transaction with snapshot
        return [e.id for e in d.elements]

    doc, tx = commit_transaction(
        db,
        doc,
        kind="migration",
        source="migration",
        mutate=mutate,
        reversible=True,
        extra_payload={"backupId": backup_id, "uncertainCount": uncertain},
    )
    return {
        "ok": True,
        "document": doc.model_dump(mode="json"),
        "transaction": tx.model_dump(mode="json"),
        "backupId": backup_id,
        "uncertainCount": uncertain,
    }


def _segments_to_elements(segs: list[ScriptSegmentRow]) -> tuple[list[ScriptElement], int]:
    elements: list[ScriptElement] = []
    uncertain = 0
    order = 0
    for s in segs:
        mapped = _TYPE_MAP.get(s.segment_type)
        if not mapped:
            mapped = "general"
            uncertain += 1
        text = (s.text or s.action or s.dialogue or "").strip()
        if mapped == "dialogue" and s.speaker:
            # emit character + dialogue
            elements.append(
                ScriptElement(
                    id=str(uuid.uuid4()),
                    type="character",
                    text=s.speaker.strip().upper(),
                    order=order,
                    sceneId=s.scene_id,
                    legacySegmentId=s.id,
                )
            )
            order += 1
            elements.append(
                ScriptElement(
                    id=str(uuid.uuid4()),
                    type="dialogue",
                    text=text or (s.dialogue or ""),
                    order=order,
                    sceneId=s.scene_id,
                    legacySegmentId=s.id,
                    metadata={"speaker": s.speaker},
                )
            )
            order += 1
            continue
        if mapped == "scene_heading" and not text and s.location:
            tod = s.time_of_day or "DAY"
            text = f"INT. {s.location.upper()} - {tod.upper()}"
        el = ScriptElement(
            id=str(uuid.uuid4()),
            type=mapped,  # type: ignore[arg-type]
            text=text,
            order=order,
            sceneId=s.scene_id,
            legacySegmentId=s.id,
            metadata={"location": s.location, "timeOfDay": s.time_of_day, "speaker": s.speaker},
        )
        elements.append(el)
        order += 1
    if not elements:
        # try join texts as fountain
        blob = "\n\n".join((s.text or s.action or s.dialogue or "").strip() for s in segs if (s.text or s.action or s.dialogue))
        if blob:
            elements = parse_fountain(blob)
            uncertain += 1
    return elements, uncertain
