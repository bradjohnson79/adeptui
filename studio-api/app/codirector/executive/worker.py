"""Durable queue worker — reloads from SQLite; recovers Running safely."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import SessionLocal
from .capability import sync_check_capabilities
from .dependencies import refresh_waiting_jobs
from .events import event_bus
from .handlers import execute_job
from .models import JobStatus
from .retry import next_status_after_failure
from .store import JobStore

logger = logging.getLogger(__name__)


class ProductionJobWorker:
    """Background poller that survives process restart via DB reload."""

    def __init__(self, *, poll_interval: float = 0.25, max_concurrent: int = 2) -> None:
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
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
            provider=job.provider or (job.payload or {}).get("provider") or "mock",
            capability_snapshot=snap,
        )
        # Re-load job after attempt bump.
        job = JobStore.get_job(db, job_id) or job
        handler = execute_job(job)

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

        if handler.status == "Blocked" or (
            not handler.ok and handler.status == "Blocked"
        ):
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
        # Merge handler result into payload for downstream approval flags when needed.
        merged = dict(job.payload or {})
        if handler.result.get("proposalId"):
            merged.setdefault("proposalId", handler.result["proposalId"])
        row = db.get(__import__("app.db", fromlist=["ProductionJob"]).ProductionJob, job_id)
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