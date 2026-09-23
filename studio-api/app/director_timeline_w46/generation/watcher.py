"""Background poller: adapter status → shared Timeline completion."""

from __future__ import annotations

import threading
import time
from typing import Any

from ...db import SessionLocal
from .completion import apply_shared_completion
from .contracts import NormalizedJobSubmission
from .registry import get_registry


def start_completion_watcher(
    *,
    project_id: str,
    scene_id: str,
    batch_id: str,
    execution_snapshot_id: str,
    submission: NormalizedJobSubmission,
    poll_interval_sec: float = 3.0,
    timeout_sec: float = 3600.0,  # H3 12s ref2va routinely exceeds 20m wall; match job_timeout_sec
) -> None:
    def _run() -> None:
        registry = get_registry()
        try:
            adapter = registry.get(submission.generatorId)
        except Exception:
            return
        # Ensure MiniMax metadata carries projectId
        meta = dict(submission.providerMetadata or {})
        meta.setdefault("projectId", project_id)
        submission.providerMetadata = meta

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                status = adapter.get_status(submission)
            except Exception:
                time.sleep(poll_interval_sec)
                continue
            if status.status not in ("completed", "failed", "cancelled"):
                try:
                    _stamp_live_job_progress(
                        project_id,
                        scene_id,
                        batch_id,
                        execution_snapshot_id,
                        status,
                    )
                except Exception:
                    pass
            if status.status in ("completed", "failed", "cancelled"):
                db = SessionLocal()
                try:
                    if status.status == "completed":
                        result = adapter.collect_result(submission)
                        draft = bool(
                            (submission.providerMetadata or {}).get("draftMode")
                            or (result.providerMetadata or {}).get("draftMode")
                        )
                        apply_shared_completion(
                            db,
                            project_id=project_id,
                            scene_id=scene_id,
                            batch_id=batch_id,
                            execution_snapshot_id=execution_snapshot_id,
                            result=result,
                            job=submission,
                            auto_approve=False,
                        )
                    elif status.status == "cancelled":
                        _mark_job_failed(
                            db,
                            project_id,
                            scene_id,
                            batch_id,
                            execution_snapshot_id,
                            status.errorCode or "CANCELLED",
                            status.errorMessage or "Cancelled",
                            cancelled=True,
                        )
                    else:
                        _mark_job_failed(
                            db,
                            project_id,
                            scene_id,
                            batch_id,
                            execution_snapshot_id,
                            status.errorCode,
                            status.errorMessage,
                        )
                except Exception as exc:
                    # Never let the watcher thread die silently: surface the
                    # failure and still try to advance the sequential chain so
                    # subsequent Queued batches are not stranded.
                    print(
                        f"[tl-watcher] terminal handling raised for batch {batch_id[:8]}: "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    try:
                        from .. import orchestrator

                        orchestrator.submit_next_queued_batch(db, project_id, scene_id)
                    except Exception as chain_exc:
                        print(
                            f"[tl-watcher] chain advance also failed for scene {scene_id[:8]}: "
                            f"{type(chain_exc).__name__}: {chain_exc}",
                            flush=True,
                        )
                finally:
                    db.close()
                return
            time.sleep(poll_interval_sec)

        db = SessionLocal()
        try:
            _mark_job_failed(
                db,
                project_id,
                scene_id,
                batch_id,
                execution_snapshot_id,
                "TIMELINE_GEN_TIMEOUT",
                "Timeline generation watcher timed out.",
            )
        except Exception as exc:
            print(
                f"[tl-watcher] timeout failure handling raised for batch {batch_id[:8]}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
        finally:
            db.close()

    thread = threading.Thread(
        target=_run,
        name=f"tl-gen-{batch_id[:8]}",
        daemon=True,
    )
    thread.start()


def _stamp_live_job_progress(
    project_id: str,
    scene_id: str,
    batch_id: str,
    execution_snapshot_id: str,
    status: Any,
) -> None:
    """Copy live Job progress/phase onto generationJobs so Timeline is not stuck at 0%."""
    from .. import store
    from ..contracts import SceneTimelineMaster

    db = SessionLocal()
    try:
        payload = store.load_master(db, project_id, scene_id)
        if not payload.get("ok"):
            return
        master = SceneTimelineMaster.model_validate(payload["master"])
        batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
        if not batch:
            return
        tel = {}
        meta = getattr(status, "providerMetadata", None) or {}
        if isinstance(meta, dict):
            raw = meta.get("progressTelemetry")
            if isinstance(raw, dict):
                tel = raw
        grounded = bool(tel.get("progressGrounded"))
        progress = float(getattr(status, "progress", 0.0) or 0.0)
        changed = False
        for job in batch.generationJobs:
            if job.executionSnapshotId != execution_snapshot_id:
                continue
            if str(job.status or "").lower() in {"completed", "failed", "cancelled", "cancelling"}:
                continue
            mapped = str(getattr(status, "status", "") or job.status or "running")
            if mapped in {"queued", "running", "pending"} and job.status != mapped:
                job.status = mapped
                changed = True
            if grounded and abs(float(job.progress or 0) - progress) > 0.001:
                job.progress = progress
                changed = True
            if grounded and not job.progressGrounded:
                job.progressGrounded = True
                changed = True
            phase = tel.get("phase")
            if phase and job.phase != phase:
                job.phase = str(phase)
                job.phaseLabel = str(tel.get("phaseLabel") or "") or job.phaseLabel
                changed = True
            if tel.get("lastProgressAt") and job.lastProgressAt != tel.get("lastProgressAt"):
                job.lastProgressAt = str(tel.get("lastProgressAt"))
                changed = True
            if tel.get("lastRuntimeEventAt") and job.lastRuntimeEventAt != tel.get("lastRuntimeEventAt"):
                job.lastRuntimeEventAt = str(tel.get("lastRuntimeEventAt"))
                changed = True
            elapsed = tel.get("elapsedActiveTime")
            if elapsed is not None and job.elapsedActiveTime != elapsed:
                job.elapsedActiveTime = float(elapsed)
                changed = True
            stalled = bool(tel.get("stalled"))
            if job.stalled != stalled:
                job.stalled = stalled
                changed = True
            node = tel.get("currentNode")
            if node and job.currentNode != node:
                job.currentNode = str(node)
                changed = True
        if changed:
            store.save_master(db, project_id, scene_id, master, touch_batches=False)
    finally:
        db.close()


def _mark_job_failed(
    db: Any,
    project_id: str,
    scene_id: str,
    batch_id: str,
    execution_snapshot_id: str,
    error_code: str | None,
    error_message: str | None,
    *,
    cancelled: bool = False,
) -> None:
    from .. import store
    from ..contracts import SceneTimelineMaster

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        return
    # TERMINAL_STATUS_GUARD: a late/stale provider failure (or watcher timeout)
    # must never rewrite a batch that already reached a creator-visible terminal
    # state — an Approved/CandidateReady batch with a playable clip is truth.
    if batch.status in ("Approved", "CandidateReady"):
        print(
            f"[tl-watcher] ignoring late failure for batch {batch_id[:8]} "
            f"(status={batch.status}, code={error_code})",
            flush=True,
        )
        return
    for job in batch.generationJobs:
        if job.executionSnapshotId == execution_snapshot_id:
            job.status = "cancelled" if cancelled else "failed"
            job.error = error_message or error_code or ("cancelled" if cancelled else "failed")
    # PLAYABLE_TAKE_GUARD: a failed/cancelled Re-Take or new take must not
    # un-approve a still-playable current take. First-generation batches
    # without an approved clip still become Failed/Cancelled.
    keep_playable = bool(batch.approvedClip and batch.approvedClip.assetId)
    if keep_playable:
        batch.status = "Approved"
    else:
        batch.status = "Cancelled" if cancelled else "Failed"
    store.save_master(db, project_id, scene_id, master)
    # FAIL HALTS QUEUE: prior Complete batches stay; cancel remaining Queued so
    # Resume (resume_incomplete_only) + Generate Scene restarts from the failed
    # batch. Do not skip ahead to N+1.
    from .. import orchestrator

    if not cancelled:
        orchestrator.halt_queued_batches_after_failure(db, project_id, scene_id)
    else:
        # Cancelled active job: still clear remaining staged queue (Stop semantics).
        orchestrator.halt_queued_batches_after_failure(db, project_id, scene_id)
    from .comfy_release import release_comfy_after_timeline_generation

    release_comfy_after_timeline_generation(
        reason=f"timeline-batch-{'cancel' if cancelled else 'fail'}:{batch_id}"
    )
