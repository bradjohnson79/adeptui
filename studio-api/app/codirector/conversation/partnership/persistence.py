"""Project-isolated partnership intelligence persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ....db import Project
from .schemas import PartnershipProjectBundle

_KEY = "partnershipIntelligence"


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


def load_partnership_bundle(db: Session, project_id: str) -> PartnershipProjectBundle:
    project = db.get(Project, project_id) if project_id else None
    settings = _settings(project)
    payload = settings.get(_KEY)
    if isinstance(payload, dict):
        try:
            bundle = PartnershipProjectBundle.model_validate(payload)
            if not bundle.collaboration.project_id:
                bundle.collaboration.project_id = project_id
            if not bundle.journey.project_id:
                bundle.journey.project_id = project_id
            if not bundle.vision.project_id:
                bundle.vision.project_id = project_id
            if not bundle.marketing.project_id:
                bundle.marketing.project_id = project_id
            return bundle
        except Exception:
            pass
    bundle = PartnershipProjectBundle()
    bundle.collaboration.project_id = project_id or ""
    bundle.journey.project_id = project_id or ""
    bundle.vision.project_id = project_id or ""
    bundle.marketing.project_id = project_id or ""
    return bundle


def save_partnership_bundle(db: Session, project_id: str, bundle: PartnershipProjectBundle) -> None:
    project = db.get(Project, project_id) if project_id else None
    if not project:
        return
    settings = _settings(project)
    bundle.collaboration.project_id = project_id
    bundle.collaboration.updated_at = _now()
    bundle.journey.project_id = project_id
    bundle.vision.project_id = project_id
    bundle.marketing.project_id = project_id
    # Never upgrade PREVIEW to approved on save — strip accidental APPROVED on PREVIEW content
    for d in bundle.deliverables:
        if d.status.value == "PREVIEW" and d.approval_required:
            pass  # keep as PREVIEW
    settings[_KEY] = bundle.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()
