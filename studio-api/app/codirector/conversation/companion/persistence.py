"""Project-scoped durable companion memory via project settings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ....db import Project
from .schemas import CompanionProjectBundle, CreatorCompanionState

_SETTINGS_KEY = "companionIntelligence"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_settings(project: Project) -> dict[str, Any]:
    try:
        data = json.loads(getattr(project, "settings_json", "") or "{}")
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def load_companion_bundle(db: Session, project_id: str) -> CompanionProjectBundle:
    project = db.get(Project, project_id)
    if not project:
        bundle = CompanionProjectBundle()
        bundle.companionState.project_id = project_id
        return bundle
    settings = _load_settings(project)
    payload = settings.get(_SETTINGS_KEY)
    if not isinstance(payload, dict):
        bundle = CompanionProjectBundle()
        bundle.companionState = CreatorCompanionState(project_id=project_id, updated_at=_now())
        bundle.creativeLens.project_id = project_id
        bundle.strengthProfile.project_id = project_id
        return bundle
    try:
        bundle = CompanionProjectBundle.model_validate(payload)
    except Exception:
        bundle = CompanionProjectBundle()
    bundle.companionState.project_id = project_id
    bundle.creativeLens.project_id = project_id
    bundle.strengthProfile.project_id = project_id
    return bundle


def save_companion_bundle(db: Session, project_id: str, bundle: CompanionProjectBundle) -> None:
    project = db.get(Project, project_id)
    if not project:
        return
    settings = _load_settings(project)
    bundle.companionState.project_id = project_id
    bundle.companionState.updated_at = _now()
    settings[_SETTINGS_KEY] = bundle.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()
