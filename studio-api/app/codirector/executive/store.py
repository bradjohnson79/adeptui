"""SQLite-durable store for Production Executive jobs (not in-memory)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, asc, desc, or_
from sqlalchemy.orm import Session

from ...db import (
    ProductionJob,
    ProductionJobAttempt,
    ProductionJobAudit,
    ProductionJobDependency,
    ProductionJobEvent,
    ProductionNotification,
)
from .models import JOB_TYPE_CAPABILITIES, JobStatus
from .schemas import (
    AttemptOut,
    AuditOut,
    EventOut,
    JobOut,
    NotificationOut,
    SceneProgressOut,
)


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat() + ("Z" if not str(dt).endswith("Z") else "")


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


class JobStore:
    @staticmethod
    def job_from_row(db: Session, row: ProductionJob) -> JobOut:
        deps = (
            db.query(ProductionJobDependency)
            .filter(ProductionJobDependency.job_id == row.id)
            .all()
        )
        return JobOut(
            id=row.id,
            type=row.type,
            owner=row.owner,
            projectId=row.project_id,
            sceneId=row.scene_id,
            timelineItemId=row.timeline_item_id,
            priority=row.priority,
            status=row.status,
            capabilityRequirements=_loads(row.capability_requirements_json, []),
            payload=_loads(row.payload_json, {}),
            result=_loads(row.result_json, None) if row.result_json else None,
            errorMessage=row.error_message,
            idempotencyKey=row.idempotency_key,
            attemptsCount=row.attempts_count,
            maxAttempts=row.max_attempts,
            provider=row.provider,
            blockedReason=row.blocked_reason,
            dependsOnJobIds=[d.depends_on_job_id for d in deps],
            createdAt=_iso(row.created_at) or "",
            updatedAt=_iso(row.updated_at) or "",
            startedAt=_iso(row.started_at),
            completedAt=_iso(row.completed_at),
        )

    @staticmethod
    def find_by_idempotency(
        db: Session, project_id: str, key: str
    ) -> ProductionJob | None:
        return (
            db.query(ProductionJob)
            .filter(
                ProductionJob.project_id == project_id,
                ProductionJob.idempotency_key == key,
            )
            .first()
        )

    @staticmethod
    def create_job(
        db: Session,
        *,
        job_type: str,
        project_id: str,
        owner: str = "user",
        scene_id: str | None = None,
        timeline_item_id: str | None = None,
        priority: int = 100,
        capability_requirements: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        depends_on_job_ids: list[str] | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
        provider: str | None = None,
        initial_status: str | None = None,
        actor: str = "user",
    ) -> JobOut:
        if idempotency_key:
            existing = JobStore.find_by_idempotency(db, project_id, idempotency_key)
            if existing:
                return JobStore.job_from_row(db, existing)

        if capability_requirements is None:
            caps = list(JOB_TYPE_CAPABILITIES.get(job_type, []))
        else:
            caps = list(capability_requirements)

        deps = list(depends_on_job_ids or [])
        status = initial_status or (
            JobStatus.WAITING.value if deps else JobStatus.QUEUED.value
        )
        now = datetime.utcnow()
        job_id = str(uuid.uuid4())
        row = ProductionJob(
            id=job_id,
            type=job_type,
            owner=owner,
            project_id=project_id,
            scene_id=scene_id,
            timeline_item_id=timeline_item_id,
            priority=priority,
            status=status,
            capability_requirements_json=json.dumps(caps),
            payload_json=json.dumps(payload or {}, default=str),
            idempotency_key=idempotency_key,
            attempts_count=0,
            max_attempts=max_attempts,
            provider=provider,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        for dep_id in deps:
            db.add(
                ProductionJobDependency(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    depends_on_job_id=dep_id,
                )
            )
        JobStore._audit(
            db,
            job_id=job_id,
            from_status=None,
            to_status=status,
            actor=actor,
            reason="created",
        )
        JobStore._event(
            db,
            job_id=job_id,
            project_id=project_id,
            event_type="job.created",
            payload={"type": job_type, "status": status, "priority": priority},
        )
        db.commit()
        db.refresh(row)
        return JobStore.job_from_row(db, row)

    @staticmethod
    def get_job(db: Session, job_id: str, *, project_id: str | None = None) -> JobOut | None:
        row = db.get(ProductionJob, job_id)
        if not row:
            return None
        if project_id and row.project_id != project_id:
            return None
        return JobStore.job_from_row(db, row)

    @staticmethod
    def list_jobs(
        db: Session,
        *,
        project_id: str,
        status: str | None = None,
        statuses: list[str] | None = None,
        scene_id: str | None = None,
        limit: int = 100,
    ) -> list[JobOut]:
        q = db.query(ProductionJob).filter(ProductionJob.project_id == project_id)
        if status:
            q = q.filter(ProductionJob.status == status)
        if statuses:
            q = q.filter(ProductionJob.status.in_(statuses))
        if scene_id:
            q = q.filter(ProductionJob.scene_id == scene_id)
        rows = (
            q.order_by(asc(ProductionJob.priority), asc(ProductionJob.created_at))
            .limit(limit)
            .all()
        )
        return [JobStore.job_from_row(db, r) for r in rows]

    @staticmethod
    def transition(
        db: Session,
        job_id: str,
        to_status: str,
        *,
        actor: str = "system",
        reason: str = "",
        detail: dict[str, Any] | None = None,
        error_message: str | None = None,
        blocked_reason: str | None = None,
        result: dict[str, Any] | None = None,
        clear_blocked: bool = False,
    ) -> JobOut | None:
        row = db.get(ProductionJob, job_id)
        if not row:
            return None
        from_status = row.status
        if from_status == to_status and not detail:
            return JobStore.job_from_row(db, row)
        now = datetime.utcnow()
        row.status = to_status
        row.updated_at = now
        if to_status == JobStatus.RUNNING.value and row.started_at is None:
            row.started_at = now
        if to_status in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            row.completed_at = now
        if error_message is not None:
            row.error_message = error_message
        if blocked_reason is not None:
            row.blocked_reason = blocked_reason
        if clear_blocked:
            row.blocked_reason = None
        if result is not None:
            row.result_json = json.dumps(result, default=str)
        JobStore._audit(
            db,
            job_id=job_id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
            detail=detail,
        )
        JobStore._event(
            db,
            job_id=job_id,
            project_id=row.project_id,
            event_type="job.status_changed",
            payload={
                "from": from_status,
                "to": to_status,
                "reason": reason,
                "actor": actor,
            },
        )
        db.commit()
        db.refresh(row)
        return JobStore.job_from_row(db, row)

    @staticmethod
    def begin_attempt(
        db: Session,
        job_id: str,
        *,
        provider: str | None,
        capability_snapshot: dict[str, Any],
    ) -> AttemptOut:
        row = db.get(ProductionJob, job_id)
        if not row:
            raise ValueError("job not found")
        attempt_n = int(row.attempts_count) + 1
        row.attempts_count = attempt_n
        row.updated_at = datetime.utcnow()
        if provider:
            row.provider = provider
        attempt = ProductionJobAttempt(
            id=str(uuid.uuid4()),
            job_id=job_id,
            attempt_n=attempt_n,
            provider=provider,
            started_at=datetime.utcnow(),
            errors_json="[]",
            capability_snapshot_json=json.dumps(capability_snapshot, default=str),
            outcome="started",
        )
        db.add(attempt)
        JobStore._event(
            db,
            job_id=job_id,
            project_id=row.project_id,
            event_type="job.attempt_started",
            payload={"attemptN": attempt_n, "provider": provider},
        )
        db.commit()
        db.refresh(attempt)
        return JobStore.attempt_from_row(attempt)

    @staticmethod
    def finish_attempt(
        db: Session,
        attempt_id: str,
        *,
        outcome: str,
        result: dict[str, Any] | None = None,
        errors: list[Any] | None = None,
    ) -> AttemptOut | None:
        attempt = db.get(ProductionJobAttempt, attempt_id)
        if not attempt:
            return None
        # Never overwrite prior finished attempts — only close open ones.
        if attempt.finished_at is not None:
            return JobStore.attempt_from_row(attempt)
        now = datetime.utcnow()
        attempt.finished_at = now
        attempt.duration_ms = int((now - attempt.started_at).total_seconds() * 1000)
        attempt.outcome = outcome
        if result is not None:
            attempt.result_json = json.dumps(result, default=str)
        if errors is not None:
            attempt.errors_json = json.dumps(errors, default=str)
        job = db.get(ProductionJob, attempt.job_id)
        if job:
            JobStore._event(
                db,
                job_id=job.id,
                project_id=job.project_id,
                event_type="job.attempt_finished",
                payload={
                    "attemptN": attempt.attempt_n,
                    "outcome": outcome,
                    "durationMs": attempt.duration_ms,
                },
            )
        db.commit()
        db.refresh(attempt)
        return JobStore.attempt_from_row(attempt)

    @staticmethod
    def attempt_from_row(row: ProductionJobAttempt) -> AttemptOut:
        return AttemptOut(
            id=row.id,
            jobId=row.job_id,
            attemptN=row.attempt_n,
            provider=row.provider,
            startedAt=_iso(row.started_at) or "",
            finishedAt=_iso(row.finished_at),
            durationMs=row.duration_ms,
            errors=_loads(row.errors_json, []),
            capabilitySnapshot=_loads(row.capability_snapshot_json, {}),
            result=_loads(row.result_json, None) if row.result_json else None,
            outcome=row.outcome,
        )

    @staticmethod
    def list_attempts(db: Session, job_id: str) -> list[AttemptOut]:
        rows = (
            db.query(ProductionJobAttempt)
            .filter(ProductionJobAttempt.job_id == job_id)
            .order_by(asc(ProductionJobAttempt.attempt_n))
            .all()
        )
        return [JobStore.attempt_from_row(r) for r in rows]

    @staticmethod
    def list_dependencies(db: Session, job_id: str) -> list[str]:
        rows = (
            db.query(ProductionJobDependency)
            .filter(ProductionJobDependency.job_id == job_id)
            .all()
        )
        return [r.depends_on_job_id for r in rows]

    @staticmethod
    def list_dependents(db: Session, job_id: str) -> list[str]:
        rows = (
            db.query(ProductionJobDependency)
            .filter(ProductionJobDependency.depends_on_job_id == job_id)
            .all()
        )
        return [r.job_id for r in rows]

    @staticmethod
    def dependency_statuses(db: Session, job_id: str) -> list[dict[str, str]]:
        dep_ids = JobStore.list_dependencies(db, job_id)
        out: list[dict[str, str]] = []
        for dep_id in dep_ids:
            row = db.get(ProductionJob, dep_id)
            out.append(
                {
                    "jobId": dep_id,
                    "status": row.status if row else "Missing",
                    "type": row.type if row else "",
                }
            )
        return out

    @staticmethod
    def claim_next_runnable(
        db: Session,
        *,
        exclude_ids: set[str] | None = None,
    ) -> JobOut | None:
        """Pick highest-priority runnable job whose dependencies are Completed."""
        q = (
            db.query(ProductionJob)
            .filter(
                ProductionJob.status.in_(
                    [JobStatus.QUEUED.value, JobStatus.RETRYING.value]
                )
            )
            .order_by(asc(ProductionJob.priority), asc(ProductionJob.created_at))
        )
        for row in q.limit(200).all():
            if exclude_ids and row.id in exclude_ids:
                continue
            deps = JobStore.dependency_statuses(db, row.id)
            if any(d["status"] != JobStatus.COMPLETED.value for d in deps):
                if row.status != JobStatus.WAITING.value and deps:
                    # Keep waiting until deps finish (audit once via transition helper).
                    if all(
                        d["status"]
                        not in (
                            JobStatus.FAILED.value,
                            JobStatus.CANCELLED.value,
                        )
                        for d in deps
                    ):
                        continue
                continue
            claimed = JobStore.transition(
                db,
                row.id,
                JobStatus.RUNNING.value,
                actor="worker",
                reason="claimed",
                clear_blocked=True,
            )
            return claimed
        return None

    @staticmethod
    def recover_running_jobs(db: Session) -> list[JobOut]:
        """On worker start: Running jobs → Retrying without duplicating finished attempts."""
        recovered: list[JobOut] = []
        rows = (
            db.query(ProductionJob)
            .filter(ProductionJob.status == JobStatus.RUNNING.value)
            .all()
        )
        for row in rows:
            # Close any open attempt as interrupted (append-only history).
            open_attempts = (
                db.query(ProductionJobAttempt)
                .filter(
                    ProductionJobAttempt.job_id == row.id,
                    ProductionJobAttempt.finished_at.is_(None),
                )
                .all()
            )
            for attempt in open_attempts:
                JobStore.finish_attempt(
                    db,
                    attempt.id,
                    outcome="interrupted",
                    errors=[{"message": "worker restart recovery"}],
                )
            job = JobStore.transition(
                db,
                row.id,
                JobStatus.RETRYING.value,
                actor="worker",
                reason="crash_recovery",
                detail={"previous": "Running"},
            )
            if job:
                recovered.append(job)
        return recovered

    @staticmethod
    def _audit(
        db: Session,
        *,
        job_id: str,
        from_status: str | None,
        to_status: str,
        actor: str,
        reason: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        db.add(
            ProductionJobAudit(
                id=str(uuid.uuid4()),
                job_id=job_id,
                from_status=from_status,
                to_status=to_status,
                actor=actor,
                reason=reason,
                detail_json=json.dumps(detail or {}, default=str),
                created_at=datetime.utcnow(),
            )
        )

    @staticmethod
    def _event(
        db: Session,
        *,
        job_id: str | None,
        project_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> ProductionJobEvent:
        event = ProductionJobEvent(
            id=str(uuid.uuid4()),
            job_id=job_id,
            project_id=project_id,
            event_type=event_type,
            payload_json=json.dumps(payload, default=str),
            created_at=datetime.utcnow(),
        )
        db.add(event)
        return event

    @staticmethod
    def list_events(
        db: Session,
        *,
        project_id: str,
        job_id: str | None = None,
        limit: int = 100,
    ) -> list[EventOut]:
        q = db.query(ProductionJobEvent).filter(
            ProductionJobEvent.project_id == project_id
        )
        if job_id:
            q = q.filter(ProductionJobEvent.job_id == job_id)
        rows = q.order_by(desc(ProductionJobEvent.created_at)).limit(limit).all()
        return [
            EventOut(
                id=r.id,
                jobId=r.job_id,
                projectId=r.project_id,
                eventType=r.event_type,
                payload=_loads(r.payload_json, {}),
                createdAt=_iso(r.created_at) or "",
            )
            for r in rows
        ]

    @staticmethod
    def list_audit(db: Session, job_id: str) -> list[AuditOut]:
        rows = (
            db.query(ProductionJobAudit)
            .filter(ProductionJobAudit.job_id == job_id)
            .order_by(asc(ProductionJobAudit.created_at))
            .all()
        )
        return [
            AuditOut(
                id=r.id,
                jobId=r.job_id,
                fromStatus=r.from_status,
                toStatus=r.to_status,
                actor=r.actor,
                reason=r.reason,
                detail=_loads(r.detail_json, {}),
                createdAt=_iso(r.created_at) or "",
            )
            for r in rows
        ]

    @staticmethod
    def create_notification(
        db: Session,
        *,
        project_id: str,
        job_id: str | None,
        event_id: str | None,
        level: str,
        title: str,
        body: str,
    ) -> NotificationOut:
        row = ProductionNotification(
            id=str(uuid.uuid4()),
            project_id=project_id,
            job_id=job_id,
            event_id=event_id,
            level=level,
            title=title,
            body=body,
            read_flag=0,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return JobStore.notification_from_row(row)

    @staticmethod
    def notification_from_row(row: ProductionNotification) -> NotificationOut:
        return NotificationOut(
            id=row.id,
            projectId=row.project_id,
            jobId=row.job_id,
            eventId=row.event_id,
            level=row.level,
            title=row.title,
            body=row.body,
            read=bool(row.read_flag),
            createdAt=_iso(row.created_at) or "",
        )

    @staticmethod
    def list_notifications(
        db: Session, project_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> list[NotificationOut]:
        q = db.query(ProductionNotification).filter(
            ProductionNotification.project_id == project_id
        )
        if unread_only:
            q = q.filter(ProductionNotification.read_flag == 0)
        rows = (
            q.order_by(desc(ProductionNotification.created_at)).limit(limit).all()
        )
        return [JobStore.notification_from_row(r) for r in rows]

    @staticmethod
    def scene_progress(db: Session, project_id: str, scene_id: str) -> SceneProgressOut:
        rows = (
            db.query(ProductionJob)
            .filter(
                ProductionJob.project_id == project_id,
                ProductionJob.scene_id == scene_id,
            )
            .all()
        )
        total = len(rows)
        completed = sum(1 for r in rows if r.status == JobStatus.COMPLETED.value)
        failed = sum(1 for r in rows if r.status == JobStatus.FAILED.value)
        blocked = sum(1 for r in rows if r.status == JobStatus.BLOCKED.value)
        running = sum(1 for r in rows if r.status == JobStatus.RUNNING.value)
        queued = sum(
            1
            for r in rows
            if r.status
            in (
                JobStatus.QUEUED.value,
                JobStatus.WAITING.value,
                JobStatus.RETRYING.value,
            )
        )
        needs_review = sum(1 for r in rows if r.status == JobStatus.NEEDS_REVIEW.value)
        pct = (completed / total * 100.0) if total else 0.0
        return SceneProgressOut(
            sceneId=scene_id,
            projectId=project_id,
            totalJobs=total,
            completed=completed,
            failed=failed,
            blocked=blocked,
            running=running,
            queued=queued,
            needsReview=needs_review,
            percentComplete=round(pct, 1),
            derivedFromJobs=True,
        )

    @staticmethod
    def statistics(db: Session, project_id: str) -> dict[str, Any]:
        rows = (
            db.query(ProductionJob)
            .filter(ProductionJob.project_id == project_id)
            .all()
        )
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_type[r.type] = by_type.get(r.type, 0) + 1
        return {
            "projectId": project_id,
            "total": len(rows),
            "byStatus": by_status,
            "byType": by_type,
        }
