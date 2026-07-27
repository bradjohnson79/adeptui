"""Bridge M2.11 / bible / vision / continuity signals into M2.12 candidate lessons."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .critique import critique_action
from .lessons import LessonStore


def bridge_decision_rejection(
    db: Session,
    *,
    project_id: str,
    decision: dict[str, Any],
    note: str = "",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    action = {
        "decisionId": decision.get("id"),
        "summary": decision.get("rationale") or decision.get("recommendation") or "",
        "recommendation": decision.get("recommendation") or "",
        "specialistId": decision.get("specialistId"),
        "confidence": decision.get("confidence"),
    }
    outcome = {
        "status": "rejected",
        "verified": True,
        "humanRejected": True,
        "rejected": True,
        "classified": True,
        "mistakeClass": _guess_class_from_category(decision.get("category")),
        "message": note or f"Decision {decision.get('id')} rejected",
        "confidence": decision.get("confidence") or 0.5,
    }
    traces = []
    return critique_action(
        db,
        project_id=project_id,
        action=action,
        outcome=outcome,
        traces=traces,
        layer="project",
        session_id=session_id,
    )


def bridge_bible_proposal_decision(
    db: Session,
    *,
    project_id: str,
    proposal_id: str,
    approved: bool,
    note: str = "",
    session_id: Optional[str] = None,
) -> dict[str, Any] | None:
    if approved:
        # Approvals are success signals; optional retrospective only.
        return critique_action(
            db,
            project_id=project_id,
            action={"summary": f"Bible proposal {proposal_id} approved", "decisionId": proposal_id},
            outcome={
                "status": "success",
                "verified": True,
                "classified": True,
                "mistakeClass": "success",
                "message": note or "Bible proposal approved",
            },
            layer="project",
            session_id=session_id,
            create_lesson=False,
        )
    return critique_action(
        db,
        project_id=project_id,
        action={"summary": f"Bible proposal {proposal_id} rejected", "decisionId": proposal_id},
        outcome={
            "status": "rejected",
            "verified": True,
            "humanRejected": True,
            "rejected": True,
            "classified": True,
            "mistakeClass": "bible",
            "message": note or "Bible proposal rejected",
            "lessonText": note or "Respect bible approval boundaries; do not re-propose rejected mutations without revision.",
        },
        layer="project",
        session_id=session_id,
    )


def bridge_vision_reject(
    db: Session,
    *,
    project_id: str,
    report_id: str,
    note: str = "",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return critique_action(
        db,
        project_id=project_id,
        action={"summary": f"Vision report {report_id} rejected", "decisionId": report_id},
        outcome={
            "status": "rejected",
            "verified": True,
            "humanRejected": True,
            "rejected": True,
            "classified": True,
            "mistakeClass": "camera",
            "message": note or "Vision validation rejected",
            "lessonText": note
            or "Tighten visual continuity / framing against bible references before re-submitting.",
        },
        layer="project",
        session_id=session_id,
    )


def bridge_continuity_dismissal(
    db: Session,
    *,
    project_id: str,
    suggestion_id: str,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return critique_action(
        db,
        project_id=project_id,
        action={"summary": f"Continuity suggestion {suggestion_id} dismissed"},
        outcome={
            "status": "dismissed",
            "verified": True,
            "classified": True,
            "mistakeClass": "continuity",
            "message": "User dismissed continuity suggestion",
            "lessonText": (
                f"User dismissed continuity suggestion {suggestion_id}; "
                "treat similar heuristic as lower priority for this project."
            ),
            "confidence": 0.55,
        },
        layer="project",
        session_id=session_id,
    )


def promote_project_lesson_into_learning_py(
    db: Session,
    *,
    project_id: str,
    lesson: dict[str, Any],
    category: str = "continuity",
) -> dict[str, Any] | None:
    """Optional bridge: active project-layer lesson -> learning.py LearnedItem."""

    from ...db import Project
    from ...learning import LearnedItem, dumps_learning, parse_learning

    if lesson.get("layer") != "project" or lesson.get("status") != "active":
        return None
    project = db.get(Project, project_id)
    if project is None:
        return None
    state = parse_learning(
        getattr(project, "learning_json", "") or "",
        getattr(project, "learning_enabled_json", "") or "",
    )
    item_id = f"m212:{lesson['id'][:8]}"
    if any(i.id == item_id for i in state.items):
        return {"alreadyPresent": True, "id": item_id}
    # Map unknown categories into a safe default.
    from ...learning import ALL_CATEGORIES

    cat = category if category in ALL_CATEGORIES else "continuity"
    state.items.append(
        LearnedItem(id=item_id, category=cat, text=str(lesson.get("text") or "")[:500], enabled=True)
    )
    lj, ej = dumps_learning(state)
    project.learning_json = lj
    project.learning_enabled_json = ej
    db.commit()
    return {"id": item_id, "category": cat, "text": lesson.get("text")}


def collect_m211_reject_signals(db: Session, project_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Best-effort scan of rejected M2.11 decisions for bridging."""

    try:
        from ..m211.decisions import DecisionRecordStore
    except Exception:
        return []
    rows = DecisionRecordStore.list_for_project(db, project_id, limit=limit)
    return [r for r in rows if str(r.get("approvalStatus") or "").lower() == "rejected"]


def _guess_class_from_category(category: Optional[str]) -> str:
    c = (category or "").lower()
    mapping = {
        "continuity": "continuity",
        "bible": "bible",
        "director": "camera",
        "camera": "camera",
        "cinematographer": "camera",
        "sound": "sfx_timing",
        "music": "music",
        "editor": "timeline",
        "qa": "test_failure",
    }
    for key, val in mapping.items():
        if key in c:
            return val
    return "structured_output"


def active_lessons_as_learning_block(lessons: list[dict[str, Any]]) -> str:
    lines = []
    for lesson in lessons:
        if lesson.get("status") != "active":
            continue
        layer = lesson.get("layer") or "project"
        cls = lesson.get("mistakeClass") or "general"
        lines.append(f"- [{layer}/{cls}] {lesson.get('text')}")
    if not lines:
        return ""
    return "Active adaptive lessons (human-approved where required):\n" + "\n".join(lines)
