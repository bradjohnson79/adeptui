"""High-level Production Executive service used by API routes."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import ProductionJob
from .dependencies import refresh_waiting_jobs
from .models import JobStatus, JobType
from .retry import can_manual_retry
from .schemas import CreateJobRequest, JobOut, MarkApprovalRequest
from .store import JobStore
from .worker import production_worker


class ProductionExecutiveService:
    @staticmethod
    def create_job(db: Session, body: CreateJobRequest) -> JobOut:
        return JobStore.create_job(
            db,
            job_type=body.type,
            project_id=body.projectId,
            owner=body.owner,
            scene_id=body.sceneId,
            timeline_item_id=body.timelineItemId,
            priority=body.priority,
            capability_requirements=body.capabilityRequirements,
            payload=body.payload,
            depends_on_job_ids=body.dependsOnJobIds,
            idempotency_key=body.idempotencyKey,
            max_attempts=body.maxAttempts,
            provider=body.provider,
            actor=body.owner,
        )

    @staticmethod
    def create_closed_loop(
        db: Session,
        *,
        project_id: str,
        scene_id: str,
        owner: str = "user",
        idempotency_key: str | None = None,
        provider: str = "mock",
    ) -> dict[str, Any]:
        """storyboard -> image -> validate -> create_proposal -> await_approval -> apply_canon."""
        if idempotency_key:
            existing = JobStore.find_by_idempotency(db, project_id, idempotency_key)
            if existing:
                jobs = JobStore.list_jobs(db, project_id=project_id, scene_id=scene_id)
                return {"jobs": [j.model_dump() for j in jobs], "reused": True}

        sb = JobStore.create_job(
            db,
            job_type=JobType.STORYBOARD_GENERATE.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            provider=provider,
            payload={"provider": provider},
            priority=10,
            idempotency_key=f"{idempotency_key}:storyboard" if idempotency_key else None,
        )
        img = JobStore.create_job(
            db,
            job_type=JobType.IMAGE_GENERATE.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            provider=provider,
            payload={"provider": provider},
            depends_on_job_ids=[sb.id],
            priority=20,
            idempotency_key=f"{idempotency_key}:image" if idempotency_key else None,
        )
        val = JobStore.create_job(
            db,
            job_type=JobType.VALIDATE.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            provider=provider,
            payload={"provider": provider, "score": 90},
            depends_on_job_ids=[img.id],
            priority=30,
            idempotency_key=f"{idempotency_key}:validate" if idempotency_key else None,
        )
        prop = JobStore.create_job(
            db,
            job_type=JobType.CREATE_PROPOSAL.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            payload={"proposalId": f"prop-{scene_id}"},
            depends_on_job_ids=[val.id],
            priority=40,
            idempotency_key=f"{idempotency_key}:proposal" if idempotency_key else None,
        )
        await_job = JobStore.create_job(
            db,
            job_type=JobType.AWAIT_APPROVAL.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            payload={"proposalId": f"prop-{scene_id}"},
            depends_on_job_ids=[prop.id],
            priority=50,
            idempotency_key=f"{idempotency_key}:await" if idempotency_key else None,
        )
        apply = JobStore.create_job(
            db,
            job_type=JobType.APPLY_CANON.value,
            project_id=project_id,
            scene_id=scene_id,
            owner=owner,
            payload={"proposalId": f"prop-{scene_id}", "proposalApproved": False},
            depends_on_job_ids=[await_job.id],
            priority=60,
            idempotency_key=f"{idempotency_key}:apply" if idempotency_key else None,
        )
        return {
            "jobs": [j.model_dump() for j in (sb, img, val, prop, await_job, apply)],
            "reused": False,
            "note": "Await/apply never auto-approve; call mark-approval after M2.2 decision.",
        }

    @staticmethod
    def pause(db: Session, job_id: str, *, actor: str = "user", reason: str = "") -> JobOut:
        job = JobStore.get_job(db, job_id)
        if not job:
            raise ValueError("job not found")
        if job.status in (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value, JobStatus.FAILED.value):
            raise ValueError(f"cannot pause job in status {job.status}")
        out = JobStore.transition(
            db, job_id, JobStatus.PAUSED.value, actor=actor, reason=reason or "paused"
        )
        assert out
        return out

    @staticmethod
    def resume(db: Session, job_id: str, *, actor: str = "user", reason: str = "") -> JobOut:
        job = JobStore.get_job(db, job_id)
        if not job:
            raise ValueError("job not found")
        if job.status != JobStatus.PAUSED.value:
            raise ValueError(f"cannot resume job in status {job.status}")
        target = JobStatus.QUEUED.value
        if job.dependsOnJobIds:
            from .dependencies import dependencies_satisfied

            target = (
                JobStatus.QUEUED.value
                if dependencies_satisfied(db, job_id)
                else JobStatus.WAITING.value
            )
        out = JobStore.transition(
            db, job_id, target, actor=actor, reason=reason or "resumed", clear_blocked=True
        )
        assert out
        return out

    @staticmethod
    def cancel(db: Session, job_id: str, *, actor: str = "user", reason: str = "") -> JobOut:
        job = JobStore.get_job(db, job_id)
        if not job:
            raise ValueError("job not found")
        if job.status == JobStatus.COMPLETED.value:
            raise ValueError("cannot cancel completed job")
        out = JobStore.transition(
            db, job_id, JobStatus.CANCELLED.value, actor=actor, reason=reason or "cancelled"
        )
        assert out
        refresh_waiting_jobs(db, job_id)
        return out

    @staticmethod
    def retry(db: Session, job_id: str, *, actor: str = "user", reason: str = "") -> JobOut:
        job = JobStore.get_job(db, job_id)
        if not job:
            raise ValueError("job not found")
        if not can_manual_retry(job):
            raise ValueError(f"cannot retry job in status {job.status}")
        # Manual retry bumps maxAttempts floor so another attempt is allowed.
        row = db.get(ProductionJob, job_id)
        if row and row.attempts_count >= row.max_attempts:
            row.max_attempts = row.attempts_count + 1
            db.commit()
        out = JobStore.transition(
            db,
            job_id,
            JobStatus.RETRYING.value,
            actor=actor,
            reason=reason or "manual_retry",
            clear_blocked=True,
            error_message=None,
        )
        assert out
        return out

    @staticmethod
    def mark_approval(db: Session, job_id: str, body: MarkApprovalRequest) -> JobOut:
        """External M2.2 approval signal — Executive never approves itself."""
        job = JobStore.get_job(db, job_id)
        if not job:
            raise ValueError("job not found")
        if job.type != JobType.AWAIT_APPROVAL.value:
            raise ValueError("mark-approval only valid for await_approval jobs")
        row = db.get(ProductionJob, job_id)
        if not row:
            raise ValueError("job not found")
        payload = json.loads(row.payload_json or "{}")
        payload["proposalId"] = body.proposalId
        payload["proposalApproved"] = bool(body.approved)
        row.payload_json = json.dumps(payload, default=str)
        db.commit()

        if not body.approved:
            out = JobStore.transition(
                db,
                job_id,
                JobStatus.CANCELLED.value,
                actor=body.actor,
                reason=body.reason or "proposal_rejected",
                result={"proposalId": body.proposalId, "approved": False},
            )
            assert out
            return out

        # Re-queue so worker can complete await + unlock apply_canon dependents.
        out = JobStore.transition(
            db,
            job_id,
            JobStatus.QUEUED.value,
            actor=body.actor,
            reason=body.reason or "proposal_approved",
            clear_blocked=True,
        )
        assert out
        # Also stamp apply_canon dependents with approval flag (still no silent apply).
        for dep_id in JobStore.list_dependents(db, job_id):
            dep = db.get(ProductionJob, dep_id)
            if not dep or dep.type != JobType.APPLY_CANON.value:
                continue
            dep_payload = json.loads(dep.payload_json or "{}")
            dep_payload["proposalApproved"] = True
            dep_payload["proposalId"] = body.proposalId
            dep.payload_json = json.dumps(dep_payload, default=str)
        db.commit()
        return out

    @staticmethod
    def ensure_worker() -> None:
        if not production_worker.running:
            production_worker.start()