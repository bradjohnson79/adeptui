"""Read-only adapter: M2.8 shot profiles → unified intent preview."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def preview_shot_profile(db: Session, profile_id: str) -> dict[str, Any]:
    from ...codirector.m28.shot_profiles.service import ShotProfileService

    profile = ShotProfileService.get(db, profile_id)
    if not profile:
        return {
            "intent": {},
            "providerMappings": {},
            "source": {"system": "m28", "id": profile_id, "version": None},
            "gaps": ["not_found"],
            "needsClarification": True,
        }
    payload = profile.get("payload") or {}
    intent = {
        "camera": payload.get("camera") or {},
        "lighting": payload.get("lighting") or {},
        "grade": payload.get("grade") or {},
        "atmosphere": payload.get("atmosphere") or {},
        "mode": payload.get("mode"),
    }
    gaps: list[str] = []
    if not intent["camera"]:
        gaps.append("missing_camera")
    if not intent["lighting"]:
        gaps.append("missing_lighting")
    return {
        "intent": intent,
        "providerMappings": {},
        "source": {
            "system": "m28",
            "id": profile_id,
            "version": profile.get("activeVersionId"),
            "name": profile.get("name"),
        },
        "gaps": gaps,
        "needsClarification": bool(gaps),
        "note": "Read-only preview. Not a native creative_item.",
    }


def preview_project_shot_profiles(db: Session, project_id: str) -> list[dict[str, Any]]:
    from sqlalchemy import text

    try:
        rows = db.execute(
            text("SELECT id FROM m28_shot_profiles WHERE project_id = :pid"),
            {"pid": project_id},
        ).mappings().all()
    except Exception:
        return []
    return [preview_shot_profile(db, r["id"]) for r in rows]
