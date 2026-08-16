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
    timeout_sec: float = 1200.0,
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
                            auto_approve=not draft,
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
    batch.status = "Cancelled" if cancelled else "Failed"
    for job in batch.generationJobs:
        if job.executionSnapshotId == execution_snapshot_id:
            job.status = "cancelled" if cancelled else "failed"
            job.error = error_message or error_code or ("cancelled" if cancelled else "failed")
    store.save_master(db, project_id, scene_id, master)
    # SEQUENTIAL_SUBMISSION_CHAIN: Failed is a terminal state — free the
    # provider slot for the next Queued batch (no-op when none queued).
    from .. import orchestrator

    orchestrator.submit_next_queued_batch(db, project_id, scene_id)
