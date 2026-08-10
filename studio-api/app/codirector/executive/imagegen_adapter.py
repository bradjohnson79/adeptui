"""ImageGen Job+Asset lifecycle adapter for Production Executive.

Polls real studio Jobs only. Never invents assets or silently completes via mock.
Comfy unavailability raises a clear error — STUDIO_E2E / ADEPT_MOCK_IMAGEGEN must not
trigger mock ImageGen completion on the Adept UI runtime path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from ...db import Job

logger = logging.getLogger(__name__)

_TRUE = frozenset({"1", "true", "TRUE", "yes", "YES", "on", "ON"})


def mock_imagegen_env_enabled() -> bool:
    """True when mock-imagegen env is set — informational only; does not enable silent success."""
    return (
        os.environ.get("STUDIO_E2E", "").strip() in _TRUE
        or os.environ.get("ADEPT_MOCK_IMAGEGEN", "").strip() in _TRUE
    )


def comfy_available() -> bool:
    """Best-effort Comfy health probe (sync HTTP; safe under a running event loop)."""
    try:
        import httpx

        from ...comfy_client import comfy

        base = getattr(comfy, "base_url", None)
        if not base:
            return False
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base}/system_stats")
            return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def should_use_mock_imagegen() -> bool:
    """Always False — runtime closed-loop never substitutes mock ImageGen completion."""
    return False


def schedule_job_queue_enqueue(job_id: str) -> None:
    """Enqueue onto the studio job_queue from sync/worker thread.

    Prefer ``run_coroutine_threadsafe`` against the job_queue worker's running
    loop when available; otherwise fall back to create_task / asyncio.run.
    Raises RuntimeError on failure so handlers can Blocked.
    """
    import asyncio

    from ...queue_worker import job_queue

    async def _put() -> None:
        await job_queue.enqueue(job_id)

    try:
        queue_loop = None
        task = getattr(job_queue, "_task", None)
        if task is not None and not task.done():
            try:
                queue_loop = task.get_loop()
            except Exception:  # noqa: BLE001
                queue_loop = None

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if queue_loop is not None and queue_loop.is_running():
            # When the caller is already running on the queue loop, waiting on a
            # thread-safe future deadlocks the request thread and stretches a
            # fast enqueue into repeated timeout windows.
            if current_loop is queue_loop:
                current_loop.create_task(_put())
                return
            fut = asyncio.run_coroutine_threadsafe(_put(), queue_loop)
            fut.result(timeout=2)
            return

        if current_loop is None:
            asyncio.run(_put())
        else:
            current_loop.create_task(_put())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not enqueue imagegen job %s onto job_queue", job_id, exc_info=True
        )
        raise RuntimeError(
            f"Failed to enqueue imagegen job {job_id} onto job_queue: {exc}"
        ) from exc


def poll_imagegen_job(
    db: Session,
    job_id: str,
    *,
    project_id: str,
    timeout_sec: float = 120.0,
    poll_interval: float = 0.1,
    allow_mock: bool = False,
) -> tuple[str, bool]:
    """Poll until Job done/failed. Returns (asset_id, used_mock=False).

    Never completes via mock. If Comfy is unavailable when the job is still queued,
    raises a clear error. allow_mock is accepted for call-site compatibility but ignored.
    """
    del allow_mock  # demock: never substitute
    del project_id

    if mock_imagegen_env_enabled():
        logger.warning(
            "ADEPT_MOCK_IMAGEGEN/STUDIO_E2E is set but mock ImageGen completion is disabled; "
            "waiting for real job %s",
            job_id,
        )

    deadline = time.time() + timeout_sec
    warned_comfy = False

    while time.time() < deadline:
        db.expire_all()
        job = db.get(Job, job_id)
        if not job:
            raise ValueError(f"imagegen job not found: {job_id}")

        if job.status == "done":
            try:
                params = json.loads(job.params_json or "{}")
            except json.JSONDecodeError:
                params = {}
            asset_id = params.get("output_asset_id")
            if not asset_id:
                raise ValueError("imagegen job done but missing output_asset_id")
            return str(asset_id), False

        if job.status in ("failed", "cancelled"):
            raise ValueError(job.message or f"imagegen job {job.status}")

        if job.status in ("queued", "running") and not comfy_available() and not warned_comfy:
            # Keep polling briefly in case Comfy comes up; surface a clear error on timeout.
            warned_comfy = True
            logger.error(
                "ComfyUI unavailable while waiting on imagegen job %s — will not mock-complete",
                job_id,
            )

        time.sleep(poll_interval)

    db.expire_all()
    job = db.get(Job, job_id)
    status = job.status if job else "missing"
    msg = (job.message if job else "") or ""

    # Prefer Blocked (not Failed) for infra/queue gaps so dependents cascade cleanly.
    if status in ("queued", "running"):
        from ...queue_worker import job_queue

        queue_task = getattr(job_queue, "_task", None)
        queue_alive = queue_task is not None and not queue_task.done()
        if not queue_alive and status == "queued":
            raise RuntimeError(
                f"ImageGen job {job_id} remained queued: studio job_queue worker is not running "
                f"(unavailable). Start the API job_queue or ensure Comfy ImageGen packs/workflows "
                f"are installed."
            )
        if not comfy_available():
            raise RuntimeError(
                f"ComfyUI unavailable; imagegen job {job_id} did not complete "
                f"(mock ImageGen completion is disabled)"
            )
        raise RuntimeError(
            f"ImageGen job {job_id} stuck in {status} after {timeout_sec}s "
            f"(unavailable for closed-loop). Studio message: {msg or 'none'}. "
            f"Check Comfy checkpoint/workflow packs (storyboard.generate / workflows.image.ready)."
        )

    if not comfy_available():
        raise RuntimeError(
            f"ComfyUI unavailable; imagegen job {job_id} did not complete "
            f"(mock ImageGen completion is disabled)"
        )
    raise TimeoutError(f"imagegen job {job_id} timed out after {timeout_sec}s (status={status})")


def read_job_asset_id(db: Session, job_id: str) -> Optional[str]:
    job = db.get(Job, job_id)
    if not job:
        return None
    try:
        params = json.loads(job.params_json or "{}")
    except json.JSONDecodeError:
        return None
    asset_id = params.get("output_asset_id")
    return str(asset_id) if asset_id else None