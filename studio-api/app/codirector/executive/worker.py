"""Durable queue worker — single-process, SQLite-backed; recovers Running safely.

Honest single-process model: one daemon thread polls and runs sync handlers
serially (max_concurrent=1). There is no distributed lease / multi-worker claim
protocol — do not pretend otherwise.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import ProductionJob, SessionLocal
from .capability import sync_check_capabilities
from .dependencies import refresh_waiting_jobs
from .events import event_bus
from .handlers import execute_job
from .models import JobStatus
from .retry import next_status_after_failure
from .store import JobStore

logger = logging.getLogger(__name__)

_CHAIN_KEYS = (
    "panelId",
    "imageJobId",
    "assetId",
    "proposalId",
    "sessionId",
    "reportId",
    "score",
    "passed",
    "band",
    "proposalApproved",
)


def _env_poll_interval(default: float = 0.25) -> float:
    raw = os.environ.get("STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL", "").strip()
    if not raw:
        return default
    try:
        return max(0.05, float(raw))
    except ValueError:
        return default


def _chain_results_to_dependents(db: Session, job_id: str, result: dict[str, Any]) -> None:
    """Propagate closed-loop outputs into waiting dependent job payloads."""
    if not result:
        return
    for dep_id in JobStore.list_dependents(db, job_id):
        dep = db.get(ProductionJob, dep_id)
        if not dep:
            continue
        try:
            payload = json.loads(dep.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        changed = False
        for key in _CHAIN_KEYS:
            if key in result and result[key] is not None:
                if payload.get(key) != result[key]:
                    payload[key] = result[key]
                    changed = True
        if changed:
            dep.payload_json = json.dumps(payload, default=str)
    db.commit()


class ProductionJobWorker:
    """Background poller that survives process restart via DB reload.

    Sync handlers run on this thread. ``max_concurrent`` defaults to 1 because
    handlers are synchronous — a higher value would be misleading without a
    thread/async executor.
    """

    def __init__(
        self,
        *,
        poll_interval: float | None = None,
        max_concurrent: int = 1,
    ) -> None:
        self.poll_interval = (
            _env_poll_interval() if poll_interval is None else max(0.05, float(poll_interval))
        )
        self.max_concurrent = max(1, int(max_concurrent))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()
        self._started = False

    @property
    def running(self) -> bool:
        return self._started and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._started and self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            db = SessionLocal()
            try:
                recovered = JobStore.recover_running_jobs(db)
                logger.info("Production Executive recovered %s running jobs", len(recovered))
            finally:
                db.close()
            self._thread = threading.Thread(
                target=self._loop, name="production-executive-worker", daemon=True
            )
            self._started = True
            self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._started = False

    def tick_once(self, db: Session | None = None) -> Optional[str]:
        """Process at most one job (tests / synchronous drain)."""
        owns = db is None
        session = db or SessionLocal()
        try:
            return self._process_one(session)
        finally:
            if owns:
                session.close()

    def drain(self, *, max_steps: int = 50) -> int:
        """Run until idle or max_steps — for deterministic tests."""
        steps = 0
        for _ in range(max_steps):
            did = self.tick_once()
            if not did:
                break
            steps += 1
        return steps

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                db = SessionLocal()
                try:
                    # Sync handlers: process one job per outer tick. max_concurrent>1
                    # is reserved for a future threaded executor and is not faked here.
                    while len(self._in_flight) < self.max_concurrent:
                        job_id = self._process_one(db)
                        if not job_id:
                            break
                finally:
                    db.close()
            except Exception:  # noqa: BLE001
                logger.exception("Production Executive worker tick failed")
            self._stop.wait(self.poll_interval)

    def _process_one(self, db: Session) -> Optional[str]:
        job = JobStore.claim_next_runnable(db, exclude_ids=self._in_flight)
        if not job:
            return None

        self._in_flight.add(job.id)
        try:
            return self._execute_claimed(db, job.id)
        finally:
            self._in_flight.discard(job.id)

    def _execute_claimed(self, db: Session, job_id: str) -> str:
        job = JobStore.get_job(db, job_id)
        if not job:
            return job_id

        mock_unavail = list((job.payload or {}).get("mockUnavailableCapabilities") or [])
        snap = sync_check_capabilities(
            requirements=job.capabilityRequirements,
            mock_unavailable=mock_unavail,
            db=db,
            project_id=job.projectId,
        )
        if not snap["available"]:
            JobStore.transition(
                db,
                job_id,
                JobStatus.BLOCKED.value,
                actor="worker",
                reason="provider_unavailable",
                blocked_reason="Missing capabilities: " + ", ".join(snap["missing"]),
                detail=snap,
            )
            event_bus.publish(
                db,
                project_id=job.projectId,
                event_type="provider.unavailable",
                job_id=job_id,
                payload={"missing": snap["missing"]},
            )
            JobStore.create_notification(
                db,
                project_id=job.projectId,
                job_id=job_id,
                event_id=None,
                level="warn",
                title="Provider unavailable",
                body="Missing capabilities: " + ", ".join(snap["missing"]),
            )
            return job_id

        attempt = JobStore.begin_attempt(
            db,
            job_id,
            provider=job.provider or (job.payload or {}).get("provider") or "local",
            capability_snapshot=snap,
        )
        job = JobStore.get_job(db, job_id) or job
        handler = execute_job(job, db)

        if handler.needs_review:
            JobStore.finish_attempt(
                db, attempt.id, outcome="needs_review", result=handler.result
            )
            JobStore.transition(
                db,
                job_id,
                JobStatus.NEEDS_REVIEW.value,
                actor="worker",
                reason="awaiting_human_approval",
                result=handler.result,
            )
            JobStore.create_notification(
                db,
                project_id=job.projectId,
                job_id=job_id,
                event_id=None,
                level="warn",
                title="Needs review",
                body="Job waiting for M2.2 approval — Production Executive will not auto-approve.",
            )
            return job_id

        if handler.status == "Blocked" or (not handler.ok and handler.status == "Blocked"):
            JobStore.finish_attempt(
                db,
                attempt.id,
                outcome="blocked",
                result=handler.result,
                errors=[{"message": handler.error}] if handler.error else None,
            )
            JobStore.transition(
                db,
                job_id,
                JobStatus.BLOCKED.value,
                actor="worker",
                reason=handler.error or "blocked",
                blocked_reason=handler.error,
                result=handler.result,
            )
            return job_id

        if handler.status == "Cancelled" or (not handler.ok and handler.status == "Cancelled"):
            JobStore.finish_attempt(
                db,
                attempt.id,
                outcome="cancelled",
                result=handler.result,
                errors=[{"message": handler.error}] if handler.error else None,
            )
            JobStore.transition(
                db,
                job_id,
                JobStatus.CANCELLED.value,
                actor="worker",
                reason=handler.error or "cancelled",
                result=handler.result,
            )
            refresh_waiting_jobs(db, job_id)
            return job_id

        if not handler.ok:
            JobStore.finish_attempt(
                db,
                attempt.id,
                outcome="failed",
                errors=[{"message": handler.error or "failed"}],
            )
            job = JobStore.get_job(db, job_id) or job
            nxt = next_status_after_failure(job)
            JobStore.transition(
                db,
                job_id,
                nxt,
                actor="worker",
                reason=handler.error or "attempt_failed",
                error_message=handler.error,
            )
            if nxt == JobStatus.FAILED.value:
                JobStore.create_notification(
                    db,
                    project_id=job.projectId,
                    job_id=job_id,
                    event_id=None,
                    level="error",
                    title="Job failed",
                    body=handler.error or "max attempts exceeded",
                )
            return job_id

        JobStore.finish_attempt(
            db, attempt.id, outcome="completed", result=handler.result
        )
        merged = dict(job.payload or {})
        merged.update({k: v for k, v in (handler.result or {}).items() if v is not None})
        row = db.get(ProductionJob, job_id)
        if row is not None:
            row.payload_json = json.dumps(merged, default=str)
            db.commit()

        JobStore.transition(
            db,
            job_id,
            JobStatus.COMPLETED.value,
            actor="worker",
            reason="handler_ok",
            result=handler.result,
            clear_blocked=True,
        )
        _chain_results_to_dependents(db, job_id, handler.result or {})
        refresh_waiting_jobs(db, job_id)
        event_bus.publish(
            db,
            project_id=job.projectId,
            event_type="job.completed",
            job_id=job_id,
            payload={"type": job.type},
        )
        JobStore.create_notification(
            db,
            project_id=job.projectId,
            job_id=job_id,
            event_id=None,
            level="success",
            title="Job completed",
            body=f"{job.type} completed",
        )
        return job_id


# Process-wide worker (started from API lifespan when flag on).
production_worker = ProductionJobWorker()
