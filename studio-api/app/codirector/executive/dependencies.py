"""Dependency resolver for Production Executive jobs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import JobStatus
from .store import JobStore


def dependencies_satisfied(db: Session, job_id: str) -> bool:
    deps = JobStore.dependency_statuses(db, job_id)
    if not deps:
        return True
    return all(d["status"] == JobStatus.COMPLETED.value for d in deps)


def dependencies_failed(db: Session, job_id: str) -> bool:
    deps = JobStore.dependency_statuses(db, job_id)
    return any(
        d["status"] in (JobStatus.FAILED.value, JobStatus.CANCELLED.value) for d in deps
    )


def refresh_waiting_jobs(db: Session, completed_job_id: str) -> list[str]:
    """Move Waiting dependents to Queued when all deps are Completed; block on failure."""
    promoted: list[str] = []
    for dep_job_id in JobStore.list_dependents(db, completed_job_id):
        job = JobStore.get_job(db, dep_job_id)
        if not job:
            continue
        if job.status not in (
            JobStatus.WAITING.value,
            JobStatus.QUEUED.value,
            JobStatus.BLOCKED.value,
        ):
            continue
        if dependencies_failed(db, dep_job_id):
            JobStore.transition(
                db,
                dep_job_id,
                JobStatus.BLOCKED.value,
                actor="resolver",
                reason="dependency_failed",
                blocked_reason=f"Dependency {completed_job_id} failed or cancelled",
            )
            continue
        if dependencies_satisfied(db, dep_job_id):
            JobStore.transition(
                db,
                dep_job_id,
                JobStatus.QUEUED.value,
                actor="resolver",
                reason="dependencies_met",
                clear_blocked=True,
            )
            promoted.append(dep_job_id)
    return promoted
