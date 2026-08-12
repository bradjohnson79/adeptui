"""Project-scoped persistence for Creative Operating Intelligence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .contracts import CreativeOperatingBundle

_KEY = "creativeOperating"


def _settings(project: Any) -> dict[str, Any]:
    raw = getattr(project, "settings_json", None)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def load_bundle(db: Session, project_id: str) -> CreativeOperatingBundle:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return CreativeOperatingBundle(projectId=project_id)
    raw = _settings(project).get(_KEY)
    if not isinstance(raw, dict):
        return CreativeOperatingBundle(projectId=project_id)
    try:
        bundle = CreativeOperatingBundle.model_validate(raw)
        bundle.projectId = project_id
        return bundle
    except Exception:  # noqa: BLE001
        return CreativeOperatingBundle(projectId=project_id)


def save_bundle(db: Session, bundle: CreativeOperatingBundle) -> CreativeOperatingBundle:
    from app.db import Project

    project = db.get(Project, bundle.projectId)
    if not project:
        return bundle
    settings = _settings(project)
    bundle.updatedAt = datetime.now(timezone.utc).isoformat()
    bundle.revision = int(bundle.revision or 0) + 1
    settings[_KEY] = bundle.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()
    return bundle
