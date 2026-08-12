"""Closed plan command service with atomic head+version+event+idempotency commits."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorProductionPlan
from ..errors import (
    PLAN_BLOCKER_NOT_FOUND,
    PLAN_VALIDATION_FAILED,
    PLAN_VERSION_CONFLICT,
    CoDirectorError,
)
from . import store
from .dependencies import compute_step_readiness
from .events import make_event
from .readiness import annotate_step_availability, build_capability_snapshot
from .schemas import (
    ActorRef,
    PlanApprovalRequirement,
    PlanCommandResult,
    PlanSource,
    PlanWarning,
    ProductionPlan,
    ProductionPlanBlocker,
    ProductionPlanStep,
)
from .state_machine import assert_plan_transition
from .validation import validate_plan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_payload(result: PlanCommandResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


class PlanCommandService:
    """Execute plan-management commands inside a single DB transaction."""

    @staticmethod
    def _check_idempotency(db: Session, project_id: str, request_id: str) -> Optional[PlanCommandResult]:
        prior = store.get_idempotency(db, project_id, request_id)
        if not prior:
            return None
        plan_data = prior.get("plan") or prior
        try:
            plan = ProductionPlan.model_validate(plan_data if "planId" in plan_data else prior.get("plan"))
        except Exception:
            plan = ProductionPlan.model_validate(prior["plan"])
        event = None
        if prior.get("event"):
            from .schemas import PlanEvent

            event = PlanEvent.model_validate(prior["event"])
        return PlanCommandResult(plan=plan, event=event, duplicated=True)

    @staticmethod
    def _commit_atomic(
        db: Session,
        *,
        project_id: str,
        request_id: str,
        command: str,
        plan: ProductionPlan,
        event_type: str,
        summary: str,
        changes: dict[str, Any],
        row: Optional[CoDirectorProductionPlan] = None,
        actor_type: str = "codirector",
        actor_id: Optional[str] = None,
    ) -> PlanCommandResult:
        event = make_event(
            plan_id=plan.planId,
            project_id=project_id,
            plan_version=plan.version,
            event_type=event_type,
            request_id=request_id,
            summary=summary,
            changes=changes,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if row is None:
            row = CoDirectorProductionPlan(
                id=plan.planId,
                project_id=project_id,
                request_id=request_id,
                playbook_id=plan.playbookId or "",
                title=plan.title,
                status=plan.state,
                plan_json="{}",
                visual_validation_pending=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                version=plan.version,
            )
            db.add(row)
        store.apply_head_fields(row, plan)
        store.add_version_row(db, plan)
        store.add_event_row(db, event)
        result = PlanCommandResult(plan=plan, event=event, duplicated=False)
        store.add_idempotency_row(
            db,
            project_id=project_id,
            request_id=request_id,
            command=command,
            plan_id=plan.planId,
            result=_result_payload(result),
        )
        db.commit()
        db.refresh(row)
        return result

    @staticmethod
    def create_draft(
        db: Session,
        *,
        project_id: str,
        request_id: str,
        title: str,
        objective: str = "",
        description: str = "",
        steps: Optional[list[dict[str, Any]]] = None,
        conversation_id: Optional[str] = None,
        actor_type: str = "codirector",
        source_type: str = "conversation",
        source_id: Optional[str] = None,
        plan_id: Optional[str] = None,
    ) -> PlanCommandResult:
        store.require_project(db, project_id)
        if request_id:
            dup = PlanCommandService._check_idempotency(db, project_id, request_id)
            if dup:
                return dup

        plan_id = (plan_id or "").strip() or str(uuid.uuid4())
        now = _now()
        step_models: list[ProductionPlanStep] = []
        for i, raw in enumerate(steps or []):
            sid = str(raw.get("stepId") or f"step-{i+1}")
            step_models.append(
                ProductionPlanStep(
                    stepId=sid,
                    planId=plan_id,
                    order=int(raw.get("order") or i + 1),
                    title=str(raw.get("title") or f"Step {i+1}"),
                    description=str(raw.get("description") or ""),
                    category=raw.get("category") or "system",  # type: ignore[arg-type]
                    state="pending",
                    dependsOn=list(raw.get("dependsOn") or []),
                    requiresApproval=bool(raw.get("requiresApproval", True)),
                    requiredCapabilities=list(raw.get("requiredCapabilities") or []),
                    proposedToolId=raw.get("proposedToolId") or raw.get("toolId"),
                    createdAt=now,
                    updatedAt=now,
                )
            )
        step_models = annotate_step_availability(step_models)
        open_blocking = 0
        snapshot = build_capability_snapshot(db, project_id, step_models, open_blocking=open_blocking)
        approvals = [
            PlanApprovalRequirement(
                requirementId=str(uuid.uuid4()),
                planId=plan_id,
                approvalType="plan_acceptance",
                status="required",
                reason="Plan acceptance is required before the plan becomes authoritative.",
                scope="plan",
            )
        ]
        plan = ProductionPlan(
            planId=plan_id,
            projectId=project_id,
            conversationId=conversation_id,
            title=title.strip() or "Untitled plan",
            objective=objective,
            description=description,
            state="draft",
            version=1,
            createdBy=ActorRef(actorType=actor_type),  # type: ignore[arg-type]
            source=PlanSource(type=source_type, sourceId=source_id),  # type: ignore[arg-type]
            steps=step_models,
            blockers=[],
            approvalRequirements=approvals,
            capabilitySnapshot=snapshot,
            createdAt=now,
            updatedAt=now,
            requestId=request_id,
            unapproved=True,
            warnings=[PlanWarning(code="UNAPPROVED_DRAFT", message="Draft is persisted but not approved.")],
        )
        validation = validate_plan(plan)
        if not validation.valid and validation.errors:
            # Drafts may persist with warnings; only hard structural errors block create
            hard = [e for e in validation.errors if e.code in {"PLAN_ID_REQUIRED", "PROJECT_REQUIRED", "TITLE_REQUIRED", "DUPLICATE_STEP_ID", "PLAN_DEPENDENCY_CYCLE", "PLAN_DEPENDENCY_MISSING", "PLAN_DEPENDENCY_SELF"}]
            if hard:
                raise CoDirectorError(
                    PLAN_VALIDATION_FAILED,
                    "Plan draft failed validation.",
                    details={"errors": [e.model_dump() for e in hard]},
                    recoverable=True,
                    recommended_action="revise_arguments",
                )
        try:
            return PlanCommandService._commit_atomic(
                db,
                project_id=project_id,
                request_id=request_id or str(uuid.uuid4()),
                command="create_draft",
                plan=plan,
                event_type="PLAN_CREATED",
                summary=f"Created unapproved draft plan '{plan.title}'.",
                changes={"state": "draft", "version": 1},
                actor_type=actor_type,
            )
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _load_for_mutation(
        db: Session, project_id: str, plan_id: str, expected_version: Optional[int]
    ) -> tuple[CoDirectorProductionPlan, ProductionPlan]:
        store.require_project(db, project_id)
        row = store.get_head(db, project_id, plan_id)
        plan = store.row_to_plan(row)
        if expected_version is not None and int(expected_version) != int(plan.version):
            raise CoDirectorError(
                PLAN_VERSION_CONFLICT,
                "Plan version conflict.",
                details={
                    "expectedVersion": expected_version,
                    "actualVersion": plan.version,
                    "currentPlanSummary": {"planId": plan.planId, "state": plan.state, "title": plan.title},
                    "recommendedAction": "reload_and_retry",
                },
                recoverable=True,
                recommended_action="retry",
            )
        return row, plan

    @staticmethod
    def _transition(
        db: Session,
        *,
        project_id: str,
        plan_id: str,
        request_id: str,
        command: str,
        expected_version: int,
        to_state: str,
        event_type: str,
        summary: str,
        revision_reason: Optional[str] = None,
        mutate=None,
        actor_type: str = "user",
        require_valid_for_ready: bool = False,
    ) -> PlanCommandResult:
        if request_id:
            dup = PlanCommandService._check_idempotency(db, project_id, request_id)
            if dup:
                return dup
        try:
            row, plan = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
            assert_plan_transition(plan.state, to_state, command=command)
            prev = plan.state
            plan.state = to_state  # type: ignore[assignment]
            plan.version = int(plan.version) + 1
            plan.updatedAt = _now()
            plan.revisionReason = revision_reason
            plan.parentVersionId = f"{plan.planId}:v{plan.version - 1}"
            if to_state in {"approved", "ready", "blocked", "paused"}:
                plan.unapproved = False
            if to_state == "paused":
                plan.pausedAt = _now()
            if to_state == "ready" and prev == "paused":
                plan.resumedAt = _now()
            if to_state == "cancelled":
                plan.cancelledAt = _now()
            if to_state == "archived":
                plan.archivedAt = _now()
            if mutate:
                mutate(plan)
            plan.steps = annotate_step_availability(plan.steps)
            open_ids = {b.stepId for b in plan.blockers if b.state == "open" and b.stepId}
            plan.steps = compute_step_readiness(plan.steps, open_ids)
            open_blocking = sum(1 for b in plan.blockers if b.state == "open" and b.severity == "blocking")
            plan.capabilitySnapshot = build_capability_snapshot(db, project_id, plan.steps, open_blocking=open_blocking)
            validation = validate_plan(plan)
            if require_valid_for_ready and to_state in {"approved", "ready"} and not validation.valid:
                raise CoDirectorError(
                    PLAN_VALIDATION_FAILED,
                    "Plan cannot be approved or marked ready with validation errors.",
                    details={"errors": [e.model_dump() for e in validation.errors]},
                    recoverable=True,
                    recommended_action="revise",
                )
            return PlanCommandService._commit_atomic(
                db,
                project_id=project_id,
                request_id=request_id or str(uuid.uuid4()),
                command=command,
                plan=plan,
                event_type=event_type,
                summary=summary,
                changes={"from": prev, "to": to_state, "version": plan.version},
                row=row,
                actor_type=actor_type,
            )
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def propose(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="propose",
            expected_version=expected_version,
            to_state="proposed",
            event_type="PLAN_PROPOSED",
            summary="Plan proposed for approval.",
        )

    @staticmethod
    def approve(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        def _mutate(plan: ProductionPlan) -> None:
            for req in plan.approvalRequirements:
                if req.approvalType == "plan_acceptance":
                    req.status = "approved"
                    req.approvedBy = "user"
                    req.approvedAt = _now()

        result = PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="approve",
            expected_version=expected_version,
            to_state="approved",
            event_type="PLAN_APPROVED",
            summary="Plan acceptance approved (does not authorize production actions).",
            mutate=_mutate,
            require_valid_for_ready=True,
        )
        plan = result.plan
        open_blocking = sum(1 for b in plan.blockers if b.state == "open" and b.severity == "blocking")
        # Only advance to ready when capabilities are truly ready and no blockers.
        if plan.capabilitySnapshot.readiness == "ready" and not open_blocking:
            return PlanCommandService._transition(
                db,
                project_id=project_id,
                plan_id=plan_id,
                request_id=f"{request_id}:post-approve",
                command="approve",
                expected_version=plan.version,
                to_state="ready",
                event_type="CAPABILITY_SNAPSHOT_UPDATED",
                summary="Post-approval readiness set to ready.",
                actor_type="system",
            )
        if open_blocking:
            return PlanCommandService._transition(
                db,
                project_id=project_id,
                plan_id=plan_id,
                request_id=f"{request_id}:post-approve",
                command="approve",
                expected_version=plan.version,
                to_state="blocked",
                event_type="CAPABILITY_SNAPSHOT_UPDATED",
                summary="Post-approval readiness set to blocked.",
                actor_type="system",
            )
        # Deferred/partial capabilities: remain approved (authoritative) but not falsely ready.
        return result

    @staticmethod
    def reject(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int, reason: str = "") -> PlanCommandResult:
        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="reject",
            expected_version=expected_version,
            to_state="draft",
            event_type="PLAN_REJECTED",
            summary=reason or "Plan rejected; returned to draft.",
            revision_reason=reason or "rejected",
        )

    @staticmethod
    def pause(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        _, current = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
        prior_state = current.state

        def _mutate(plan: ProductionPlan) -> None:
            plan.metadata = {**(plan.metadata or {}), "stateBeforePause": prior_state}

        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="pause",
            expected_version=expected_version,
            to_state="paused",
            event_type="PLAN_PAUSED",
            summary="Plan paused.",
            mutate=_mutate,
        )

    @staticmethod
    def resume(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        _, current = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
        prior = str((current.metadata or {}).get("stateBeforePause") or "ready")
        if prior not in {"ready", "blocked", "approved"}:
            prior = "ready"

        def _mutate(p: ProductionPlan) -> None:
            meta = dict(p.metadata or {})
            meta.pop("stateBeforePause", None)
            p.metadata = meta

        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="resume",
            expected_version=expected_version,
            to_state=prior,
            event_type="PLAN_RESUMED",
            summary=f"Plan resumed to {prior}.",
            mutate=_mutate,
        )

    @staticmethod
    def cancel(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="cancel",
            expected_version=expected_version,
            to_state="cancelled",
            event_type="PLAN_CANCELLED",
            summary="Plan cancelled.",
        )

    @staticmethod
    def archive(db: Session, *, project_id: str, plan_id: str, request_id: str, expected_version: int) -> PlanCommandResult:
        return PlanCommandService._transition(
            db,
            project_id=project_id,
            plan_id=plan_id,
            request_id=request_id,
            command="archive",
            expected_version=expected_version,
            to_state="archived",
            event_type="PLAN_ARCHIVED",
            summary="Plan archived.",
        )

    @staticmethod
    def revise(
        db: Session,
        *,
        project_id: str,
        plan_id: str,
        request_id: str,
        expected_version: int,
        title: Optional[str] = None,
        objective: Optional[str] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        revision_reason: str = "",
    ) -> PlanCommandResult:
        if request_id:
            dup = PlanCommandService._check_idempotency(db, project_id, request_id)
            if dup:
                return dup
        try:
            row, plan = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
            if plan.state in {"cancelled", "archived"}:
                assert_plan_transition(plan.state, "draft", command="revise")
            prev_state = plan.state
            prev_version = plan.version
            if title is not None:
                plan.title = title
            if objective is not None:
                plan.objective = objective
            if steps is not None:
                now = _now()
                rebuilt: list[ProductionPlanStep] = []
                for i, raw in enumerate(steps):
                    sid = str(raw.get("stepId") or f"step-{i+1}")
                    rebuilt.append(
                        ProductionPlanStep(
                            stepId=sid,
                            planId=plan.planId,
                            order=int(raw.get("order") or i + 1),
                            title=str(raw.get("title") or f"Step {i+1}"),
                            description=str(raw.get("description") or ""),
                            category=raw.get("category") or "system",  # type: ignore[arg-type]
                            state=raw.get("state") or "pending",  # type: ignore[arg-type]
                            dependsOn=list(raw.get("dependsOn") or []),
                            requiresApproval=bool(raw.get("requiresApproval", True)),
                            requiredCapabilities=list(raw.get("requiredCapabilities") or []),
                            proposedToolId=raw.get("proposedToolId") or raw.get("toolId"),
                            createdAt=now,
                            updatedAt=now,
                        )
                    )
                plan.steps = annotate_step_availability(rebuilt)
            # Revisions of authoritative plans return to proposed for re-acceptance
            if prev_state in {"approved", "ready", "blocked", "paused"}:
                to_state = "proposed"
                plan.unapproved = True
            else:
                to_state = prev_state if prev_state != "cancelled" else "draft"
            if to_state != prev_state:
                assert_plan_transition(prev_state, to_state, command="revise")
            plan.state = to_state  # type: ignore[assignment]
            plan.version = prev_version + 1
            plan.updatedAt = _now()
            plan.revisionReason = revision_reason or "revised"
            plan.parentVersionId = f"{plan.planId}:v{prev_version}"
            open_blocking = sum(1 for b in plan.blockers if b.state == "open" and b.severity == "blocking")
            plan.capabilitySnapshot = build_capability_snapshot(db, project_id, plan.steps, open_blocking=open_blocking)
            validation = validate_plan(plan)
            if not validation.valid:
                raise CoDirectorError(
                    PLAN_VALIDATION_FAILED,
                    "Revised plan failed validation.",
                    details={"errors": [e.model_dump() for e in validation.errors]},
                    recoverable=True,
                    recommended_action="revise",
                )
            return PlanCommandService._commit_atomic(
                db,
                project_id=project_id,
                request_id=request_id or str(uuid.uuid4()),
                command="revise",
                plan=plan,
                event_type="PLAN_REVISED",
                summary=revision_reason or "Plan revised.",
                changes={"fromVersion": prev_version, "toVersion": plan.version, "state": plan.state},
                row=row,
                actor_type="user",
            )
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def resolve_blocker(
        db: Session,
        *,
        project_id: str,
        plan_id: str,
        request_id: str,
        expected_version: int,
        blocker_id: str,
    ) -> PlanCommandResult:
        if request_id:
            dup = PlanCommandService._check_idempotency(db, project_id, request_id)
            if dup:
                return dup
        try:
            row, plan = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
            found = None
            for b in plan.blockers:
                if b.blockerId == blocker_id:
                    found = b
                    break
            if not found:
                raise CoDirectorError(
                    PLAN_BLOCKER_NOT_FOUND,
                    "Blocker not found.",
                    details={"blockerId": blocker_id},
                    recoverable=False,
                    recommended_action="none",
                )
            found.state = "resolved"
            found.resolvedAt = _now()
            plan.version += 1
            plan.updatedAt = _now()
            plan.parentVersionId = f"{plan.planId}:v{plan.version - 1}"
            return PlanCommandService._commit_atomic(
                db,
                project_id=project_id,
                request_id=request_id or str(uuid.uuid4()),
                command="resolve_blocker",
                plan=plan,
                event_type="BLOCKER_RESOLVED",
                summary=f"Resolved blocker {blocker_id}.",
                changes={"blockerId": blocker_id},
                row=row,
                actor_type="user",
            )
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def add_blocker(
        db: Session,
        *,
        project_id: str,
        plan_id: str,
        request_id: str,
        expected_version: int,
        blocker: dict[str, Any],
    ) -> PlanCommandResult:
        if request_id:
            dup = PlanCommandService._check_idempotency(db, project_id, request_id)
            if dup:
                return dup
        try:
            row, plan = PlanCommandService._load_for_mutation(db, project_id, plan_id, expected_version)
            b = ProductionPlanBlocker(
                blockerId=str(blocker.get("blockerId") or uuid.uuid4()),
                planId=plan.planId,
                stepId=blocker.get("stepId"),
                category=str(blocker.get("category") or "system"),
                severity=blocker.get("severity") or "blocking",  # type: ignore[arg-type]
                title=str(blocker.get("title") or "Blocker"),
                description=str(blocker.get("description") or ""),
                sourceType=str(blocker.get("sourceType") or "system"),
                sourceId=blocker.get("sourceId"),
                resolutionType=str(blocker.get("resolutionType") or "user_action"),
                recommendedAction=blocker.get("recommendedAction"),
                state="open",
                createdAt=_now(),
            )
            plan.blockers.append(b)
            plan.version += 1
            plan.updatedAt = _now()
            return PlanCommandService._commit_atomic(
                db,
                project_id=project_id,
                request_id=request_id or str(uuid.uuid4()),
                command="add_blocker",
                plan=plan,
                event_type="BLOCKER_ADDED",
                summary=f"Added blocker {b.blockerId}.",
                changes={"blockerId": b.blockerId},
                row=row,
            )
        except Exception:
            db.rollback()
            raise
