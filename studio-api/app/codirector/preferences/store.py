"""Project-scoped generator preferences (not a second asset store)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ...db import ProjectTraitRow


CATEGORY = "codirector_generator_preferences"
KEY = "defaults"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_generator_preferences(db: Session, project_id: str) -> dict[str, Any]:
    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == CATEGORY,
            ProjectTraitRow.key == KEY,
        )
        .first()
    )
    if row is None or not row.value:
        return {}
    try:
        data = json.loads(row.value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_generator_preference(
    db: Session,
    project_id: str,
    modality: str,
    provider: str,
) -> dict[str, Any]:
    current = load_generator_preferences(db, project_id)
    current[modality] = provider
    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == CATEGORY,
            ProjectTraitRow.key == KEY,
        )
        .first()
    )
    payload = json.dumps(current)
    if row:
        row.value = payload
        row.provenance = "CODEX_PREFERENCE_RESOLVER"
    else:
        db.add(
            ProjectTraitRow(
                id=str(uuid4()),
                project_id=project_id,
                category=CATEGORY,
                key=KEY,
                value=payload,
                provenance="CODEX_PREFERENCE_RESOLVER",
                created_at=_now(),
            )
        )
    db.commit()
    return current
