"""Pending execution store — persists a pending execution across conversational turns.

Spec §2 (Execution State Machine): "This state must survive across conversational
turns in the active Co-Director session. Do not infer pending execution only from
previous natural-language messages. Use explicit structured execution state."

Spec §3 (Pending Execution Contract): structured data for a pending operation that
has NOT yet dispatched — it is awaiting confirmation or required input.

Spec §4 (Confirmation Resolution): when state == AWAITING_CONFIRMATION and the
user responds affirmatively, transition directly to READY_TO_DISPATCH and dispatch.

Stored as a JSON value in a `ProjectTraitRow` with:
- category: "codirector_pending_execution"
- key: the project_id (one active pending per project)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PENDING_CATEGORY = "codirector_pending_execution"
PENDING_KEY = "active"


# Execution state machine (spec §2).
PENDING_STATES = (
    "IDLE",
    "PLANNING",
    "AWAITING_REQUIRED_INPUT",
    "AWAITING_CONFIRMATION",
    "READY_TO_DISPATCH",
    "EXECUTING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingExecution(BaseModel):
    """Structured pending execution data (spec §3).

    Persisted across conversational turns so a user's "Yes, proceed" can resolve
    the pending operation WITHOUT re-running general conversational reasoning.
    """

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    capability: str = ""
    project_id: str = ""
    intent: str = "EXECUTION"

    # The unified_intent snapshot — used to re-dispatch on confirmation.
    # Stored as a dict so it survives schema evolution across turns.
    unified_intent: dict[str, Any] = Field(default_factory=dict)

    # Requested parameters (spec §6).
    requested_parameters: dict[str, Any] = Field(default_factory=dict)

    # Resolved context — attachments, references, scene, character, style.
    resolved_context: dict[str, Any] = Field(default_factory=dict)

    attachment_asset_ids: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    requested_output_count: int = 1

    # Required information that is still missing (spec §6, §31).
    missing_required_fields: list[str] = Field(default_factory=list)

    # Whether the capability's approval policy requires confirmation (spec §50).
    confirmation_required: bool = False

    # The question Co-Director asked, if any (for context on the confirmation turn).
    confirmation_question: str = ""

    state: str = "IDLE"

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()


def save_pending(db: Session, project_id: str, pending: PendingExecution) -> PendingExecution:
    """Persist a pending execution for a project (one active per project)."""
    from ...db import ProjectTraitRow

    pending.project_id = project_id
    pending.touch()

    existing = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PENDING_CATEGORY,
            ProjectTraitRow.key == PENDING_KEY,
        )
        .first()
    )

    payload = json.dumps(pending.model_dump(mode="json"))

    if existing:
        existing.value = payload
        existing.provenance = "CODEX_PENDING_EXECUTION"
    else:
        row = ProjectTraitRow(
            id=str(uuid4()),
            project_id=project_id,
            category=PENDING_CATEGORY,
            key=PENDING_KEY,
            value=payload,
            provenance="CODEX_PENDING_EXECUTION",
            created_at=_now(),
        )
        db.add(row)

    db.commit()
    return pending


def get_active_pending(db: Session, project_id: str) -> Optional[PendingExecution]:
    """Return the active pending execution for a project, or None."""
    from ...db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PENDING_CATEGORY,
            ProjectTraitRow.key == PENDING_KEY,
        )
        .first()
    )
    if not row:
        return None
    try:
        data = json.loads(row.value)
        return PendingExecution(**data)
    except Exception as exc:
        logger.error("Failed to load pending execution for %s: %s", project_id, exc)
        return None


def clear_pending(db: Session, project_id: str) -> None:
    """Clear the active pending execution for a project."""
    from ...db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == PENDING_CATEGORY,
            ProjectTraitRow.key == PENDING_KEY,
        )
        .first()
    )
    if row:
        db.delete(row)
        db.commit()


def transition_state(db: Session, project_id: str, pending: PendingExecution, new_state: str) -> PendingExecution:
    """Transition a pending execution to a new state and persist."""
    if new_state not in PENDING_STATES:
        raise ValueError(f"Invalid pending execution state: {new_state}")
    pending.state = new_state
    return save_pending(db, project_id, pending)
