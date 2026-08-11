"""Execution pack store — persists ExecutionPlan packs as project-scoped traits.

Mirrors the visual_sheet pack pattern (character_identity/visual_sheet.py:_save_pack)
but scoped to the project rather than the character profile.

The pack is stored as a JSON value in a `ProjectTraitRow` with:
- category: "codirector_execution"
- key: the execution_id
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..execution.contracts import ExecutionPlan

logger = logging.getLogger(__name__)

PACK_CATEGORY = "codirector_execution"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_pack(db: Session, project_id: str, pack: ExecutionPlan) -> ExecutionPlan:
    """Persist an ExecutionPlan pack as a project trait."""
    from ...db import ProjectTraitRow

    pack.updated_at = _now()
    if not pack.created_at:
        pack.created_at = _now()

    existing = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PACK_CATEGORY,
            ProjectTraitRow.key == pack.execution_id,
        )
        .first()
    )

    if existing:
        existing.value = json.dumps(pack.model_dump(mode="json"))
        existing.provenance = "CODEX_EXECUTION_DISPATCHER"
    else:
        row = ProjectTraitRow(
            id=str(uuid4()),
            project_id=project_id,
            category=PACK_CATEGORY,
            key=pack.execution_id,
            value=json.dumps(pack.model_dump(mode="json")),
            provenance="CODEX_EXECUTION_DISPATCHER",
            created_at=_now(),
        )
        db.add(row)

    db.commit()
    return pack


def load_pack(db: Session, project_id: str, execution_id: str) -> ExecutionPlan | None:
    """Load an ExecutionPlan pack by execution_id."""
    from ...db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PACK_CATEGORY,
            ProjectTraitRow.key == execution_id,
        )
        .first()
    )
    if not row:
        return None
    try:
        data = json.loads(row.value)
        return ExecutionPlan(**data)
    except Exception as exc:
        logger.error("Failed to load execution pack %s: %s", execution_id, exc)
        return None


def list_packs(db: Session, project_id: str, active_only: bool = False) -> list[ExecutionPlan]:
    """List execution packs for a project."""
    from ...db import ProjectTraitRow

    rows = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PACK_CATEGORY,
        )
        .order_by(ProjectTraitRow.id.desc())
        .all()
    )
    packs: list[ExecutionPlan] = []
    for row in rows:
        try:
            data = json.loads(row.value)
            pack = ExecutionPlan(**data)
            if active_only and pack.is_terminal:
                continue
            packs.append(pack)
        except Exception:
            continue
    return packs


def delete_pack(db: Session, project_id: str, execution_id: str) -> bool:
    """Delete an execution pack (rare — used for cleanup)."""
    from ...db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PACK_CATEGORY,
            ProjectTraitRow.key == execution_id,
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
