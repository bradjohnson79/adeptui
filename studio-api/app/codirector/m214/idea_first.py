"""Idea-first Storyteller discovery + format guidance + progressive depth."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .kinds import PROJECT_STAGES
from .store import M214Store

_FORMAT_GUIDANCE = {
    "idea": "Capture the spark: who, where, emotional want. Defer format until direction emerges.",
    "discovery": "Guided discovery: 2-4 high-impact questions; propose format options without locking.",
    "treatment": "Shape a treatment: logline, tone, acts. Keep emotional arc first.",
    "screenplay": "Deepen into scene pages only after emotional direction is confirmed.",
    "previs": "Translate approved direction into visual/sonic previs cards.",
    "production": "Department brief sync; one primary next action for the user.",
    "post": "Review media, sound, and continuity against the UnifiedSceneBrief.",
    "delivery": "Final review checklist; no silent export without Approval Center.",
}


def propose_from_idea(
    db: Session,
    *,
    project_id: str,
    idea: str,
    preferred_format: str = "",
) -> dict[str, Any]:
    stage = "discovery"
    M214Store.upsert_stage(db, project_id, stage, {"idea": idea, "preferredFormat": preferred_format})
    questions = [
        "Whose emotional want drives this moment?",
        "What changes for them by the end of the scene?",
        "Should this feel intimate, epic, or somewhere between?",
    ]
    if preferred_format:
        questions.append(f"Confirm format '{preferred_format}' or explore alternatives?")
    else:
        questions.append("Do you want a short scene, treatment, or full short film?")
    M214Store.log_capability(
        db,
        capability_id="codirector.project.propose",
        action="idea_first",
        project_id=project_id,
        payload={"stage": stage},
    )
    return {
        "projectId": project_id,
        "stage": stage,
        "mode": "guided",
        "idea": idea,
        "formatGuidance": _FORMAT_GUIDANCE[stage],
        "progressiveDepth": "shallow",
        "questions": questions[:4],
        "honesty": "mocked",
        "note": "Proposals only until Storyteller handoff is approved.",
        "stages": list(PROJECT_STAGES),
    }


def advance_depth(db: Session, project_id: str, stage: str) -> dict[str, Any]:
    if stage not in PROJECT_STAGES:
        raise ValueError(f"Unknown stage {stage}")
    M214Store.upsert_stage(db, project_id, stage)
    depth = "shallow" if stage in {"idea", "discovery"} else "medium" if stage in {"treatment", "screenplay"} else "deep"
    return {
        "projectId": project_id,
        "stage": stage,
        "progressiveDepth": depth,
        "formatGuidance": _FORMAT_GUIDANCE.get(stage, ""),
        "honesty": "mocked",
    }
