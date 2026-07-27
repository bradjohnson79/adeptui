"""Production-plan visualization (idea -> delivery stages)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .kinds import PROJECT_STAGES
from .store import M214Store


def production_plan_view(db: Session, project_id: str) -> dict[str, Any]:
    stage_info = M214Store.get_stage(db, project_id)
    current = stage_info.get("stage") or "idea"
    stages = []
    reached = True
    for s in PROJECT_STAGES:
        if s == current:
            status = "current"
            reached = False
        elif reached:
            status = "complete"
        else:
            status = "upcoming"
        stages.append({"id": s, "status": status})
    return {
        "projectId": project_id,
        "currentStage": current,
        "stages": stages,
        "path": "idea -> discovery -> treatment -> screenplay -> previs -> production -> post -> delivery",
        "honesty": "scaffolded",
    }
