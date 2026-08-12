"""Deterministic apply of a confirmed creator correction.

DETERMINISTIC_CODE_APPLIES: the LLM never mutates project knowledge. This module
computes and applies exact record changes, supersedes (never erases) old
inferences, writes confirmed creator records, updates correction memory, and
snapshots state for undo.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ....db import Project
from ...conversation.knowledge import apply_wiki_candidates
from ...conversation.schemas import WikiCandidate
from ...conversation.snapshot import load_snapshot, save_snapshot
from .contracts import (
    CoDirectorLearnedCorrection,
    CorrectionPreview,
    CreatorWikiCorrection,
)
from . import memory

_KEY_REVISIONS = "wikiCorrectionRevisions"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings(project: Project) -> dict[str, Any]:
    try:
        raw = json.loads(getattr(project, "settings_json", "") or "{}")
        return raw if isinstance(raw, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_settings(db: Session, project: Project, settings: dict[str, Any]) -> None:
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _section_for_entity_type(entity_type: str) -> str:
    return {
        "character": "characters",
        "location": "locationsAndSets",
        "organization": "worldAndLore",
        "attribute": "characters",
        "wardrobe": "wardrobe",
        "prop": "props",
        "timeline_event": "timeline",
        "world_rule": "worldAndLore",
        "story": "storyAndEpisodes",
        "note": "storyAndEpisodes",
    }.get(entity_type, "storyAndEpisodes")


def _find_entries_containing(snapshot: Any, name: str) -> list[Any]:
    low = _norm(name)
    if not low:
        return []
    out = []
    for entry in getattr(snapshot, "knowledgeEntries", []) or []:
        state = str(getattr(entry, "state", "") or "")
        if state in {"rejected", "superseded"}:
            continue
        if low in _norm(getattr(entry, "text", "") or ""):
            out.append(entry)
    return out


def apply_correction(
    db: Session,
    project_id: str,
    preview: CorrectionPreview,
) -> dict[str, Any]:
    """Apply a confirmed correction. Returns a result dict with undo id + summary lines."""
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}

    snapshot = load_snapshot(db, project_id)

    # Snapshot BEFORE mutation for undo (CORRECTION_MUST_BE_REVERSIBLE).
    undo_snapshot = {
        "projectIntelligence": json.loads(json.dumps(snapshot.model_dump(mode="json"))),
    }
    previous_revision = int((_settings(project).get("wikiRevision") or 0))

    superseded: list[str] = []
    created: list[str] = []
    affected_pages: set[str] = set()
    summary_lines: list[str] = []

    candidates: list[WikiCandidate] = []

    # 1. Entity reclassifications (character-section purity).
    for reclass in preview.entityReclassifications:
        name = reclass.name
        matches = _find_entries_containing(snapshot, name)
        for entry in matches:
            if getattr(entry, "state", "") in {"superseded", "rejected"}:
                continue
            entry.state = "superseded"
            superseded.append(entry.id)
        new_section = _section_for_entity_type(reclass.toType)
        if reclass.toType == "attribute" and reclass.attachTo:
            text = f"{reclass.attachTo}: {name}."
        else:
            text = f"{name} is a {reclass.toType.replace('_', ' ')}."
        cand = WikiCandidate(
            id=f"corr-{uuid4().hex[:10]}",
            text=text,
            state="confirmed",
            section=new_section,
            provenance="explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE",
        )
        candidates.append(cand)
        created.append(cand.id)
        affected_pages.add(new_section)
        summary_lines.append(f"Reclassified “{name}” as a {reclass.toType.replace('_', ' ')}.")

    # 2. Aliases / merges.
    for alias, canonical in (preview.aliases or {}).items():
        for entry in _find_entries_containing(snapshot, alias):
            if getattr(entry, "state", "") in {"superseded", "rejected"}:
                continue
            entry.state = "superseded"
            superseded.append(entry.id)
        cand = WikiCandidate(
            id=f"corr-{uuid4().hex[:10]}",
            text=f"{alias} and {canonical} are the same identity.",
            state="confirmed",
            section="characters",
            provenance="explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE",
        )
        candidates.append(cand)
        created.append(cand.id)
        affected_pages.add("characters")
        summary_lines.append(f"Merged “{alias}” into “{canonical}”.")

    # 3. Explicit record removals / rewrites by id.
    for record_id in preview.affectedRecords:
        for entry in getattr(snapshot, "knowledgeEntries", []) or []:
            if getattr(entry, "id", "") == record_id and getattr(entry, "state", "") not in {
                "superseded",
                "rejected",
            }:
                entry.state = "superseded"
                superseded.append(entry.id)

    # 4. The creator's instruction itself becomes a confirmed high-authority record.
    instruction_text = preview.instruction.strip()
    if instruction_text:
        target_section = "storyAndEpisodes"
        if preview.targets:
            page = (preview.targets[0].pageType or preview.targets[0].pageId or "").lower()
            if "char" in page:
                target_section = "characters"
            elif "stor" in page or "summar" in page:
                target_section = "storyAndEpisodes"
            elif "loc" in page or "world" in page:
                target_section = "worldAndLore"
            elif "timeline" in page or "continuity" in page:
                target_section = "timeline"
        cand = WikiCandidate(
            id=f"corr-{uuid4().hex[:10]}",
            text=instruction_text,
            state="confirmed",
            section=target_section,
            provenance="explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE",
        )
        candidates.append(cand)
        created.append(cand.id)
        affected_pages.add(target_section)

    # Apply candidates deterministically (supersede lifecycle).
    snapshot = apply_wiki_candidates(snapshot, candidates, preview.instruction)
    save_snapshot(db, snapshot)

    # 5. Persist learned correction into project-scoped memory.
    overrides = {
        r.name.strip().lower(): r.toType for r in preview.entityReclassifications
    }
    learned = CoDirectorLearnedCorrection(
        id=f"learn-{uuid4().hex[:12]}",
        projectId=project_id,
        correctionType=preview.correctionType,
        instruction=preview.instruction,
        learnedRule=preview.learnedRule or preview.instruction,
        affectedEntities=[r.name for r in preview.entityReclassifications]
        + list((preview.aliases or {}).keys()),
        aliases=dict(preview.aliases or {}),
        targetSections=[t.label for t in preview.targets if t.label],
        entityTypeOverrides=overrides,
        active=True,
    )
    memory.save_correction(db, learned)

    # 6. Revision record for undo.
    revision_id = f"crev_{uuid4().hex[:12]}"
    correction_id = f"corr_{uuid4().hex[:12]}"
    settings = _settings(project)
    revisions = settings.get(_KEY_REVISIONS) or []
    if not isinstance(revisions, list):
        revisions = []
    revisions.append(
        {
            "revisionId": revision_id,
            "correctionId": correction_id,
            "projectId": project_id,
            "createdAt": _utcnow(),
            "reversible": True,
            "previousWikiRevision": previous_revision,
            "snapshot": undo_snapshot,
            "learnedCorrectionId": learned.id,
        }
    )
    settings[_KEY_REVISIONS] = revisions[-30:]
    _save_settings(db, project, settings)

    # 7. Durable correction record.
    correction = CreatorWikiCorrection(
        id=correction_id,
        projectId=project_id,
        targetPageIds=[t.pageId for t in preview.targets if t.pageId],
        targetSectionIds=[t.sectionId for t in preview.targets if t.sectionId],
        instruction=preview.instruction,
        correctionType=preview.correctionType,
        supersededRecordIds=superseded,
        createdRecordIds=created,
        affectedPageIds=sorted(affected_pages),
        creatorConfirmed=True,
        revisionId=revision_id,
    )
    _persist_correction(db, project, correction)

    if preview.summaryRecompile:
        summary_lines.append("Story Summary revised.")

    return {
        "ok": True,
        "correction": correction.model_dump(mode="json"),
        "undoId": revision_id,
        "learnedCorrectionId": learned.id,
        "summaryLines": summary_lines,
        "supersededCount": len(superseded),
        "createdCount": len(created),
    }


def _persist_correction(db: Session, project: Project, correction: CreatorWikiCorrection) -> None:
    settings = _settings(project)
    history = settings.get("wikiCorrections") or []
    if not isinstance(history, list):
        history = []
    history.append(correction.model_dump(mode="json"))
    settings["wikiCorrections"] = history[-100:]
    _save_settings(db, project, settings)


def list_corrections(db: Session, project_id: str) -> list[dict[str, Any]]:
    project = db.get(Project, project_id)
    if not project:
        return []
    settings = _settings(project)
    history = settings.get("wikiCorrections") or []
    return [h for h in history if isinstance(h, dict)]


__all__ = ["apply_correction", "list_corrections"]
