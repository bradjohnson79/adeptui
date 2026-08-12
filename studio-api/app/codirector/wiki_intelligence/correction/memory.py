"""Project-scoped creator-correction memory.

Persists `CoDirectorLearnedCorrection` records under `settings_json["correctionMemory"]`.
Project-scoped only — a correction inside one creator's project never becomes a
universal product rule unless deliberately promoted into global product logic.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .contracts import CoDirectorLearnedCorrection

_KEY = "correctionMemory"


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


def _load_project(db: Session, project_id: str) -> Any:
    from app.db import Project

    return db.get(Project, project_id)


def load_corrections(db: Session, project_id: str) -> list[CoDirectorLearnedCorrection]:
    project = _load_project(db, project_id)
    if not project:
        return []
    raw = _settings(project).get(_KEY)
    if not isinstance(raw, list):
        return []
    out: list[CoDirectorLearnedCorrection] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(CoDirectorLearnedCorrection.model_validate(item))
        except Exception:  # noqa: BLE001
            continue
    return out


def save_correction(db: Session, correction: CoDirectorLearnedCorrection) -> CoDirectorLearnedCorrection:
    project = _load_project(db, correction.projectId)
    if not project:
        return correction
    settings = _settings(project)
    existing = load_corrections(db, correction.projectId)
    # Replace same-id, else append. Cap at 100 most recent.
    existing = [c for c in existing if c.id != correction.id]
    existing.append(correction)
    settings[_KEY] = [c.model_dump(mode="json") for c in existing[-100:]]
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()
    return correction


def active_corrections(db: Session, project_id: str) -> list[CoDirectorLearnedCorrection]:
    return [c for c in load_corrections(db, project_id) if c.active]


def active_aliases(db: Session, project_id: str) -> dict[str, str]:
    """Alias map learned from creator merge corrections (alias -> canonical)."""
    out: dict[str, str] = {}
    for c in active_corrections(db, project_id):
        for alias, canonical in (c.aliases or {}).items():
            if alias and canonical:
                out[alias] = canonical
    return out


def active_rules(db: Session, project_id: str) -> list[str]:
    """Human-readable learned rules (e.g. 'Do not re-center the Story Summary on the Adept')."""
    return [c.learnedRule for c in active_corrections(db, project_id) if c.learnedRule]


def entity_type_overrides(db: Session, project_id: str) -> dict[str, str]:
    """Entity-name -> entity-type overrides learned from creator reclassifications.

    Keys are normalized (lowercase) entity names; values are entity types such as
    'location', 'organization', 'attribute'.
    """
    out: dict[str, str] = {}
    for c in active_corrections(db, project_id):
        for name, etype in (c.entityTypeOverrides or {}).items():
            if name and etype:
                out[name.strip().lower()] = etype
    return out


__all__ = [
    "load_corrections",
    "save_correction",
    "active_corrections",
    "active_aliases",
    "active_rules",
    "entity_type_overrides",
]
