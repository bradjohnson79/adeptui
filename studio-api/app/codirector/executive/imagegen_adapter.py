"""ImageGen Job+Asset lifecycle adapter for Production Executive.

When STUDIO_E2E / ADEPT_MOCK_IMAGEGEN=1 (or Comfy is unavailable), completes a
deterministic mock ImageGen through the real Job + Asset tables — never a
fake-only result inside the executive handler alone.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...config import settings
from ...db import Asset, Job
from ...script_storyboard import StoryboardPanelRow

logger = logging.getLogger(__name__)

_TRUE = frozenset({"1", "true", "TRUE", "yes", "YES", "on", "ON"})


def mock_imagegen_env_enabled() -> bool:
    return (
        os.environ.get("STUDIO_E2E", "").strip() in _TRUE
        or os.environ.get("ADEPT_MOCK_IMAGEGEN", "").strip() in _TRUE
    )


def comfy_available() -> bool:
    """Best-effort Comfy health probe; False means mock adapter may take over."""
    try:
        from ...comfy_client import comfy

        # Prefer a cheap sync-ish check if present; otherwise treat as unknown/available.
        checker = getattr(comfy, "health", None) or getattr(comfy, "is_available", None)
        if checker is None:
            return not mock_imagegen_env_enabled()
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(checker):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return not mock_imagegen_env_enabled()
                return bool(loop.run_until_complete(checker()))
            except Exception:  # noqa: BLE001
                return False
        return bool(checker())
    except Exception:  # noqa: BLE001
        return False


def should_use_mock_imagegen() -> bool:
    if mock_imagegen_env_enabled():
        return True
    return not comfy_available()


def _placeholder_png_bytes() -> bytes:
    # Minimal valid 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def complete_mock_imagegen_job(
    db: Session,
    job_id: str,
    *,
    project_id: str,
) -> str:
    """Mark studio Job done and create Asset; returns asset_id."""
    job = db.get(Job, job_id)
    if not job:
        raise ValueError(f"imagegen job not found: {job_id}")

    params: dict[str, Any]
    try:
        params = json.loads(job.params_json or "{}")
    except json.JSONDecodeError:
        params = {}

    existing = params.get("output_asset_id")
    if job.status == "done" and existing:
        return str(existing)

    asset_id = str(uuid.uuid4())
    media_root = Path(settings.data_dir) / "projects" / project_id / "assets"
    media_root.mkdir(parents=True, exist_ok=True)
    filename = f"mock-imagegen-{asset_id[:8]}.png"
    path = media_root / filename
    path.write_bytes(_placeholder_png_bytes())

    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=str(params.get("tag") or "storyboard"),
        kind="image",
        filename=filename,
        path=str(path),
        labels_json=json.dumps(params.get("labels") or ["storyboard", "mock"]),
        prompt_meta_json=json.dumps(
            {"prompt": params.get("prompt"), "mockAdapter": True}, default=str
        ),
    )
    db.add(asset)

    params["output_asset_id"] = asset_id
    params["mockAdapter"] = True
    job.params_json = json.dumps(params, default=str)
    job.status = "done"
    job.progress = 1.0
    job.message = "Mock ImageGen complete (ADEPT_MOCK_IMAGEGEN/STUDIO_E2E or Comfy unavailable)"
    job.stage = "complete"
    job.updated_at = datetime.utcnow()
    job.output_path = str(path)

    panel_id = params.get("panel_id")
    if panel_id:
        panel = db.get(StoryboardPanelRow, panel_id)
        if panel:
            panel.asset_id = asset_id
            panel.status = "complete"

    db.commit()
    return asset_id


def schedule_job_queue_enqueue(job_id: str) -> None:
    """Best-effort enqueue onto the studio job_queue from sync context."""
    try:
        import asyncio

        from ...queue_worker import job_queue

        async def _put() -> None:
            await job_queue.enqueue(job_id)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_put())
        except RuntimeError:
            asyncio.run(_put())
    except Exception:  # noqa: BLE001
        logger.warning("Could not enqueue imagegen job %s onto job_queue", job_id, exc_info=True)


def poll_imagegen_job(
    db: Session,
    job_id: str,
    *,
    project_id: str,
    timeout_sec: float = 120.0,
    poll_interval: float = 0.1,
    allow_mock: bool = True,
) -> tuple[str, bool]:
    """Poll until Job done/failed. Returns (asset_id, used_mock).

    When allow_mock and mock adapter applies, completes through Job+Asset lifecycle.
    """
    deadline = time.time() + timeout_sec
    used_mock = False

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
            return str(asset_id), used_mock

        if job.status in ("failed", "cancelled"):
            raise ValueError(job.message or f"imagegen job {job.status}")

        if allow_mock and should_use_mock_imagegen() and job.status in ("queued", "running"):
            asset_id = complete_mock_imagegen_job(db, job_id, project_id=project_id)
            used_mock = True
            return asset_id, used_mock

        time.sleep(poll_interval)

    if allow_mock and should_use_mock_imagegen():
        asset_id = complete_mock_imagegen_job(db, job_id, project_id=project_id)
        return asset_id, True

    raise TimeoutError(f"imagegen job {job_id} timed out after {timeout_sec}s")


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
