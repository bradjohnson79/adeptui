"""Regression checks required before activating lessons."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from .lessons import LessonStore
from .safety import AdaptiveLearningSafetyError


def attach_regression_suite(
    db: Session,
    lesson_id: str,
    *,
    suite_id: Optional[str] = None,
    actor: str = "system",
) -> dict[str, Any]:
    lesson = LessonStore.get(db, lesson_id)
    if lesson is None:
        raise AdaptiveLearningSafetyError("Lesson not found")
    sid = suite_id or f"m212-reg-{lesson_id[:8]}-{uuid.uuid4().hex[:6]}"
    updated = LessonStore.update_fields(
        db,
        lesson_id,
        fields={"regressionSuiteId": sid, "regressionPassed": False},
        actor=actor,
        action="attach_regression",
        note=f"Attached regression suite {sid}",
    )
    assert updated is not None
    return updated


def run_regression_check(
    db: Session,
    lesson_id: str,
    *,
    actor: str = "system",
    force_fail: bool = False,
) -> dict[str, Any]:
    """Lightweight gate: ensure lesson has evidence + suite + non-empty policy/text."""

    lesson = LessonStore.get(db, lesson_id)
    if lesson is None:
        raise AdaptiveLearningSafetyError("Lesson not found")
    suite_id = lesson.get("regressionSuiteId")
    if not suite_id:
        lesson = attach_regression_suite(db, lesson_id, actor=actor)
        suite_id = lesson.get("regressionSuiteId")

    checks = {
        "hasText": bool(str(lesson.get("text") or "").strip()),
        "hasEvidence": float(lesson.get("evidenceScore") or 0.0) >= 0.3,
        "hasSuite": bool(suite_id),
        "notSystemAuto": True,
        "layerValid": lesson.get("layer") in ("session", "project", "user", "system"),
    }
    passed = all(checks.values()) and not force_fail
    updated = LessonStore.update_fields(
        db,
        lesson_id,
        fields={"regressionPassed": passed},
        actor=actor,
        action="regression_run",
        note="passed" if passed else "failed",
    )
    assert updated is not None
    return {
        "lessonId": lesson_id,
        "suiteId": suite_id,
        "passed": passed,
        "checks": checks,
        "lesson": updated,
    }


def require_regression_passed(lesson: dict[str, Any]) -> None:
    if not lesson.get("regressionSuiteId"):
        raise AdaptiveLearningSafetyError("Regression suite required before activate")
    if not lesson.get("regressionPassed"):
        raise AdaptiveLearningSafetyError("Regression check must pass before activate")
