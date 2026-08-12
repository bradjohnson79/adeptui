"""Persist discovery bundle in project settings."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ....db import Project
from .schemas import DiscoveryProjectBundle, LivingProjectBrief

_KEY = "discoveryIntelligence"


def _settings(project: Project | None) -> dict[str, Any]:
    if not project:
        return {}
    try:
        data = json.loads(getattr(project, "settings_json", "") or "{}")
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def load_discovery_bundle(db: Session, project_id: str) -> DiscoveryProjectBundle:
    project = db.get(Project, project_id) if project_id else None
    settings = _settings(project)
    payload = settings.get(_KEY)
    if isinstance(payload, dict):
        try:
            bundle = DiscoveryProjectBundle.model_validate(payload)
            bundle.brief.project_id = project_id
            return bundle
        except Exception:
            pass
    bundle = DiscoveryProjectBundle(brief=LivingProjectBrief(project_id=project_id))
    return bundle


def save_discovery_bundle(db: Session, project_id: str, bundle: DiscoveryProjectBundle) -> None:
    project = db.get(Project, project_id) if project_id else None
    if not project:
        return
    settings = _settings(project)
    bundle.brief.project_id = project_id
    settings[_KEY] = bundle.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()
