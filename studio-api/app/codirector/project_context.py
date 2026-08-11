"""Unified project context retrieval for Co-Director.

Retrieves the latest saved versions of project pillars (story, script,
storyboard, characters, foundation status) for Co-Director reasoning.
Does NOT duplicate or cache — always reads from the authoritative source.

A pillar that has not been created yet resolves to ``None``. A pillar whose
authoritative store cannot be reached also resolves to ``None`` rather than
raising, so a single missing pillar never blocks the rest of the context
assembly. Callers that need to distinguish "absent" from "error" can inspect
the returned shape directly.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session


def retrieve_project_context(
    db: Session,
    project_id: str,
    pillars: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Retrieve project pillar content for Co-Director context.

    Args:
        db: Database session.
        project_id: Project UUID.
        pillars: Which pillars to retrieve. ``None`` means all available.

    Returns:
        Dict keyed by pillar name (``story``, ``script``, ``storyboard``,
        ``characters``, ``foundation``). Each value is either the pillar
        content or ``None`` if not available.
    """
    all_pillars = ["story", "script", "storyboard", "characters", "foundation"]
    target_pillars = pillars if pillars else all_pillars

    result: dict[str, Any] = {}
    if "story" in target_pillars:
        result["story"] = _get_story(db, project_id)
    if "script" in target_pillars:
        result["script"] = _get_script(db, project_id)
    if "storyboard" in target_pillars:
        result["storyboard"] = _get_storyboard(db, project_id)
    if "characters" in target_pillars:
        result["characters"] = _get_characters(db, project_id)
    if "foundation" in target_pillars:
        result["foundation"] = _get_foundation(db, project_id)

    return result


def _get_story(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Get story document content from the authoritative story store."""
    try:
        from app.story.store import load_document

        row = load_document(db, project_id)
        if row and row.content:
            return {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "wordCount": row.word_count,
                "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
            }
    except Exception:
        pass
    return None


def _get_script(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Get the most recently updated script document with its elements."""
    try:
        from app.scriptwriter.store import list_documents, load_document

        docs = list_documents(db, project_id)
        if not docs:
            return None
        doc = load_document(db, docs[0].id)
        if not doc:
            return None
        scenes = [
            {"sceneNumber": e.sceneNumber, "type": e.type, "text": e.text}
            for e in doc.elements
            if e.type == "scene_heading"
        ]
        elements = [
            {"type": e.type, "text": e.text, "sceneNumber": e.sceneNumber}
            for e in doc.elements
        ]
        return {
            "id": doc.id,
            "title": doc.title,
            "format": doc.format,
            "draftStatus": doc.draftStatus,
            "revision": doc.revision,
            "elementCount": len(doc.elements),
            "sceneCount": len(scenes),
            "scenes": scenes,
            "elements": elements,
            "updatedAt": doc.updatedAt or None,
        }
    except Exception:
        pass
    return None


def _get_storyboard(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Get storyboard panels via the authoritative storyboard_studio store.

    ``StoryboardDocument.pages`` only carry panel ids; the panel bodies live
    on ``StoryboardPanelRow`` and are hydrated by ``hydrate_panels``. We read
    through that single authoritative path rather than re-deriving layout.
    """
    try:
        from app.storyboard_studio.documents import hydrate_panels

        data = hydrate_panels(project_id)
        panels = data.get("panels") or []
        if not panels:
            return None
        out_panels = []
        for p in panels:
            out_panels.append(
                {
                    "panelId": p.get("panelId"),
                    "label": p.get("label"),
                    "prompt": p.get("prompt"),
                    "shotSize": p.get("shotSize"),
                    "lens": p.get("lens"),
                    "durationEst": p.get("durationEst"),
                    "scriptLinkStatus": p.get("scriptLinkStatus"),
                    "status": p.get("status"),
                    "approval": p.get("approval"),
                }
            )
        return {
            "document": data.get("document"),
            "panelCount": len(out_panels),
            "panels": out_panels,
            "totalDurationEst": sum(p["durationEst"] or 0 for p in out_panels),
        }
    except Exception:
        pass
    return None


def _get_characters(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Get character profiles from the authoritative character_identity service."""
    try:
        from app.character_identity.service import list_profiles

        profiles = list_profiles(db, project_id)
        if not profiles:
            return None
        return {
            "count": len(profiles),
            "characters": [
                {
                    "id": p.id,
                    "name": p.name,
                    "role": p.role,
                    "description": p.description,
                    "status": p.status,
                    "speciesOrType": p.species_or_type,
                    "apparentAge": p.apparent_age,
                    "activeVoiceProfileId": p.active_voice_profile_id,
                }
                for p in profiles
            ],
        }
    except Exception:
        pass
    return None


def _get_foundation(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Get project foundation/status.

    There is no dedicated ``project_foundation`` module; the authoritative
    project status (counts, render progress, status label) is produced by
    ``app.project_service.project_status``, shared by the HTTP router and
    Co-Director read tools so the two can never drift apart.
    """
    try:
        from app.db import Project
        from app.project_service import project_status

        project = db.get(Project, project_id)
        if not project:
            return None
        return project_status(db, project)
    except Exception:
        pass
    return None
