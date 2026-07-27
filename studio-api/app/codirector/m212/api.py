"""FastAPI routes for Co-Director M2.12 Adaptive Learning."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from . import calibration as calibration_mod
from . import strategy as strategy_mod
from .bridge import (
    bridge_bible_proposal_decision,
    bridge_continuity_dismissal,
    bridge_decision_rejection,
    bridge_vision_reject,
    collect_m211_reject_signals,
)
from .critique import create_retrospective, critique_action, list_retrospectives
from .flags import FLAG_NAME, adaptive_learning_enabled
from .lessons import LessonStore
from .promote import promote_lesson, retire_lesson, rollback_lesson
from .regression import attach_regression_suite, run_regression_check
from .safety import (
    AdaptiveLearningSafetyError,
    assert_manifest_unchanged,
    assert_path_writable_by_learning,
    safety_contract,
)

router = APIRouter(prefix="/m212", tags=["codirector-m212"])


def _flag(name: str = FLAG_NAME) -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, name, False))


def _require(name: str = FLAG_NAME) -> None:
    if _flag(name):
        return
    raise HTTPException(
        status_code=404,
        detail="M2.12 adaptive learning capability is not enabled.",
    )


def _http_safety(exc: AdaptiveLearningSafetyError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class CritiqueBody(BaseModel):
    projectId: str
    action: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    layer: str = "project"
    sessionId: Optional[str] = None
    createLesson: bool = True


class RetrospectiveBody(BaseModel):
    projectId: str
    summary: str = ""
    action: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    sessionId: Optional[str] = None
    traceId: Optional[str] = None
    layer: str = "project"


class PromoteBody(BaseModel):
    actor: str = "user"
    role: str = "user"
    note: str = ""
    intoLearningPy: bool = True


class RollbackBody(BaseModel):
    actor: str = "user"
    note: str = ""


class BridgeDecisionBody(BaseModel):
    projectId: str
    decision: dict[str, Any]
    note: str = ""
    sessionId: Optional[str] = None


class BridgeProposalBody(BaseModel):
    projectId: str
    proposalId: str
    approved: bool = False
    note: str = ""
    sessionId: Optional[str] = None


class BridgeVisionBody(BaseModel):
    projectId: str
    reportId: str
    note: str = ""
    sessionId: Optional[str] = None


class BridgeContinuityBody(BaseModel):
    projectId: str
    suggestionId: str
    sessionId: Optional[str] = None


class CalibrationBody(BaseModel):
    projectId: Optional[str] = None
    predictedConfidence: float
    observedOutcome: str
    context: dict[str, Any] = Field(default_factory=dict)


class StrategyCreateBody(BaseModel):
    name: str
    pack: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    activate: bool = False


class ForbiddenWriteProbeBody(BaseModel):
    path: str


@router.get("/status")
async def m212_status() -> dict[str, Any]:
    _require()
    digest = assert_manifest_unchanged()
    return {
        "enabled": adaptive_learning_enabled(),
        "flag": FLAG_NAME,
        "safety": safety_contract(),
        "manifestSha256": digest,
        "layers": ["session", "project", "user", "system"],
        "evolutionMode": "structured_lessons_and_strategy_packs",
        "fineTuning": False,
        "autonomousSourceRewrite": False,
    }


@router.get("/safety")
async def m212_safety() -> dict[str, Any]:
    _require()
    return safety_contract()


@router.post("/safety/probe-forbidden-write")
async def m212_probe_forbidden_write(body: ForbiddenWriteProbeBody) -> dict[str, Any]:
    """Test helper: learning module must refuse Manifest/lock paths."""

    _require()
    try:
        assert_path_writable_by_learning(body.path)
        return {"allowed": True, "path": body.path}
    except AdaptiveLearningSafetyError as exc:
        return {"allowed": False, "path": body.path, "reason": str(exc)}


@router.post("/critique")
async def m212_critique(body: CritiqueBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return critique_action(
            db,
            project_id=body.projectId,
            action=body.action,
            outcome=body.outcome,
            traces=body.traces,
            layer=body.layer,
            session_id=body.sessionId,
            create_lesson=body.createLesson,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/retrospectives")
async def m212_retrospective(body: RetrospectiveBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        critique = critique_action(
            db,
            project_id=body.projectId,
            action=body.action,
            outcome=body.outcome,
            traces=body.traces,
            layer=body.layer,
            session_id=body.sessionId,
            create_lesson=True,
        )
        return create_retrospective(
            db,
            project_id=body.projectId,
            summary=body.summary or critique.get("summary") or "",
            critique=critique,
            session_id=body.sessionId,
            trace_id=body.traceId,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.get("/retrospectives")
async def m212_list_retrospectives(
    projectId: str = Query(...),
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    rows = list_retrospectives(db, projectId, limit=limit)
    return {"projectId": projectId, "retrospectives": rows, "count": len(rows)}


@router.get("/lessons")
async def m212_list_lessons(
    projectId: Optional[str] = None,
    layer: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    rows = LessonStore.list_lessons(
        db, project_id=projectId, layer=layer, status=status, limit=limit
    )
    return {"lessons": rows, "count": len(rows)}


@router.get("/lessons/{lesson_id}")
async def m212_get_lesson(lesson_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    row = LessonStore.get(db, lesson_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return row


@router.get("/lessons/{lesson_id}/versions")
async def m212_lesson_versions(
    lesson_id: str, limit: int = 50, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    rows = LessonStore.versions(db, lesson_id, limit=limit)
    return {"lessonId": lesson_id, "versions": rows, "count": len(rows)}


@router.post("/lessons/{lesson_id}/regression")
async def m212_attach_and_run_regression(
    lesson_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        attach_regression_suite(db, lesson_id)
        return run_regression_check(db, lesson_id)
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/lessons/{lesson_id}/promote")
async def m212_promote(
    lesson_id: str, body: PromoteBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return promote_lesson(
            db,
            lesson_id,
            actor=body.actor,
            role=body.role,
            note=body.note,
            into_learning_py=body.intoLearningPy,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/lessons/{lesson_id}/rollback")
async def m212_rollback(
    lesson_id: str, body: RollbackBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return rollback_lesson(db, lesson_id, actor=body.actor, note=body.note)
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/lessons/{lesson_id}/retire")
async def m212_retire(
    lesson_id: str, body: RollbackBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return retire_lesson(db, lesson_id, actor=body.actor, note=body.note)
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/bridge/decision-reject")
async def m212_bridge_decision(body: BridgeDecisionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return bridge_decision_rejection(
            db,
            project_id=body.projectId,
            decision=body.decision,
            note=body.note,
            session_id=body.sessionId,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/bridge/bible-proposal")
async def m212_bridge_proposal(body: BridgeProposalBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        out = bridge_bible_proposal_decision(
            db,
            project_id=body.projectId,
            proposal_id=body.proposalId,
            approved=body.approved,
            note=body.note,
            session_id=body.sessionId,
        )
        return out or {}
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/bridge/vision-reject")
async def m212_bridge_vision(body: BridgeVisionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return bridge_vision_reject(
            db,
            project_id=body.projectId,
            report_id=body.reportId,
            note=body.note,
            session_id=body.sessionId,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/bridge/continuity-dismiss")
async def m212_bridge_continuity(
    body: BridgeContinuityBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return bridge_continuity_dismissal(
            db,
            project_id=body.projectId,
            suggestion_id=body.suggestionId,
            session_id=body.sessionId,
        )
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.get("/bridge/m211-rejects")
async def m212_m211_rejects(
    projectId: str = Query(...), limit: int = 20, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    rows = collect_m211_reject_signals(db, projectId, limit=limit)
    return {"projectId": projectId, "rejectedDecisions": rows, "count": len(rows)}


@router.post("/calibration")
async def m212_calibration(body: CalibrationBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return calibration_mod.record_sample(
        db,
        predicted_confidence=body.predictedConfidence,
        observed_outcome=body.observedOutcome,
        project_id=body.projectId,
        context=body.context,
    )


@router.get("/calibration")
async def m212_calibration_list(
    projectId: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    rows = calibration_mod.list_samples(db, project_id=projectId, limit=limit)
    health = calibration_mod.calibration_health(db, project_id=projectId)
    return {"samples": rows, "count": len(rows), "health": health}


@router.get("/strategy")
async def m212_strategy_list(db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    packs = strategy_mod.list_packs(db)
    active = strategy_mod.get_active_pack(db)
    return {"packs": packs, "active": active, "count": len(packs)}


@router.post("/strategy")
async def m212_strategy_create(body: StrategyCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    pack = strategy_mod.create_pack(
        db, name=body.name, pack=body.pack or None, version=body.version
    )
    if body.activate:
        pack = strategy_mod.activate_pack(db, pack["id"])
    return pack


@router.post("/strategy/{pack_id}/activate")
async def m212_strategy_activate(pack_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return strategy_mod.activate_pack(db, pack_id)
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.post("/strategy/{pack_id}/rollback")
async def m212_strategy_rollback(pack_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return strategy_mod.rollback_pack(db, pack_id)
    except AdaptiveLearningSafetyError as exc:
        raise _http_safety(exc) from exc


@router.get("/dashboard")
async def m212_dashboard(
    projectId: str = Query(...), db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    lessons = LessonStore.list_lessons(db, project_id=projectId, limit=200)
    pending = [l for l in lessons if l.get("status") == "candidate"]
    active = [l for l in lessons if l.get("status") == "active"]
    rolled = [l for l in lessons if l.get("status") == "rolled_back"]
    health = calibration_mod.calibration_health(db, project_id=projectId)
    retros = list_retrospectives(db, projectId, limit=10)
    active_pack = strategy_mod.get_active_pack(db)
    return {
        "projectId": projectId,
        "pendingApprovals": pending,
        "activeLessons": active,
        "recentRollbacks": rolled[:20],
        "calibrationHealth": health,
        "retrospectives": retros,
        "activeStrategyPack": active_pack,
        "safety": {
            "fineTuning": False,
            "manifestSha256": assert_manifest_unchanged(),
            "systemAutoActivate": False,
        },
    }
