"""Public PlanService façade for Wave 4 durable production plans."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from . import store
from .commands import PlanCommandService
from .readiness import evaluate_readiness
from .schemas import PlanCommandResult, PlanReadinessReport, PlanValidationResult, ProductionPlan
from .validation import validate_plan


class PlanService:
    """Canonical production plan API used by tools, routers, and intelligence adapter."""

    create_draft = staticmethod(PlanCommandService.create_draft)
    propose = staticmethod(PlanCommandService.propose)
    approve = staticmethod(PlanCommandService.approve)
    reject = staticmethod(PlanCommandService.reject)
    revise = staticmethod(PlanCommandService.revise)
    pause = staticmethod(PlanCommandService.pause)
    resume = staticmethod(PlanCommandService.resume)
    cancel = staticmethod(PlanCommandService.cancel)
    archive = staticmethod(PlanCommandService.archive)
    resolve_blocker = staticmethod(PlanCommandService.resolve_blocker)

    @staticmethod
    def get(db: Session, project_id: str, plan_id: str) -> ProductionPlan:
        store.require_project(db, project_id)
        return store.row_to_plan(store.get_head(db, project_id, plan_id))

    @staticmethod
    def list(db: Session, project_id: str, *, limit: int = 50) -> list[ProductionPlan]:
        store.require_project(db, project_id)
        return [store.row_to_plan(r) for r in store.list_heads(db, project_id, limit=limit)]

    @staticmethod
    def get_version(db: Session, project_id: str, plan_id: str, version: int) -> ProductionPlan:
        return store.get_version_snapshot(db, project_id, plan_id, version)

    @staticmethod
    def list_versions(db: Session, project_id: str, plan_id: str) -> list[dict[str, Any]]:
        rows = store.list_versions(db, project_id, plan_id)
        return [
            {
                "planId": r.plan_id,
                "version": r.version,
                "state": r.state,
                "revisionReason": r.revision_reason,
                "parentVersionId": r.parent_version_id,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    @staticmethod
    def list_events(db: Session, project_id: str, plan_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in store.list_events(db, project_id, plan_id, limit=limit)]

    @staticmethod
    def validate(db: Session, project_id: str, plan_id: str) -> PlanValidationResult:
        plan = PlanService.get(db, project_id, plan_id)
        return validate_plan(plan)

    @staticmethod
    def get_readiness(db: Session, project_id: str, plan_id: str) -> PlanReadinessReport:
        plan = PlanService.get(db, project_id, plan_id)
        return evaluate_readiness(db, plan)

    @staticmethod
    def active_plan(db: Session, project_id: str) -> Optional[ProductionPlan]:
        store.require_project(db, project_id)
        row = store.find_active(db, project_id)
        return store.row_to_plan(row) if row else None

    @staticmethod
    def session_fields(db: Session, project_id: Optional[str]) -> dict[str, Any]:
        if not project_id:
            return {
                "activePlanId": None,
                "activePlanVersion": None,
                "activePlanState": None,
                "activeStepId": None,
                "planReadiness": None,
                "openPlanBlockers": [],
                "lastPlanCommand": None,
            }
        try:
            plan = PlanService.active_plan(db, project_id)
        except Exception:
            plan = None
        if not plan:
            return {
                "activePlanId": None,
                "activePlanVersion": None,
                "activePlanState": None,
                "activeStepId": None,
                "planReadiness": None,
                "openPlanBlockers": [],
                "lastPlanCommand": None,
            }
        open_blockers = [b.blockerId for b in plan.blockers if b.state == "open"]
        return {
            "activePlanId": plan.planId,
            "activePlanVersion": plan.version,
            "activePlanState": plan.state,
            "activeStepId": plan.activeStepId,
            "planReadiness": plan.capabilitySnapshot.readiness if plan.capabilitySnapshot else None,
            "openPlanBlockers": open_blockers,
            "lastPlanCommand": None,
            "activeProductionPlan": {
                "id": plan.planId,
                "title": plan.title,
                "state": plan.state,
                "version": plan.version,
                "unapproved": plan.unapproved,
            },
        }
