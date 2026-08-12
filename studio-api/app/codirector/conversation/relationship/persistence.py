"""Project-scoped relationship + creator profile persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ....db import Project
from .schemas import CoDirectorRelationshipProfile, CreatorCreativeProfile, balanced_defaults

_REL_KEY = "relationshipProfile"
_CREATOR_KEY = "creatorCreativeProfile"
_GLOBAL_KEY = "globalRelationshipProfile"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings(project: Project | None) -> dict[str, Any]:
    if not project:
        return {}
    try:
        data = json.loads(getattr(project, "settings_json", "") or "{}")
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def load_relationship_profile(db: Session, project_id: str) -> CoDirectorRelationshipProfile:
    project = db.get(Project, project_id) if project_id else None
    settings = _settings(project)
    payload = settings.get(_REL_KEY)
    if isinstance(payload, dict):
        try:
            return CoDirectorRelationshipProfile.model_validate(payload)
        except Exception:
            pass
    # Global prefs may seed names/role when project profile absent.
    global_payload = settings.get(_GLOBAL_KEY)
    if isinstance(global_payload, dict):
        try:
            g = CoDirectorRelationshipProfile.model_validate(global_payload)
            g.relationship_scope = "PROJECT"
            g.onboarding_completed = False
            return g
        except Exception:
            pass
    return CoDirectorRelationshipProfile()


def save_relationship_profile(db: Session, project_id: str, profile: CoDirectorRelationshipProfile) -> None:
    project = db.get(Project, project_id) if project_id else None
    if not project:
        return
    settings = _settings(project)
    profile.updated_at = _now()
    settings[_REL_KEY] = profile.model_dump(mode="json")
    if profile.relationship_scope == "GLOBAL":
        settings[_GLOBAL_KEY] = profile.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()


def load_creator_profile(db: Session, project_id: str) -> CreatorCreativeProfile:
    project = db.get(Project, project_id) if project_id else None
    settings = _settings(project)
    payload = settings.get(_CREATOR_KEY)
    if isinstance(payload, dict):
        try:
            return CreatorCreativeProfile.model_validate(payload)
        except Exception:
            pass
    return CreatorCreativeProfile()


def save_creator_profile(db: Session, project_id: str, profile: CreatorCreativeProfile) -> None:
    project = db.get(Project, project_id) if project_id else None
    if not project:
        return
    settings = _settings(project)
    settings[_CREATOR_KEY] = profile.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()


def ensure_relationship_ready(db: Session, project_id: str) -> CoDirectorRelationshipProfile:
    profile = load_relationship_profile(db, project_id)
    return profile


def skip_onboarding(db: Session, project_id: str) -> CoDirectorRelationshipProfile:
    profile = balanced_defaults()
    save_relationship_profile(db, project_id, profile)
    return profile
