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

    # m413: Spatial Map + ERS + Scene Creator state. Always present as keys
    # (None when absent) so callers can distinguish "pillar absent" from
    # "pillar errored" without a try/except at the call site. These reuse the
    # same authoritative stores as the spatial_map router and ers_persistence
    # — no duplicate stores (Build Law #5, #17).
    result["spatial_map_summary"] = _get_spatial_map_summary(db, project_id)
    result["ers_packages"] = _get_ers_packages(db, project_id)
    result["scene_batches"] = _get_scene_batches(db, project_id)

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
    """Get foundation status for all four pillars.

    The authoritative Foundation Status (story/script/storyboard/characters
    pillar readiness, missing pillars, ready-for-timeline flag) is produced by
    ``app.project_foundation.service.get_foundation_status``, shared by the
    HTTP router and Co-Director read tools so the two can never drift apart.
    """
    try:
        from app.project_foundation.service import get_foundation_status

        status = get_foundation_status(db, project_id)
        return status.model_dump()
    except Exception:
        pass
    return None


def _get_spatial_map_summary(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Compact summary of the most recent SpatialMapDocument.

    Reuses ``spatial_map.service.list_documents`` — the same authoritative
    store the spatial_map HTTP router uses. Returns ``None`` when absent or
    when the subsystem is unavailable. The summary is intentionally small so
    it can be injected into Co-Director context without dumping raw placement
    JSON.
    """
    try:
        from app.spatial_map.service import list_documents

        docs = list_documents(db, project_id)
        if not docs:
            return None
        doc = docs[0]
        has_ers = False
        try:
            from app.spatial_map.ers_persistence import list_ers_packages

            for pkg in list_ers_packages(db, project_id):
                if pkg.scene_layout_id == doc.id:
                    has_ers = True
                    break
        except Exception:
            pass
        return {
            "id": doc.id,
            "title": doc.title,
            "character_count": len(doc.characters or []),
            "prop_count": len(doc.props or []),
            "camera_count": len(doc.cameras or []),
            "has_background": bool(doc.backgroundAssetId),
            "has_ers": has_ers,
            "scene_id": doc.sceneId,
            "updated_at": doc.updatedAt,
        }
    except Exception:
        pass
    return None


def _get_ers_packages(db: Session, project_id: str) -> Optional[list[dict[str, Any]]]:
    """Compact summaries of recent EnvironmentReferencePackage entries.

    Reuses ``spatial_map.ers_persistence.list_ers_packages``. Returns ``None``
    when no ERS packages exist or the subsystem is unavailable.
    """
    try:
        from app.spatial_map.ers_persistence import list_ers_packages

        packages = list_ers_packages(db, project_id)
        if not packages:
            return None
        summaries: list[dict[str, Any]] = []
        for pkg in packages[:5]:
            directional = pkg.directional_assets or {}
            summaries.append(
                {
                    "id": pkg.id,
                    "scene_layout_id": pkg.scene_layout_id,
                    "atlas_asset_id": pkg.atlas_asset_id,
                    "has_directional_assets": any(directional.values()),
                    "has_composite": bool(pkg.ers_composite_asset_id),
                    "orientation": pkg.orientation,
                    "created_at": pkg.created_at,
                }
            )
        return summaries
    except Exception:
        pass
    return None


def _get_scene_batches(db: Session, project_id: str) -> Optional[list[dict[str, Any]]]:
    """Compact summaries of recent SceneGenerationBatch entries.

    Reuses ``spatial_map.ers_persistence.list_scene_batches``. Returns
    ``None`` when no scene batches exist or the subsystem is unavailable.
    """
    try:
        from app.spatial_map.ers_persistence import list_scene_batches

        batches = list_scene_batches(db, project_id)
        if not batches:
            return None
        summaries: list[dict[str, Any]] = []
        for batch in batches[:5]:
            results = list(batch.result_asset_ids or [])
            completed = sum(1 for r in results if r and not str(r).startswith("failed_"))
            summaries.append(
                {
                    "id": batch.id,
                    "ers_package_id": batch.ers_package_id,
                    "shot_count": len(batch.shot_requests or []),
                    "completed_count": completed,
                    "output_count": batch.output_count,
                    "created_at": batch.created_at,
                }
            )
        return summaries
    except Exception:
        pass
    return None
