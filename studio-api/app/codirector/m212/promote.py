"""Promotion gates, rollback, and learning.py optional project bridge."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .bridge import promote_project_lesson_into_learning_py
from .lessons import LessonStore
from .regression import require_regression_passed, run_regression_check
from .safety import AdaptiveLearningSafetyError, assert_no_system_auto_activate

# evidence threshold before promote
MIN_EVIDENCE_SCORE = 0.4
MIN_CONFIDENCE = 0.35

LAYER_APPROVAL_ROLES = {
    "session": ("policy", "system", "user"),
    "project": ("user", "human", "producer"),
    "user": ("user", "human"),
    "system": ("product", "policy", "admin"),
}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def promote_lesson(
    db: Session,
    lesson_id: str,
    *,
    actor: str,
    role: str,
    note: str = "",
    into_learning_py: bool = True,
    run_regression: bool = True,
) -> dict[str, Any]:
    lesson = LessonStore.get(db, lesson_id)
    if lesson is None:
        raise AdaptiveLearningSafetyError("Lesson not found")
    layer = str(lesson.get("layer") or "")
    assert_no_system_auto_activate(layer, auto=False)

    if lesson.get("status") not in ("candidate", "rolled_back"):
        raise AdaptiveLearningSafetyError(
            f"Cannot promote lesson in status={lesson.get('status')}"
        )

    if float(lesson.get("evidenceScore") or 0.0) < MIN_EVIDENCE_SCORE:
        raise AdaptiveLearningSafetyError(
            f"Evidence score below threshold ({MIN_EVIDENCE_SCORE})"
        )
    if float(lesson.get("confidence") or 0.0) < MIN_CONFIDENCE:
        raise AdaptiveLearningSafetyError(
            f"Confidence below threshold ({MIN_CONFIDENCE})"
        )

    allowed_roles = LAYER_APPROVAL_ROLES.get(layer, ())
    if role not in allowed_roles:
        raise AdaptiveLearningSafetyError(
            f"Role '{role}' cannot approve layer '{layer}'. Need one of {allowed_roles}"
        )
    if layer == "system" and role not in ("product", "policy", "admin"):
        raise AdaptiveLearningSafetyError("System-layer requires Product/policy approval")

    if run_regression:
        reg = run_regression_check(db, lesson_id, actor=actor)
        if not reg["passed"]:
            raise AdaptiveLearningSafetyError("Regression check failed; cannot activate")
        lesson = reg["lesson"]
    else:
        require_regression_passed(lesson)

    approval = {
        "actor": actor,
        "role": role,
        "note": note,
        "approvedAt": _now_iso(),
        "layer": layer,
    }
    updated = LessonStore.update_fields(
        db,
        lesson_id,
        fields={
            "status": "active",
            "approval": approval,
            "promotedAt": _now_iso(),
            "retiredAt": None,
        },
        actor=actor,
        action="promote",
        note=note or f"promoted by {actor} ({role})",
        bump_version=True,
    )
    assert updated is not None

    learning_bridge = None
    if into_learning_py and layer == "project" and updated.get("projectId"):
        cat = _category_for_mistake(updated.get("mistakeClass") or "")
        learning_bridge = promote_project_lesson_into_learning_py(
            db,
            project_id=updated["projectId"],
            lesson=updated,
            category=cat,
        )

    return {"lesson": updated, "learningBridge": learning_bridge}


def rollback_lesson(
    db: Session,
    lesson_id: str,
    *,
    actor: str,
    note: str = "",
) -> dict[str, Any]:
    """Disable bad lesson without deleting history (audit via versions)."""

    lesson = LessonStore.get(db, lesson_id)
    if lesson is None:
        raise AdaptiveLearningSafetyError("Lesson not found")
    if lesson.get("status") == "candidate":
        # Rejecting a candidate is retire, not rollback.
        updated = LessonStore.update_fields(
            db,
            lesson_id,
            fields={"status": "retired", "retiredAt": _now_iso()},
            actor=actor,
            action="retire",
            note=note or "candidate rejected",
            bump_version=True,
        )
        return {"lesson": updated, "action": "retire"}

    updated = LessonStore.update_fields(
        db,
        lesson_id,
        fields={"status": "rolled_back", "retiredAt": _now_iso()},
        actor=actor,
        action="rollback",
        note=note or f"rolled back by {actor}",
        bump_version=True,
    )
    return {"lesson": updated, "action": "rollback"}


def retire_lesson(
    db: Session,
    lesson_id: str,
    *,
    actor: str,
    note: str = "",
) -> dict[str, Any]:
    lesson = LessonStore.get(db, lesson_id)
    if lesson is None:
        raise AdaptiveLearningSafetyError("Lesson not found")
    updated = LessonStore.update_fields(
        db,
        lesson_id,
        fields={"status": "retired", "retiredAt": _now_iso()},
        actor=actor,
        action="retire",
        note=note or f"retired by {actor}",
        bump_version=True,
    )
    return {"lesson": updated}


def _category_for_mistake(mistake_class: str) -> str:
    mapping = {
        "continuity": "continuity",
        "camera": "camera",
        "music": "pacing",
        "sfx_timing": "motion",
        "bible": "profiles",
        "timeline": "coverage",
        "structured_output": "prompts",
        "provider": "engines",
        "export": "render",
    }
    return mapping.get(mistake_class, "continuity")
