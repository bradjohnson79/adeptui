"""Notes CRUD + bridge from knowledgeEntries + promotion helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..conversation.knowledge import apply_wiki_candidates
from ..conversation.schemas import WikiCandidate
from ..conversation.snapshot import load_snapshot, save_snapshot
from .contracts import WorkingNote


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _note_id(project_id: str, text: str) -> str:
    digest = hashlib.sha1(f"{project_id}:{text.strip().lower()}".encode("utf-8")).hexdigest()[:12]
    return f"note-{digest}"


def _guess_category(text: str) -> str:
    lower = (text or "").lower()
    if re.search(r"\b(character|protagonist|agent|dr\.|doctor)\b", lower):
        return "Character"
    if re.search(r"\b(location|room|facility|set|place)\b", lower):
        return "Location"
    if re.search(r"\b(theme|premise|story|plot|episode)\b", lower):
        return "Story"
    if re.search(r"\b(world|lore|rule)\b", lower):
        return "World"
    if re.search(r"\b(research|archive|interview)\b", lower):
        return "Research"
    if "?" in (text or ""):
        return "Question"
    if re.search(r"\b(maybe|might|could|possible|what if)\b", lower):
        return "Idea"
    return "Unresolved"


def _ensure_notes_list(snapshot: Any) -> list[WorkingNote]:
    raw = getattr(snapshot, "workingNotes", None)
    if raw is None:
        # Bridge knowledgeEntries into Notes on first access
        notes: list[WorkingNote] = []
        for entry in getattr(snapshot, "knowledgeEntries", None) or []:
            text = str(getattr(entry, "text", "") or "").strip()
            if len(text) < 3:
                continue
            state = str(getattr(entry, "state", "proposed") or "proposed")
            if state in {"rejected", "superseded"}:
                continue
            status = "PROMOTED" if state in {"confirmed", "approved"} else "RAW"
            notes.append(
                WorkingNote(
                    id=_note_id(snapshot.projectId, text),
                    projectId=snapshot.projectId,
                    text=text,
                    category=_guess_category(text),  # type: ignore[arg-type]
                    source="conversation",
                    confidence=0.7 if status == "PROMOTED" else 0.5,
                    promotionStatus=status,  # type: ignore[arg-type]
                    authority="MODEL_INFERRED_WIKI_CANDIDATE",
                )
            )
        snapshot.workingNotes = [n.model_dump(mode="json") for n in notes]  # type: ignore[attr-defined]
        return notes
    out: list[WorkingNote] = []
    for item in raw:
        if isinstance(item, WorkingNote):
            out.append(item)
        elif isinstance(item, dict):
            out.append(WorkingNote.model_validate(item))
        else:
            try:
                out.append(WorkingNote.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
    snapshot.workingNotes = [n.model_dump(mode="json") for n in out]  # type: ignore[attr-defined]
    return out


def list_notes(db: Session, project_id: str) -> dict[str, Any]:
    snapshot = load_snapshot(db, project_id)
    notes = _ensure_notes_list(snapshot)
    # Persist bridge once
    save_snapshot(db, snapshot)
    visible = [n for n in notes if n.promotionStatus not in {"DISMISSED", "SUPERSEDED"}]
    return {
        "ok": True,
        "projectId": project_id,
        "notes": [n.model_dump(mode="json") for n in visible],
        "count": len(visible),
        "layer": "notes_working_memory",
    }


def upsert_notes_from_texts(
    db: Session,
    project_id: str,
    texts: list[str],
    *,
    source: str = "conversation",
    category: str | None = None,
    authority: str = "MODEL_INFERRED_WIKI_CANDIDATE",
) -> list[WorkingNote]:
    snapshot = load_snapshot(db, project_id)
    notes = _ensure_notes_list(snapshot)
    by_id = {n.id: n for n in notes}
    created: list[WorkingNote] = []
    for text in texts:
        t = (text or "").strip()
        if len(t) < 8:
            continue
        nid = _note_id(project_id, t)
        if nid in by_id:
            continue
        note = WorkingNote(
            id=nid,
            projectId=project_id,
            text=t,
            category=(category or _guess_category(t)),  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            authority=authority,
            promotionStatus="RAW",
        )
        notes.insert(0, note)
        by_id[nid] = note
        created.append(note)
    snapshot.workingNotes = [n.model_dump(mode="json") for n in notes[:200]]  # type: ignore[attr-defined]
    save_snapshot(db, snapshot)
    return created


def dismiss_note(db: Session, project_id: str, note_id: str) -> dict[str, Any]:
    snapshot = load_snapshot(db, project_id)
    notes = _ensure_notes_list(snapshot)
    ok = False
    for n in notes:
        if n.id == note_id:
            n.promotionStatus = "DISMISSED"
            n.updatedAt = _now()
            ok = True
            break
    snapshot.workingNotes = [n.model_dump(mode="json") for n in notes]  # type: ignore[attr-defined]
    save_snapshot(db, snapshot)
    return {"ok": ok, "projectId": project_id, "noteId": note_id}


def promote_note_to_wiki(
    db: Session,
    project_id: str,
    *,
    note_id: str | None = None,
    text: str | None = None,
    destination: str = "story",
    authority: str = "USER_EXPLICIT_WIKI_WRITE",
    page_hint: str | None = None,
) -> dict[str, Any]:
    """High-authority path: Notes → confirmed knowledge → dirty compile."""
    snapshot = load_snapshot(db, project_id)
    notes = _ensure_notes_list(snapshot)
    body = (text or "").strip()
    target: WorkingNote | None = None
    if note_id:
        target = next((n for n in notes if n.id == note_id), None)
        if target:
            body = target.text
    if not body:
        return {"ok": False, "error": "Nothing to promote"}

    section = {
        "story": "storyAndEpisodes",
        "character": "characters",
        "characters": "characters",
        "world": "worldAndSetting",
        "location": "worldAndSetting",
        "episode": "storyAndEpisodes",
        "overview": "knownDetails",
        "production": "productionDecisions",
    }.get((destination or "story").lower(), "storyAndEpisodes")

    candidate = WikiCandidate(
        id=f"promo-{hashlib.sha1(body.encode()).hexdigest()[:10]}",
        text=body,
        state="confirmed",
        section=section,
        provenance=f"explicit_wiki_write:{authority}",
    )
    snapshot = apply_wiki_candidates(snapshot, [candidate], text or "explicit wiki promote")

    if target:
        target.promotionStatus = "PROMOTED"
        target.authority = authority
        target.promotedPageId = page_hint or destination
        target.updatedAt = _now()
    else:
        note = WorkingNote(
            id=_note_id(project_id, body),
            projectId=project_id,
            text=body,
            category=_guess_category(body),  # type: ignore[arg-type]
            source="creator",
            promotionStatus="PROMOTED",
            authority=authority,
            promotedPageId=page_hint or destination,
            confidence=0.95,
        )
        notes.insert(0, note)

    snapshot.workingNotes = [n.model_dump(mode="json") for n in notes]  # type: ignore[attr-defined]
    save_snapshot(db, snapshot)

    # Trigger compile
    from ..wiki_intelligence.compiled.page_compiler import compile_wiki_bundle

    bundle = compile_wiki_bundle(db, project_id, force_full=True)
    return {
        "ok": True,
        "projectId": project_id,
        "promotedText": body,
        "destination": destination,
        "authority": authority,
        "compiledRevision": bundle.get("compiledRevision"),
        "pageCount": len(bundle.get("pages") or []),
    }


def demote_wiki_to_note(
    db: Session,
    project_id: str,
    record_id: str,
) -> dict[str, Any]:
    """Move a Wiki knowledge record back into Notes (Wiki→Notes).

    The record is superseded (never erased) and re-created as a RAW WorkingNote
    so the creator can refine it before re-promoting. Preserves provenance.
    """
    snapshot = load_snapshot(db, project_id)
    target = None
    for entry in getattr(snapshot, "knowledgeEntries", []) or []:
        if getattr(entry, "id", "") == record_id:
            target = entry
            break
    if target is None:
        return {"ok": False, "error": "record_not_found"}

    text = str(getattr(target, "text", "") or "").strip()
    if not text:
        return {"ok": False, "error": "record_empty"}

    # Supersede the Wiki record (preserve provenance; never erase).
    target.state = "superseded"

    notes = _ensure_notes_list(snapshot)
    note = WorkingNote(
        id=_note_id(project_id, text),
        projectId=project_id,
        text=text,
        category=_guess_category(text),  # type: ignore[arg-type]
        source="creator",
        promotionStatus="RAW",
        authority="USER_EXPLICIT_WIKI_WRITE",
        confidence=0.6,
    )
    # Avoid duplicate notes with the same id.
    notes = [n for n in notes if n.id != note.id]
    notes.insert(0, note)
    snapshot.workingNotes = [n.model_dump(mode="json") for n in notes]  # type: ignore[attr-defined]
    save_snapshot(db, snapshot)

    from ..wiki_intelligence.compiled.page_compiler import compile_wiki_bundle

    bundle = compile_wiki_bundle(db, project_id, force_full=True)
    return {
        "ok": True,
        "projectId": project_id,
        "demotedRecordId": record_id,
        "noteId": note.id,
        "compiledRevision": bundle.get("compiledRevision"),
    }
