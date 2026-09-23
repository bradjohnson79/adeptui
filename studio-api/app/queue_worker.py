from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .comfy_client import comfy
from .config import settings
from .db import Asset, Job, Project, Scene, SessionLocal
from .lipsync_tracks import dumps_lipsync_tracks, parse_lipsync_tracks
from .media_ops import export_pack, mux_audio, stitch_videos
from .mouth_tracker import Roi, track_mouth_rois
from .references import inject_spatial_and_camera, resolve_prompt
from .spatial import parse_spatial_map, spatial_prompt_notes
from .fal_catalog import (
    build_fal_arguments,
    build_fal_image_arguments,
    fal_still_edit_model_id,
    is_fal_engine,
    seedance_product_id,
)
from .fal_client import download_url, extract_image_url, extract_video_url, run_fal_model, upload_file_to_fal
from .secrets_store import get_secret
from .vram_profiles import resolve_render_plan
from .workflows import (
    build_latentsync_workflow,
    customize_angle_prompts,
    lipsync_available_hint,
    views_for_tool,
)
from .workflows.lipsync_runtime import (
    extract_output_path_from_history,
    lipsync_no_output_error,
    prepare_still_face_video,
    run_latentsync_direct,
)
from .video_runtime.runtime_event_bridge import runtime_event_bridge

logger = logging.getLogger(__name__)


def _timeline_job_is_h3(params: dict, resolved_engine: str) -> bool:
    gen = str(params.get("generatorId") or params.get("adapterId") or "").strip().lower()
    engine = str(params.get("engine") or resolved_engine or "").strip().lower()
    return gen.startswith("minimax-h3") or engine.startswith("minimax")


#: Job states that mean "an earlier process was still carrying this in memory".
#: The queue is an in-process asyncio queue, so any row left in one of these at
#: startup belongs to a process that is gone and will never touch it again.
NON_TERMINAL_STATES: tuple[str, ...] = ("queued", "running", "cancelling", "cancel_requested")

#: 1 Frame (single start image, no middle/end) may only use certified v1.1 generators.
#: Timeline / R2V batches keep their own authority and are not blocked here.
_RETIRED_1F_LEAVES: frozenset[str] = frozenset({
    "ltx.simple_i2v",
    "ltx.ingredients_ic_lora",
})

#: Recovery message written to a job the restart could not resume. It says the work
#: stopped, not that it failed on its own merits, because those are different things.
INTERRUPTED_MESSAGE = (
    "Interrupted by an API restart before it finished. The studio queue does not resume "
    "work that was already running, because the provider-side render (ComfyUI prompt or "
    "fal.ai request) cannot be re-attached and re-submitting it would repeat the work and "
    "any spend. Start it again when you are ready."
)

STALE_MESSAGE = (
    "Left queued by an API restart and too old to start automatically. Nothing was "
    "generated. Start it again when you are ready."
)

SESSION_INTERRUPTED_MESSAGE = (
    "Stopped because this render belonged to a previous session. It was not started again. "
    "Choose New Take or Re-Take when you want a new render."
)

STALE_APPROVED_CRS_MESSAGE = (
    "Left queued by an abandoned Character Creator tab. The approved look was not "
    "changed. Start a new sheet if you want a replacement."
)

NEVER_STARTED_MESSAGE = (
    "This image never started. It stayed in line and was never sent to an image engine."
)

STALE_RUNNING_MESSAGE = (
    "The local picture engine is no longer working on this job, and the worker never "
    "finished saving a result. Nothing new was added to the Library."
)

RESULT_NOT_REGISTERED_MESSAGE = (
    "The picture engine finished this job, but the studio worker never saved the result "
    "into the Library. The render itself did not fail."
)

WORKER_LOST_PROMPT_MESSAGE = (
    "The studio worker lost this job before a result was saved. The local picture engine "
    "is still reachable, but it is not working on this prompt anymore."
)

#: Queued rows older than this on API restart never reached a provider.
_NEVER_DISPATCHED_RECOVERY_SEC = 30 * 60

#: Live drain: queued-never-claimed while the worker is stuck or dead.
_NEVER_STARTED_LIVE_SEC = 180

#: Running Comfy jobs with no progress and no active prompt are orphans.
_STALE_RUNNING_SEC = 60

_DEFAULT_RECOVERY_MAX_AGE_HOURS = 24.0


def _recovery_max_age_hours() -> float:
    """How old a queued job may be and still be resumed automatically on startup."""
    raw = os.environ.get("STUDIO_JOB_RECOVERY_MAX_AGE_HOURS", "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_RECOVERY_MAX_AGE_HOURS
    return value if value > 0 else _DEFAULT_RECOVERY_MAX_AGE_HOURS


def _job_params(job: Job) -> dict:
    try:
        raw = json.loads(job.params_json or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _route_a_graph_summary(state: Any) -> str:
    graph = getattr(state, "submitted_graph", None) or {}
    if not isinstance(graph, dict):
        return ""
    cond = (graph.get("5") or {}).get("inputs") or {}
    sched = (graph.get("8") or {}).get("inputs") or {}
    parts: list[str] = []
    width = cond.get("width")
    height = cond.get("height")
    if width and height:
        parts.append(f"{int(width)}×{int(height)}")
    length = cond.get("length")
    if length:
        parts.append(f"{int(length)} frames")
    steps = sched.get("steps")
    if steps:
        parts.append(f"{int(steps)} steps")
    return " · ".join(parts)


def queued_job_is_stale_approved_crs(job: Job, db: Session | None = None) -> bool:
    """True when auto-starting this queued row would overwrite an approved look.

    Abandoned Character Creator tabs leave `korri_*` / visual-sheet rows queued.
    Recycle/drain must not resume those. An explicit new Generate still enqueues
    onto the live asyncio queue and is not classified here.
    """
    params = _job_params(job)
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    purpose = str(params.get("purpose") or ctx.get("objective") or "")
    tag = str(params.get("tag") or "")
    character_id = str(ctx.get("characterId") or params.get("characterId") or "")
    is_crs = job.kind in {"character_sheet", "imagegen"} and (
        purpose == "character_sheet"
        or tag.startswith("korri_")
        or "four_view" in tag
        or "visual-sheet" in tag
        or job.kind == "character_sheet"
    )
    if not is_crs:
        return False
    if tag.startswith("korri_") and not character_id:
        return True
    if not character_id:
        return False
    own_session = db is None
    session = db or SessionLocal()
    try:
        from .codirector.perception.character_canon import register_character_canon

        result = register_character_canon(session, job.project_id, character_id)
        return bool(result.get("ok") and result.get("approvedSheetAssetId"))
    except Exception:
        return tag.startswith("korri_")
    finally:
        if own_session:
            session.close()


def job_cancel_should_interrupt_comfy(
    job_id: str,
    *,
    job_prompt_id: str | None = None,
    active_prompt_by_job: dict[str, str] | None = None,
    heavy_local_active: str | None = None,
) -> bool:
    """Interrupt Comfy only when this job owns the in-flight prompt.

    Leftover coverage cancel must not drop a sibling CRS law-view prompt.
    """
    jid = str(job_id or "").strip()
    if not jid:
        return False
    if heavy_local_active and str(heavy_local_active) != jid:
        return False
    tracked_map = active_prompt_by_job or {}
    tracked = str(tracked_map.get(jid) or "").strip()
    bound = tracked or str(job_prompt_id or "").strip()
    if not bound:
        return False
    for other_id, other_prompt in tracked_map.items():
        if str(other_id) == jid:
            continue
        if str(other_prompt or "").strip():
            return False
    return True


class JobQueue:
    def __init__(self) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._drain_task: Optional[asyncio.Task] = None
        self._enqueued: set[str] = set()
        self._cancel: set[str] = set()
        self._active_prompt: dict[str, str] = {}
        self._heavy_local_active: Optional[str] = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
        if self._drain_task is None:
            self._drain_task = asyncio.create_task(self._drain_watchdog())
        runtime_event_bridge.start()

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancel

    def bind_prompt(self, job_id: str, prompt_id: str) -> None:
        pid = str(prompt_id or "").strip()
        if not pid:
            raise RuntimeError("Refusing to bind an empty Comfy prompt_id")
        self._active_prompt[job_id] = pid
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if job:
                job.comfy_prompt_id = pid
                if job.status == "queued":
                    job.status = "running"
                    job.stage = job.stage or "processing"
                    job.message = job.message or "Bound to ComfyUI"
                job.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def unbind_prompt(self, job_id: str) -> None:
        self._active_prompt.pop(job_id, None)

    @staticmethod
    def _job_skips_comfy_bind(job: Job) -> bool:
        try:
            params = json.loads(job.params_json or "{}")
        except Exception:
            params = {}
        if not isinstance(params, dict):
            return False
        provider = str(
            params.get("provider") or params.get("providerId") or params.get("engine") or ""
        ).lower()
        if "fal" in provider or provider == "kie":
            return True
        if provider in {"minimax-h3", "minimax_h3"}:
            # Route A :8192 skips Adept Comfy :8188 bind. Timeline H3 Ref2V
            # (h3_ref2va / adept-comfy-8188) samples on :8188 and must bind.
            if JobQueue._job_is_timeline_h3_local(job):
                return False
            return True
        return bool(params.get("cloudPaid") or params.get("useFal"))

    @staticmethod
    def _job_params_dict(job: Job) -> dict:
        try:
            params = json.loads(job.params_json or "{}")
        except Exception:
            params = {}
        return params if isinstance(params, dict) else {}

    @classmethod
    def _looks_like_provider_model_id(cls, value: str | None) -> bool:
        token = str(value or "").strip().lower()
        if not token:
            return False
        if "/" in token:
            return True
        return token.startswith(("fal-", "fal_", "kie-", "kie_", "bytedance", "wavespeed"))

    @classmethod
    def _job_is_hosted_provider(cls, job: Job) -> bool:
        params = cls._job_params_dict(job)
        provider = str(
            params.get("provider") or params.get("providerId") or params.get("engine") or ""
        ).lower()
        if "fal" in provider or provider in {"kie", "wavespeed"}:
            return True
        return bool(params.get("cloudPaid") or params.get("useFal"))

    @classmethod
    def _history_dict(cls, job: Job) -> dict:
        try:
            hist = json.loads(job.history_json or "{}")
        except Exception:
            hist = {}
        return hist if isinstance(hist, dict) else {}

    @classmethod
    def _h3_runtime_markers(cls, job: Job) -> tuple[str, str]:
        """Return (mechanism, runtime) from history/params. Empty strings if unknown."""
        params = cls._job_params_dict(job)
        hist = cls._history_dict(job)
        vr = hist.get("videoRuntime") if isinstance(hist.get("videoRuntime"), dict) else {}
        mechanism = ""
        runtime = ""
        for src in (vr, hist):
            if not isinstance(src, dict):
                continue
            for key in ("r2v", "i2v", "t2v"):
                blob = src.get(key)
                if not isinstance(blob, dict):
                    continue
                mechanism = mechanism or str(blob.get("mechanism") or "")
                runtime = runtime or str(blob.get("runtime") or "")
        if not mechanism:
            mechanism = str(params.get("mechanism") or "")
        if not runtime:
            runtime = str(params.get("runtime") or params.get("resolvedRuntime") or "")
        r2v_params = params.get("r2v")
        if isinstance(r2v_params, dict):
            mechanism = mechanism or str(r2v_params.get("mechanism") or "")
            runtime = runtime or str(r2v_params.get("runtime") or "")
        return mechanism.lower(), runtime.lower()

    @classmethod
    def _job_is_timeline_h3_local(cls, job: Job) -> bool:
        """Timeline MiniMax H3 Ref2V samples on Adept Comfy :8188, not Route A :8192."""
        mechanism, runtime = cls._h3_runtime_markers(job)
        if mechanism == "h3_ref2va":
            return True
        return "adept-comfy-8188" in runtime

    @classmethod
    def _job_is_route_a_job(cls, job: Job) -> bool:
        if cls._job_is_timeline_h3_local(job):
            return False
        mechanism, _runtime = cls._h3_runtime_markers(job)
        if mechanism.startswith("route_a"):
            return True
        params = cls._job_params_dict(job)
        engine = str(params.get("engine") or params.get("provider") or "").lower()
        if engine in {"minimax-h3", "minimax_h3"}:
            return True
        return cls._job_is_bound_route_a(job)

    @classmethod
    def _job_runtime_class(cls, job: Job) -> str:
        """Classify before any cancel touches a runtime: hosted | route_a | local_comfy."""
        if cls._job_is_hosted_provider(job):
            return "hosted"
        if cls._job_is_route_a_job(job):
            return "route_a"
        return "local_comfy"

    def _halt_client_for(self, runtime_class: str):
        from .comfy_client import ComfyClient, comfy

        if runtime_class == "route_a":
            from .minimax_h3.private_access import runtime_url

            return ComfyClient(base_url=runtime_url())
        return comfy

    @classmethod
    def _job_is_bound_route_a(cls, job: Job) -> bool:
        """True when MiniMax Route A already accepted a prompt. Never re-enqueue."""
        if not str(getattr(job, "comfy_prompt_id", "") or "").strip():
            return False
        if cls._job_is_timeline_h3_local(job):
            return False
        params = cls._job_params_dict(job)
        engine = str(params.get("engine") or params.get("provider") or "").lower()
        if engine in {"minimax-h3", "minimax_h3"}:
            return True
        mechanism, _runtime = cls._h3_runtime_markers(job)
        return mechanism.startswith("route_a")

    async def _wait_comfy(
        self,
        job: Job,
        prompt_id: str,
        *,
        on_progress: Any = None,
        preview_engine: str | None = None,
    ) -> dict:
        """Wait for Comfy with cancel observation + prompt binding. Optionally
        publish live low-res preview frames to the preview bus."""
        self.bind_prompt(job.id, prompt_id)
        # Persist prompt id on a short-lived session. Do NOT assign
        # job.comfy_prompt_id on the caller's ORM instance — that dirties the
        # outer Session for the entire wait_for_prompt span and can deadlock
        # the post-wait "Finalizing MiniMax H3 output" commit (same stranding
        # mode as the old _progress ORM write, job 98db381c).
        db_bind = SessionLocal()
        try:
            row = db_bind.get(Job, job.id)
            if row is not None and row.comfy_prompt_id != prompt_id:
                row.comfy_prompt_id = prompt_id
                row.updated_at = datetime.utcnow()
                db_bind.commit()
        finally:
            db_bind.close()

        preview_seq = 0

        async def _progress(p: float, msg: str, stage: str | None = None) -> None:
            # Never register successful progress once cancel was requested.
            if job.id in self._cancel:
                return
            # CRITICAL: do not dirty the caller's ORM Job instance here.
            # Mutating it opens a write transaction on the outer Session that
            # spans wait_for_prompt and deadlocks the SessionLocal commit below,
            # stranding MiniMax H3 at writing_output/done with a finished Comfy
            # file and no studio ingest.
            db = SessionLocal()
            try:
                row = db.get(Job, job.id)
                if row:
                    if row.status in ("cancelling", "cancel_requested", "cancelled", "cancel_failed_runtime_active"):
                        return
                    from .video_runtime.progress_telemetry import (
                        apply_heartbeat,
                        extract_progress_telemetry,
                        is_grounded_progress_message,
                        merge_progress_telemetry,
                    )

                    node = None
                    text = str(msg or "")
                    if "Executing node " in text:
                        node = text.split("Executing node ", 1)[-1].split("·", 1)[0].strip().split()[0]
                    grounded = is_grounded_progress_message(text) or (
                        float(p or 0) > 0 and "sampling step" in text.lower()
                    )
                    tel = apply_heartbeat(
                        extract_progress_telemetry(row.history_json),
                        progress=float(p or 0),
                        message=text,
                        stage=stage,
                        node=node,
                        job_status=row.status or "running",
                        grounded=grounded,
                    )
                    if grounded or float(p or 0) >= 1.0:
                        row.progress = p
                    row.message = text[:4000]
                    if stage:
                        row.stage = str(stage)[:64]
                    row.history_json = merge_progress_telemetry(row.history_json, tel)
                    row.updated_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            if on_progress:
                try:
                    result = on_progress(p, msg)
                    if hasattr(result, "__await__"):
                        await result
                except TypeError:
                    pass

        async def _preview_frame(data: bytes) -> None:
            """Publish a low-res preview frame. Failure never fails the render."""
            nonlocal preview_seq
            try:
                from .preview_bus import GenerationPreview, preview_bus

                preview_seq += 1
                # Detect format from magic bytes (JPEG FFD8 / PNG 8950).
                ext = ".jpg" if data[:2] == b"\xff\xd8" else ".png"
                path = preview_bus.save_bytes(job.id, data, ext)
                preview = GenerationPreview(
                    jobId=job.id,
                    sceneId=str(job.scene_id or ""),
                    engineId=preview_engine or "auto",
                    previewId=f"pv_{job.id[:8]}_{preview_seq}",
                    sequenceNumber=preview_seq,
                    createdAt=datetime.utcnow().isoformat(),
                    stage="live_preview",
                    progress=job.progress,
                    mediaType="image",
                    localPath=str(path),
                )
                await preview_bus.publish("preview_updated", preview)
            except Exception:
                logging.getLogger(__name__).debug("Preview publish failed", exc_info=True)

        return await comfy.wait_for_prompt(
            prompt_id,
            on_progress=_progress,
            cancel_check=lambda: job.id in self._cancel,
            on_preview_frame=_preview_frame if preview_engine else None,
        )

    async def recover_interrupted(self) -> dict[str, list[str]]:
        """Reconcile jobs an earlier process left non-terminal, before the loop starts.

        `queued` work never reached a provider, so it is re-enqueued. `running` work may
        have reached one, so it is closed as interrupted rather than silently restarted -
        a second fal.ai submission would spend credits again. Either way no row is left
        non-terminal with nothing watching it.
        """
        resumed: list[str] = []
        interrupted: list[str] = []
        cutoff = datetime.utcnow() - timedelta(hours=_recovery_max_age_hours())

        db = SessionLocal()
        try:
            rows = (
                db.query(Job)
                .filter(Job.status.in_(NON_TERMINAL_STATES))
                .order_by(Job.created_at.asc())
                .all()
            )
            for job in rows:
                created = job.created_at or datetime.utcnow()
                from .runtime_session import job_in_current_session

                if not job_in_current_session(_job_params(job)):
                    previous = job.status
                    self._note_recovery(job, action="interrupted", previous=previous, stale=True)
                    job.status = "cancelled"
                    job.stage = "interrupted"
                    job.message = SESSION_INTERRUPTED_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    interrupted.append(job.id)
                    continue
                if self._job_is_bound_route_a(job):
                    # Already on :8192. Re-enqueue would start a second GPU job.
                    # API recycle must not mark it interrupted while Route A works.
                    if job.status == "queued":
                        job.status = "running"
                        if (job.stage or "").strip().lower() in {
                            "",
                            "queued",
                            "claimed",
                            "preparing",
                        }:
                            job.stage = "processing"
                        job.updated_at = datetime.utcnow()
                    continue
                local_comfy = self._recover_local_comfy_job(db, job)
                if local_comfy == "observe":
                    continue
                if local_comfy == "harvested":
                    continue
                if local_comfy == "result_missing":
                    self._note_recovery(job, action="interrupted", previous=job.status)
                    job.status = "failed"
                    job.stage = "failed"
                    job.message = RESULT_NOT_REGISTERED_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    interrupted.append(job.id)
                    continue
                if job.status == "queued" and queued_job_is_stale_approved_crs(job, db):
                    self._note_recovery(job, action="interrupted", previous="queued", stale=True)
                    job.status = "failed"
                    job.stage = "interrupted"
                    job.message = STALE_APPROVED_CRS_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    interrupted.append(job.id)
                    continue
                if job.status == "queued" and created >= cutoff:
                    age_sec = (datetime.utcnow() - created).total_seconds()
                    stage = str(job.stage or "").strip().lower()
                    never_claimed = stage in {"", "queued"} or age_sec >= _NEVER_DISPATCHED_RECOVERY_SEC
                    if never_claimed and age_sec >= _NEVER_DISPATCHED_RECOVERY_SEC:
                        self._note_recovery(job, action="interrupted", previous="queued", stale=True)
                        job.status = "failed"
                        job.stage = "interrupted"
                        job.message = NEVER_STARTED_MESSAGE[:4000]
                        job.updated_at = datetime.utcnow()
                        interrupted.append(job.id)
                        continue
                    self._note_recovery(job, action="resumed", previous="queued")
                    resumed.append(job.id)
                    continue
                previous = job.status
                self._note_recovery(
                    job,
                    action="interrupted",
                    previous=previous,
                    stale=previous == "queued",
                )
                job.status = "failed"
                job.stage = "interrupted"
                job.message = (STALE_MESSAGE if previous == "queued" else INTERRUPTED_MESSAGE)[:4000]
                job.updated_at = datetime.utcnow()
                interrupted.append(job.id)
            if rows:
                db.commit()
            # Pack is a projection of Job rows. Recover may have just marked
            # jobs failed (e.g. e1422136 interrupted) while the parent pack
            # stayed queued — advance those packs now.
            try:
                from .codirector.execution.advance import reconcile_non_terminal_packs

                reconcile_non_terminal_packs(db, persist_artifacts=False)
            except Exception:
                logger.exception(
                    "Execution pack reconcile after recover_interrupted failed"
                )
        finally:
            db.close()

        for job_id in resumed:
            await self.enqueue(job_id)

        if resumed or interrupted:
            logger.warning(
                "Studio job queue recovery: resumed=%s interrupted=%s",
                len(resumed),
                len(interrupted),
            )
        return {"resumed": resumed, "interrupted": interrupted}

    @staticmethod
    def _note_recovery(job: Job, *, action: str, previous: str, stale: bool = False) -> None:
        """Append an audit entry to the job's history so recovery is traceable, not implied."""
        try:
            history = json.loads(job.history_json or "{}")
            if not isinstance(history, dict):
                history = {}
        except json.JSONDecodeError:
            history = {}
        entries = history.get("recovery")
        if not isinstance(entries, list):
            entries = []
        entries.append(
            {
                "action": action,
                "previousStatus": previous,
                "stale": stale,
                "at": datetime.utcnow().isoformat(),
            }
        )
        history["recovery"] = entries
        job.history_json = json.dumps(history)

    async def enqueue(self, job_id: str) -> None:
        self._enqueued.add(job_id)
        await self._q.put(job_id)

    async def drain_orphaned_queued(self) -> dict[str, list[str]]:
        """Start DB-queued jobs that never made it onto the in-memory asyncio queue.

        After a cancelled/zombie job the consumer can continue while newer ImageProduct
        rows remain `queued` only in SQLite. Periodic drain closes that hole without
        recycling the API process (which would also resume leftover approved CRS).
        """
        started: list[str] = []
        abandoned: list[str] = []
        unbound_failed = await asyncio.to_thread(self.fail_unbound_running)
        stale_running = await asyncio.to_thread(self.fail_stale_running_comfy)
        never_started = await asyncio.to_thread(
            self.fail_never_started_queued, force=bool(stale_running)
        )
        db = SessionLocal()
        try:
            rows = (
                db.query(Job)
                .filter(Job.status == "queued")
                .order_by(Job.created_at.asc())
                .all()
            )
            to_start: list[str] = []
            for job in rows:
                if job.id in self._enqueued:
                    continue
                from .runtime_session import job_in_current_session

                if not job_in_current_session(_job_params(job)):
                    self._note_recovery(job, action="interrupted", previous="queued", stale=True)
                    job.status = "cancelled"
                    job.stage = "interrupted"
                    job.message = SESSION_INTERRUPTED_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    abandoned.append(job.id)
                    continue
                if queued_job_is_stale_approved_crs(job, db):
                    self._note_recovery(job, action="interrupted", previous="queued", stale=True)
                    job.status = "failed"
                    job.stage = "interrupted"
                    job.message = STALE_APPROVED_CRS_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    abandoned.append(job.id)
                    continue
                to_start.append(job.id)
            if abandoned:
                db.commit()
        finally:
            db.close()
        for job_id in to_start:
            await self.enqueue(job_id)
            started.append(job_id)
        if started or abandoned or stale_running or never_started:
            logger.warning(
                "Studio job queue drain: started=%s abandoned_approved_crs=%s stale_running=%s never_started=%s",
                len(started),
                len(abandoned),
                len(stale_running),
                len(never_started),
            )
        if self._task is not None and self._task.done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                self._task = loop.create_task(self._loop())
                logger.warning("Studio job queue loop was dead; restarted after drain")
        return {
            "started": started,
            "abandoned": abandoned,
            "unboundFailed": unbound_failed,
            "staleRunning": stale_running,
            "neverStarted": never_started,
        }

    @staticmethod
    def _comfy_prompt_activity(prompt_id: str) -> str:
        """Return active | done | idle | unknown for a Comfy prompt. Observe only."""
        pid = (prompt_id or "").strip()
        if not pid:
            return "unknown"
        try:
            import httpx

            from .comfy_client import comfy

            base = getattr(comfy, "base_url", None)
            if not base:
                return "unknown"
            with httpx.Client(timeout=5.0) as client:
                hist = client.get(f"{base}/history/{pid}")
                if hist.status_code == 200:
                    entry = (hist.json() or {}).get(pid) or {}
                    status = entry.get("status") or {}
                    if status.get("completed") is True or status.get("status_str") in {
                        "success",
                        "error",
                    }:
                        return "done"
                queue = client.get(f"{base}/queue")
                if queue.status_code == 200:
                    payload = queue.json() or {}
                    running = payload.get("queue_running") or []
                    pending = payload.get("queue_pending") or []
                    ids = [item[1] for item in (running + pending) if isinstance(item, (list, tuple)) and len(item) > 1]
                    if pid in ids:
                        return "active"
            return "idle"
        except Exception:
            return "unknown"

    @staticmethod
    def _comfy_runtime_reachable() -> bool:
        """True when Adept Comfy :8188 answers a cheap health probe."""
        try:
            import httpx

            from .comfy_client import comfy

            base = getattr(comfy, "base_url", None)
            if not base:
                return False
            with httpx.Client(timeout=3.0) as client:
                stats = client.get(f"{base}/system_stats")
            return stats.status_code == 200
        except Exception:
            return False

    def _recover_local_comfy_job(self, db: Session, job: Job) -> str:
        """Observe or harvest a local :8188 prompt after an API process change.

        Returns observe | harvested | result_missing | skip.
        skip means this is not a bound local Comfy job — caller keeps existing recovery.
        """
        if JobQueue._job_skips_comfy_bind(job):
            return "skip"
        prompt_id = str(job.comfy_prompt_id or "").strip()
        if not prompt_id:
            return "skip"
        activity = self._comfy_prompt_activity(prompt_id)
        if activity in {"active", "unknown"}:
            self._note_recovery(job, action="observe", previous=job.status)
            if job.status == "queued":
                job.status = "running"
                if (job.stage or "").strip().lower() in {"", "queued", "claimed", "preparing"}:
                    job.stage = "processing"
            job.updated_at = datetime.utcnow()
            return "observe"
        if activity == "done":
            if self._harvest_completed_local_comfy_job(db, job):
                self._note_recovery(job, action="harvested", previous=job.status)
                return "harvested"
            return "result_missing"
        return "skip"

    def _harvest_completed_local_comfy_job(self, db: Session, job: Job) -> bool:
        """Register a finished :8188 prompt onto the existing job. No resubmit."""
        if str(job.status or "").lower() in {"cancelled", "canceled"}:
            return False
        prompt_id = str(job.comfy_prompt_id or "").strip()
        if not prompt_id:
            return False
        try:
            import httpx

            from .comfy_client import comfy

            base = getattr(comfy, "base_url", None)
            if not base:
                return False
            with httpx.Client(timeout=8.0) as client:
                hist = client.get(f"{base}/history/{prompt_id}")
            if hist.status_code != 200:
                return False
            entry = (hist.json() or {}).get(prompt_id) or {}
            files = comfy.find_output_files(entry)
            if not files:
                return False
            src = files[0]
            dest_dir = settings.data_dir / "projects" / job.project_id / "renders"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"reconciled_{job.id[:8]}_{src.name}"
            if not dest.is_file():
                shutil.copy2(src, dest)
            suffix = dest.suffix.lower()
            if suffix in {".mp4", ".webm", ".mov", ".mkv"}:
                from .video_runtime.output_gate import validate_video_output

                gate = validate_video_output(dest, asset_registered=False)
                if not gate.passed:
                    return False
                from .video_runtime.scene_output_library import register_render_output_asset

                params = _job_params(job)
                out_asset = register_render_output_asset(
                    db,
                    project_id=job.project_id,
                    dest=dest,
                    tag=str(params.get("batchBlockId") or job.kind or "reconciled")[:64],
                    prompt_meta={
                        "engine": params.get("engine") or job.kind,
                        "comfyPromptId": prompt_id,
                        "reconciled": True,
                    },
                )
                params = {**params, "outputAssetIds": [out_asset.id], "output_asset_id": out_asset.id}
                job.params_json = json.dumps(params)
            job.output_path = str(dest)
            job.status = "done"
            job.stage = "complete"
            job.progress = 1.0
            job.message = "Scene render complete" if job.kind == "render_scene" else "Render complete"
            job.updated_at = datetime.utcnow()
            if job.scene_id:
                scene = db.get(Scene, job.scene_id)
                if scene is not None:
                    scene.output_path = str(dest)
            self._bind_harvested_timeline_job(db, job)
            return True
        except Exception:
            logger.exception("Failed to harvest completed Comfy prompt %s for job %s", prompt_id, job.id)
            return False

    def _bind_harvested_timeline_job(self, db: Session, job: Job) -> None:
        """Replay Timeline completion after an API recycle so the active Take receives the asset."""
        params = _job_params(job)
        batch_id = str(params.get("batchBlockId") or "").strip()
        snap_id = str(params.get("executionSnapshotId") or "").strip()
        asset_ids = [str(x) for x in (params.get("outputAssetIds") or []) if x]
        if not (job.scene_id and batch_id and snap_id and asset_ids):
            return
        try:
            from .director_timeline_w46.generation.completion import apply_shared_completion
            from .director_timeline_w46.generation.contracts import (
                NormalizedJobSubmission,
                TimelineGenerationResult,
            )

            submission = NormalizedJobSubmission(
                internalJobId=job.id,
                providerJobId=str(job.comfy_prompt_id or "") or None,
                queueJobId=job.id,
                generatorId=str(params.get("generatorId") or params.get("engine") or "minimax-h3"),
                status="completed",
                apiUsed=False,
                providerMetadata={
                    "projectId": job.project_id,
                    "sceneId": job.scene_id,
                    "batchBlockId": batch_id,
                    "executionSnapshotId": snap_id,
                    "outputAssetIds": asset_ids,
                    "reconciled": True,
                },
            )
            result = TimelineGenerationResult(
                internalJobId=job.id,
                providerJobId=str(job.comfy_prompt_id or "") or None,
                queueJobId=job.id,
                generatorId=submission.generatorId,
                status="completed",
                progress=1.0,
                outputAssetIds=asset_ids,
                apiUsed=False,
                providerMetadata=submission.providerMetadata,
            )
            apply_shared_completion(
                db,
                project_id=job.project_id,
                scene_id=str(job.scene_id),
                batch_id=batch_id,
                execution_snapshot_id=snap_id,
                result=result,
                job=submission,
                auto_approve=False,
            )
        except Exception:
            logger.exception("Harvested job %s did not bind to Timeline Take", job.id)

    def fail_stale_running_comfy(self, *, older_than_sec: int = _STALE_RUNNING_SEC) -> list[str]:
        """Fail or reconcile running local jobs whose Comfy prompt is finished or gone."""
        failed: list[str] = []
        mutated = False
        cutoff = datetime.utcnow() - timedelta(seconds=max(1, int(older_than_sec)))
        db = SessionLocal()
        try:
            rows = (
                db.query(Job)
                .filter(Job.status == "running")
                .order_by(Job.updated_at.asc())
                .all()
            )
            for job in rows:
                if JobQueue._job_skips_comfy_bind(job):
                    continue
                prompt_id = str(job.comfy_prompt_id or "").strip()
                if not prompt_id:
                    continue
                updated = job.updated_at or job.created_at or datetime.utcnow()
                if updated > cutoff:
                    continue
                activity = self._comfy_prompt_activity(prompt_id)
                if activity == "active" or activity == "unknown":
                    continue
                if activity == "done":
                    if self._harvest_completed_local_comfy_job(db, job):
                        self._note_recovery(job, action="harvested", previous="running")
                        mutated = True
                        continue
                    job.status = "failed"
                    job.stage = "failed"
                    job.message = RESULT_NOT_REGISTERED_MESSAGE[:4000]
                    job.updated_at = datetime.utcnow()
                    failed.append(job.id)
                    continue
                job.status = "failed"
                job.stage = "failed"
                job.message = (
                    STALE_RUNNING_MESSAGE if not self._comfy_runtime_reachable() else WORKER_LOST_PROMPT_MESSAGE
                )[:4000]
                job.updated_at = datetime.utcnow()
                failed.append(job.id)
            if failed or mutated:
                db.commit()
        finally:
            db.close()
        return failed

    def fail_never_started_queued(
        self,
        *,
        older_than_sec: int = _NEVER_STARTED_LIVE_SEC,
        force: bool = False,
    ) -> list[str]:
        """Fail queued jobs that cannot dispatch (worker dead or blocked on a stale local job)."""
        failed: list[str] = []
        cutoff = datetime.utcnow() - timedelta(seconds=max(1, int(older_than_sec)))
        loop_dead = self._task is None or self._task.done()
        stale_blocker = bool(force)
        db = SessionLocal()
        try:
            if not stale_blocker:
                running = (
                    db.query(Job)
                    .filter(Job.status == "running")
                    .all()
                )
                for row in running:
                    if JobQueue._job_skips_comfy_bind(row):
                        continue
                    updated = row.updated_at or row.created_at or datetime.utcnow()
                    if updated > datetime.utcnow() - timedelta(seconds=_STALE_RUNNING_SEC):
                        continue
                    prompt_id = str(row.comfy_prompt_id or "").strip()
                    activity = self._comfy_prompt_activity(prompt_id) if prompt_id else "idle"
                    if activity in {"done", "idle"}:
                        stale_blocker = True
                        break
            if not loop_dead and not stale_blocker:
                return failed
            rows = (
                db.query(Job)
                .filter(Job.status == "queued")
                .order_by(Job.created_at.asc())
                .all()
            )
            for job in rows:
                created = job.created_at or datetime.utcnow()
                if created > cutoff:
                    continue
                stage = str(job.stage or "").strip().lower()
                if stage not in {"", "queued"}:
                    continue
                job.status = "failed"
                job.stage = "failed"
                job.message = NEVER_STARTED_MESSAGE[:4000]
                job.updated_at = datetime.utcnow()
                failed.append(job.id)
            if failed:
                db.commit()
        finally:
            db.close()
        return failed

    def fail_unbound_running(self, *, older_than_sec: int = 45) -> list[str]:
        """Fail running Comfy jobs that never received a prompt_id (bind-or-fail)."""
        failed: list[str] = []
        cutoff = datetime.utcnow() - timedelta(seconds=older_than_sec)
        db = SessionLocal()
        try:
            rows = (
                db.query(Job)
                .filter(Job.status == "running")
                .order_by(Job.updated_at.asc())
                .all()
            )
            for job in rows:
                if job.comfy_prompt_id:
                    continue
                if job.id in self._active_prompt:
                    continue
                if str(job.stage or "") != "claimed":
                    continue
                if JobQueue._job_skips_comfy_bind(job):
                    continue
                updated = job.updated_at or job.created_at or datetime.utcnow()
                if updated > cutoff:
                    continue
                job.status = "failed"
                job.stage = "failed"
                job.message = "Failed closed: running without a bound Comfy prompt_id."
                job.updated_at = datetime.utcnow()
                failed.append(job.id)
            if failed:
                db.commit()
        finally:
            db.close()
        return failed

    async def _drain_watchdog(self) -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await self.drain_orphaned_queued()
            except Exception:
                logger.exception("Studio job queue drain watchdog failed")

    def cancel(self, job_id: str) -> None:
        self._cancel.add(job_id)

    async def cancel_and_halt(self, job_id: str) -> dict:
        """Verified deep cancel: classify runtime, then halt only that runtime.
        # CANCEL_PROVENANCE: attribute mysterious mid-sample cancels (Scene11 B2).
        try:
            import traceback as _tb
            logger.warning(
                "CANCEL_PROVENANCE job_id=%s stack=\n%s",
                job_id,
                "".join(_tb.format_stack(limit=30)),
            )
            try:
                Path = __import__("pathlib").Path
                Path(r"C:\AdeptFilmWorks\AIVideoStudio\data\cancel_provenance.log").open("a", encoding="utf-8").write(
                    f"{__import__('datetime').datetime.utcnow().isoformat()}Z job={job_id}\n{''.join(_tb.format_stack(limit=30))}\n---\n"
                )
            except Exception:
                pass
        except Exception:
            logger.exception("CANCEL_PROVENANCE log failed for %s", job_id)

        ``local_comfy`` → Adept Comfy :8188.
        ``route_a`` → MiniMax H3 :8192 (no /free — warm residency).
        ``hosted`` → never interrupt Comfy; CANCEL_REJECTED until a real remote cancel exists.
        """
        self._cancel.add(job_id)
        prompt_id = self._active_prompt.get(job_id)
        runtime_class = "local_comfy"
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return {"ok": False, "error": "job_not_found"}
            if job.status == "cancelled" and job.stage == "cancelled":
                return {"ok": True, "alreadyCancelled": True, "promptId": job.comfy_prompt_id}
            runtime_class = self._job_runtime_class(job)
            stored_prompt = str(job.comfy_prompt_id or "").strip()
            if runtime_class == "hosted" or self._looks_like_provider_model_id(stored_prompt):
                prompt_id = None
            elif not prompt_id and stored_prompt:
                prompt_id = stored_prompt

            if runtime_class == "hosted":
                self._cancel.discard(job_id)
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(
                    job.history_json,
                    {
                        "cancelRequestedAt": datetime.utcnow().isoformat(),
                        "cancelRejected": True,
                        "cancelReason": "PROVIDER_CANCEL_UNSUPPORTED",
                    },
                )
                job.message = (
                    "This hosted generator cannot cancel a running job. "
                    "The remote generation continues until it finishes."
                )
                job.updated_at = datetime.utcnow()
                db.commit()
                return {
                    "ok": False,
                    "status": job.status,
                    "cancelRejected": True,
                    "cancelReason": "PROVIDER_CANCEL_UNSUPPORTED",
                    "confirmedStopped": False,
                    "halt": {"interrupt": False, "confirmedStopped": False, "hosted": True},
                }

            owns_active = job_cancel_should_interrupt_comfy(
                job_id,
                job_prompt_id=prompt_id,
                active_prompt_by_job=dict(self._active_prompt),
                heavy_local_active=self._heavy_local_active,
            )
            runtime_label = "MiniMax H3" if runtime_class == "route_a" else "ComfyUI"
            job.status = "cancelling"
            job.stage = "cancelling"
            job.message = (
                f"Cancel requested — waiting for {runtime_label} to confirm prompt stopped"
                if owns_active
                else "Cancel requested — isolating leftover job (active prompt untouched)"
            )
            job.updated_at = datetime.utcnow()
            from .video_runtime.job_model import merge_video_runtime_history

            job.history_json = merge_video_runtime_history(
                job.history_json,
                {
                    "stage": "cancelling",
                    "cancelRequestedAt": datetime.utcnow().isoformat(),
                    "promptId": prompt_id,
                    "isolatedCancel": not owns_active,
                    "runtimeClass": runtime_class,
                },
            )
            db.commit()
        finally:
            db.close()

        halt_client = self._halt_client_for(runtime_class)
        if not owns_active:
            if prompt_id:
                try:
                    await halt_client.delete_queue_prompt(prompt_id)
                except Exception:
                    logger.exception("Isolated cancel could not delete queued prompt %s", prompt_id)
            self._set_status(
                job_id,
                "cancelled",
                0,
                "Cancelled leftover job without interrupting the active generation",
                stage="cancelled",
                video_runtime_patch={
                    "stage": "cancelled",
                    "failureClass": "user_cancellation",
                    "computeConsumed": False,
                    "isolatedCancel": True,
                    "runtimeClass": runtime_class,
                },
            )
            return {
                "ok": True,
                "status": "cancelled",
                "promptId": prompt_id,
                "halt": {"interrupt": False, "confirmedStopped": True, "isolated": True},
                "confirmedStopped": True,
                "isolated": True,
                "runtimeClass": runtime_class,
            }

                # Phase 5: Prop Advanced angle cancel must NOT /free — keep residency + ref-encode session healthy.
        preserve_prop_angle = False
        try:
            from .image_runtime.prop_angle_session import (
                note_angle_cancelled,
                should_preserve_residency_on_cancel,
            )
            _dbp = SessionLocal()
            try:
                _jp = _dbp.get(Job, job_id)
                _params = {}
                if _jp is not None:
                    try:
                        _params = json.loads(_jp.params_json or "{}") or {}
                    except Exception:
                        _params = {}
                preserve_prop_angle = should_preserve_residency_on_cancel(_params)
                if preserve_prop_angle:
                    angle_name = ""
                    ctx = _params.get("creativeContext") if isinstance(_params.get("creativeContext"), dict) else {}
                    angle_name = str(ctx.get("angle") or "")
                    cancel_meta = note_angle_cancelled(job_id, angle=angle_name)
                    # Keep residency marker so next same-family angle skips unload.
                    try:
                        from .image_runtime.residency import note_still_loaded
                        fam = str(_params.get("modelFamilyPreference") or _params.get("modelFamily") or "qwen_edit_2509")
                        note_still_loaded(fam or "qwen_edit_2509", "prop_creator")
                    except Exception:
                        pass
                    if _jp is not None:
                        from .video_runtime.job_model import merge_video_runtime_history
                        _jp.history_json = merge_video_runtime_history(
                            _jp.history_json,
                            {
                                "angleSessionCancel": cancel_meta,
                                "preserveResidencyOnCancel": True,
                                "requestFreeMemory": False,
                            },
                        )
                        _dbp.add(_jp)
                        _dbp.commit()
            finally:
                _dbp.close()
        except Exception:
            logger.debug("prop angle cancel residency preserve skipped", exc_info=True)

        halt = await halt_client.halt_prompt(
            prompt_id,
            confirm_timeout_sec=20.0,
            request_free_memory=(runtime_class == "local_comfy" and not preserve_prop_angle),
        )

        confirmed = bool(halt.get("confirmedStopped"))
        if confirmed:
            runtime_label = "MiniMax H3" if runtime_class == "route_a" else "ComfyUI"
            self._set_status(
                job_id,
                "cancelled",
                0,
                f"Cancelled — {runtime_label} confirmed prompt is no longer active or queued",
                stage="cancelled",
                video_runtime_patch={
                    "stage": "cancelled",
                    "failureClass": "user_cancellation",
                    "computeConsumed": bool(prompt_id),
                    "halt": halt,
                    "vramFullyReleased": False,
                    "runtimeClass": runtime_class,
                },
            )
            if self._heavy_local_active == job_id:
                self._heavy_local_active = None
            return {
                "ok": True,
                "status": "cancelled",
                "promptId": prompt_id,
                "halt": halt,
                "confirmedStopped": True,
                "runtimeClass": runtime_class,
            }

        self._set_status(
            job_id,
            "cancel_failed_runtime_active",
            0,
            (
                "Cancel failed — interrupt/delete sent but the runtime prompt remained "
                "active or queued (COMFY_CANCEL_NOT_CONFIRMED)."
            ),
            stage="cancel_failed_runtime_active",
            video_runtime_patch={
                "stage": "cancel_failed_runtime_active",
                "failureClass": "COMFY_CANCEL_NOT_CONFIRMED",
                "errorCode": "COMFY_CANCEL_NOT_CONFIRMED",
                "computeConsumed": True,
                "halt": halt,
                "retrySafe": False,
                "settingsShouldChange": True,
                "runtimeClass": runtime_class,
            },
        )
        return {
            "ok": False,
            "status": "cancel_failed_runtime_active",
            "errorCode": "COMFY_CANCEL_NOT_CONFIRMED",
            "promptId": prompt_id,
            "halt": halt,
            "confirmedStopped": False,
            "runtimeClass": runtime_class,
        }

    async def _loop(self) -> None:
        while True:
            job_id = await self._q.get()
            self._enqueued.discard(job_id)
            try:
                if job_id in self._cancel:
                    self._cancel.discard(job_id)
                    self._set_status(job_id, "cancelled", 0, "Cancelled")
                    continue
                await self._run_job(job_id)
            except Exception as exc:
                from .comfy_client import JobCancelledError
                from .video_runtime.failures import classify_exception, failure_payload

                if isinstance(exc, JobCancelledError) or job_id in self._cancel:
                    # Deep cancel is owned by cancel_and_halt — do not race it to
                    # "cancelled" before Comfy confirms the prompt stopped.
                    db = SessionLocal()
                    try:
                        row = db.get(Job, job_id)
                        terminal = row and row.status in (
                            "cancelled",
                            "cancel_failed_runtime_active",
                            "cancelling",
                        )
                    finally:
                        db.close()
                    if not terminal:
                        # Cancel observed in-worker without API cancel_and_halt path.
                        await self.cancel_and_halt(job_id)
                    self._cancel.discard(job_id)
                else:
                    fc = classify_exception(exc)
                    summary = str(exc).strip().splitlines()[0][:280] or "Job failed"
                    detail = traceback.format_exc()[-1500:]
                    payload = failure_payload(
                        fc,
                        message=summary,
                        compute_consumed=True,
                        details={"traceback": detail},
                    )
                    # Preview Monitor is creator-facing: summary only.
                    # Traceback lives in failure.details, behind Show Details.
                    message = summary[:4000]
                    self._set_status(
                        job_id,
                        "failed",
                        0,
                        message,
                        video_runtime_patch={
                            "stage": "failed",
                            "failure": payload,
                        },
                    )
            finally:
                self.unbind_prompt(job_id)
                if self._heavy_local_active == job_id:
                    self._heavy_local_active = None
                try:
                    from .image_runtime.prop_angle_session import release_inflight
                    release_inflight(job_id)
                except Exception:
                    logger.debug("prop angle release_inflight skipped", exc_info=True)
                self._q.task_done()
                try:
                    await self.drain_orphaned_queued()
                except Exception:
                    logger.exception("Studio job queue drain after job %s failed", job_id)

    def _set_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        message: str,
        output: str | None = None,
        video_runtime_patch: dict | None = None,
        stage: str | None = None,
    ) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            if job.status in {"cancelled", "canceled"} and status not in {"cancelled", "canceled"}:
                logger.info(
                    "Refusing status walk-back %s → %s for cancelled job %s",
                    job.status,
                    status,
                    job_id,
                )
                return
            job.status = status
            job.progress = progress
            job.message = message[:4000]
            if video_runtime_patch:
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(job.history_json, video_runtime_patch)
            if stage:
                job.stage = stage
            else:
                # Infer only when the caller did not set an explicit stage.
                # "Loading MiniMax…" must not pin the UI on preparing.
                low = (message or "").lower()
                if "prepar" in low:
                    job.stage = "preparing"
                elif "assembl" in low or "stitch" in low:
                    job.stage = "assembling"
                elif "lipsync" in low or "mix" in low or "post" in low:
                    job.stage = "post"
                elif status == "running":
                    job.stage = job.stage or "processing"
                elif status == "done":
                    job.stage = "complete"
            if status == "failed":
                job.stage = "failed"
            elif status == "cancelled":
                job.stage = "cancelled"
            job.updated_at = datetime.utcnow()
            if output:
                job.output_path = output
            db.commit()
            # Bridge Studio JobQueue completion → Co-Director SSE job.* events.
            # No-op for non-Co-Director jobs (no executionId in params). All
            # failures are swallowed inside the bridge so the completion path
            # never breaks. The pack store remains the source of truth.
            try:
                from .codirector.execution.events import bridge_job_status_change

                bridge_job_status_change(db, job_id, status, stage=stage or "", message=message)
            except Exception:
                logger.exception("bridge_job_status_change failed for job %s", job_id)
        finally:
            db.close()

    async def _run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            if job.status in ("done", "failed", "cancelled", "canceled"):
                return
            project = db.get(Project, job.project_id)
            if not project:
                raise RuntimeError("Project missing")
            job.status = "queued"
            job.stage = "claimed"
            job.progress = 0.05
            job.message = "Claimed — waiting for runtime bind"
            if self._job_skips_comfy_bind(job):
                job.status = "running"
                job.stage = "processing"
                job.message = "Starting"
            job.updated_at = datetime.utcnow()
            try:
                from .video_runtime.job_model import merge_video_runtime_history

                hops = {}
                try:
                    hist = json.loads(job.history_json or "{}")
                    if isinstance(hist, dict):
                        hops = dict((hist.get("videoRuntime") or {}).get("queueHops") or {})
                except Exception:
                    hops = {}
                hops["claimedAt"] = datetime.utcnow().isoformat()
                job.history_json = merge_video_runtime_history(
                    job.history_json, {"queueHops": hops}
                )
            except Exception:
                pass
            db.commit()

            if job.id in self._cancel:
                job.status = "cancelled"
                job.stage = "cancelled"
                job.message = "Cancelled before execution"
                db.commit()
                return

            # W47 / Law 27: Docker Local — wait for runtime/GPU; never silent substitute
            try:
                params = {}
                if job.params_json:
                    import json as _json

                    params = _json.loads(job.params_json) if isinstance(job.params_json, str) else (job.params_json or {})
                model_id = params.get("modelId") or params.get("activeModelId") or params.get("runtimeModelId")
                if model_id and str(model_id).startswith("docker-runtime:"):
                    from .docker_runtime.queue_hooks import ensure_docker_runtime_ready, reserve_vram, release_vram

                    gate = ensure_docker_runtime_ready(str(model_id))
                    if not gate.get("ok"):
                        job.status = "queued"
                        job.stage = str(gate.get("stage") or "waiting_for_runtime")
                        job.message = str(gate.get("message") or "Waiting for Docker runtime")
                        job.progress = 0.02
                        job.updated_at = datetime.utcnow()
                        hist = {}
                        try:
                            hist = _json.loads(job.history_json) if job.history_json else {}
                        except Exception:
                            hist = {}
                        if not isinstance(hist, dict):
                            hist = {}
                        hist["dockerRuntimeGate"] = gate
                        hist["noSilentFallback"] = True
                        job.history_json = _json.dumps(hist)
                        db.commit()
                        return
                    rid = str(gate.get("runtimeId") or "")
                    vram = float(params.get("estimatedVramGb") or 0)
                    if rid and vram:
                        reserve_vram(rid, vram)
                    # Attach provenance onto history for asset consumers
                    hist = {}
                    try:
                        hist = _json.loads(job.history_json) if job.history_json else {}
                    except Exception:
                        hist = {}
                    if not isinstance(hist, dict):
                        hist = {}
                    hist["dockerRuntimeProvenance"] = gate.get("provenance") or {
                        "runtimeId": rid,
                        "fallbackUsed": False,
                    }
                    job.history_json = _json.dumps(hist)
                    job.message = "Docker runtime ready"
                    db.commit()
                    # release reservation when job finishes is best-effort below via finally pattern
                    self._docker_vram_lease = (rid, vram)  # type: ignore[attr-defined]
            except Exception:
                pass

            if job.kind == "video_upscale":
                # Honest deferred path — do not pretend SeedVR2 ran.
                job.status = "failed"
                job.stage = "failed"
                job.message = (
                    "video.upscale is deferred in M41 4.1A. The SeedVR2 worker path is not "
                    "implemented; capabilityState=deferred. No compute was consumed."
                )
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(
                    job.history_json,
                    {
                        "failureClass": "workflow_invalid",
                        "capabilityState": "deferred",
                        "computeConsumed": False,
                        "retrySafe": False,
                    },
                )
                db.commit()
                return

            if job.kind in ("render_scene", "render_shot"):
                await self._render_scene(db, job, project)
            elif job.kind in ("render_timeline", "batch_timeline"):
                await self._render_timeline(db, job, project, batch=job.kind == "batch_timeline")
            elif job.kind == "editor_mix":
                await self._editor_mix(db, job, project)
            elif job.kind == "lipsync":
                await self._lipsync(db, job, project)
            elif job.kind == "export":
                await self._export(db, job, project)
            elif job.kind in ("character_sheet", "multi_angle"):
                await self._image_tool(db, job, project)
            elif job.kind == "dual_lipsync":
                await self._dual_lipsync(db, job, project)
            elif job.kind == "media_retake":
                await self._media_retake(db, job, project)
            elif job.kind == "performance_retake":
                await self._performance_retake(db, job, project)
            elif job.kind == "video_extend":
                await self._video_extend_local(db, job, project)
            elif job.kind == "txt2vid":
                # video.extend may have been queued as txt2vid historically — route local extend
                params = self._job_params(job)
                vr = params.get("videoRuntime") if isinstance(params.get("videoRuntime"), dict) else {}
                if (params.get("mode") == "generative_continuation") or (
                    isinstance(vr, dict) and vr.get("mode") == "video_extend"
                ):
                    await self._video_extend_local(db, job, project)
                else:
                    await self._txt2vid(db, job, project)
            elif job.kind in ("imagegen", "imagegen_edit"):
                await self._imagegen(db, job, project)
            elif job.kind == "magi_overlay_compose":
                from .magi.composition.service import run_overlay_compose_job

                run_overlay_compose_job(db, job)
            elif job.kind in ("magi_upscale", "magi_audio_generate", "magi_final_render"):
                from .magi.jobs import claim_job, finish_job

                if job.status in {"done", "failed", "cancelled", "canceled", "timed_out", "running"}:
                    return
                claim_job(db, job)
                if job.kind == "magi_upscale":
                    from .magi.upscaling import run_upscale_job

                    result = run_upscale_job(db, job)
                elif job.kind == "magi_audio_generate":
                    from .magi.audio_generate import run_audio_job

                    result = run_audio_job(db, job)
                else:
                    from .magi.final_render import run_final_render_job

                    result = run_final_render_job(db, job)
                finish_job(
                    db,
                    job,
                    ok=bool(result.get("ok")),
                    message=str(result.get("message") or ("Ready" if result.get("ok") else "Failed")),
                    result=result,
                )
            else:
                raise RuntimeError(f"Unknown job kind {job.kind}")
        finally:
            db.close()

    def _asset_map(self, db: Session, project_id: str) -> dict[str, tuple[str, str]]:
        assets = db.query(Asset).filter(Asset.project_id == project_id).all()
        out: dict[str, tuple[str, str]] = {}
        for a in assets:
            if a.tag:
                out[a.tag.lstrip("@")] = (a.id, a.comfy_name or a.filename)
        return out

    def _get_asset(self, db: Session, asset_id: str | None) -> Asset | None:
        if not asset_id:
            return None
        return db.get(Asset, asset_id)

    def _persist_comfy_name(self, asset_id: str, comfy_name: str) -> None:
        db = SessionLocal()
        try:
            row = db.get(Asset, asset_id)
            if row and row.comfy_name != comfy_name:
                row.comfy_name = comfy_name
                db.commit()
        finally:
            db.close()

    async def _stage_library_asset(self, asset: Asset | None) -> str | None:
        if not asset:
            self._last_staged_comfy = None
            return None
        from .video_runtime.comfy_asset_stage import ComfyAssetMissing, ComfyAssetStagingFailed, stage_library_asset

        try:
            staged = await asyncio.to_thread(stage_library_asset, asset)
        except (ComfyAssetMissing, ComfyAssetStagingFailed):
            self._last_staged_comfy = None
            return None
        self._persist_comfy_name(asset.id, staged.comfy_name)
        # Phase 4: expose stage reuse to ref-encode cache instrumentation.
        self._last_staged_comfy = {
            "assetId": staged.asset_id,
            "comfyName": staged.comfy_name,
            "reused": bool(staged.reused),
            "bytes": int(staged.bytes),
            "sourcePath": staged.source_path,
        }
        return staged.comfy_name

    async def _stage_h3_visual_asset(self, asset: Asset | None, role: str = ""):
        if not asset:
            return None
        from .video_runtime.comfy_asset_stage import (
            ComfyAssetMissing,
            ComfyAssetStagingFailed,
            stage_h3_visual_asset,
        )

        try:
            staged = await asyncio.to_thread(stage_h3_visual_asset, asset, role=role)
        except (ComfyAssetMissing, ComfyAssetStagingFailed):
            return None
        self._persist_comfy_name(asset.id, staged.comfy_name)
        return staged

    async def _stage_direct_visual_asset(self, asset: Asset | None):
        if not asset:
            return None
        from .video_runtime.comfy_asset_stage import (
            ComfyAssetMissing,
            ComfyAssetStagingFailed,
            stage_library_asset,
        )

        try:
            staged = await asyncio.to_thread(stage_library_asset, asset)
        except (ComfyAssetMissing, ComfyAssetStagingFailed):
            return None
        self._persist_comfy_name(asset.id, staged.comfy_name)
        return staged

    async def _ensure_comfy_image(self, asset: Asset | None) -> str | None:
        return await self._stage_library_asset(asset)

    async def _ensure_comfy_file(self, asset: Asset | None) -> str | None:
        return await self._stage_library_asset(asset)

    def _scene_prompt(self, project: Project, scene: Scene, db: Session) -> str:
        tag_map = self._asset_map(db, project.id)
        resolved = resolve_prompt(scene.prompt, tag_map)
        notes = ""
        try:
            from .spatial_prompt_builder import assemble_prompt_layers, flatten_layers, guidance_hint
            from .spatial_scene import get_or_create_spatial, parse_spatial_doc

            row = get_or_create_spatial(db, project.id, scene.id)
            doc = parse_spatial_doc(row, project.spatial_map_json)
            layers = assemble_prompt_layers(doc)
            pos, _neg = flatten_layers(layers)
            if pos.strip():
                notes = f"{pos}\n{guidance_hint(doc.guidance)}"
            else:
                spatial = parse_spatial_map(project.spatial_map_json)
                notes = spatial_prompt_notes(spatial)
        except Exception:
            spatial = parse_spatial_map(project.spatial_map_json)
            notes = spatial_prompt_notes(spatial)
        combined = " ".join(x for x in [project.global_prompt, resolved.prompt] if x).strip()
        # Director camera motion + motion-tag text hints (honest text adapters)
        try:
            import re

            from .director_timeline_w46.master_lookup import load_scene_master
            from .profiles import ProfileItem

            master = load_scene_master(db, getattr(scene, "project_id", None), scene.id)
            cam_bits: list[str] = []
            prompt_text_parts: list[str] = []
            for batch in getattr(master, "batchBlocks", None) or []:
                for cam in getattr(batch, "cameraInstructions", None) or []:
                    motion = str(getattr(cam, "motion_type", "") or getattr(cam, "text", "") or "").strip()
                    if motion:
                        cam_bits.append(motion.replace("_", " "))
                for seg in getattr(batch, "promptSegments", None) or []:
                    prompt_text_parts.append(str(getattr(seg, "text", "") or ""))
            if cam_bits:
                combined = f"{combined} Camera: {'; '.join(cam_bits)}".strip()
            tags = re.findall(r"#([A-Za-z0-9_-]+)", " ".join(prompt_text_parts))
            if tags:
                rows = db.query(ProfileItem).filter(ProfileItem.kind == "motion").all()
                known = {r.tag.lstrip("#").lower(): r for r in rows}
                hints = []
                for t in tags:
                    row = known.get(t.lower())
                    if row:
                        hints.append(f"motion reference {row.name} ({row.tag})")
                    else:
                        hints.append(f"(undefined motion tag #{t})")
                if hints:
                    combined = f"{combined} Motion: {'; '.join(hints)}".strip()
        except Exception:
            pass
        return inject_spatial_and_camera(combined, scene.camera_note, notes)

    def _frames_for_scene(self, scene: Scene, fps: int) -> int:
        from .video_runtime.legal_canvas import exact_frame_count

        return exact_frame_count(float(scene.duration_sec), int(fps))

    async def _build_and_run_scene(self, db: Session, project: Project, scene: Scene, job: Job) -> Path:
        positive = self._scene_prompt(project, scene, db)
        negative = project.negative_prompt
        # SEED LAW: -1 means randomize BEFORE Comfy submit (never clamp to 0).
        from .video_runtime.seed_resolve import resolve_execution_seed, seed_lineage_patch
        from .video_runtime.job_model import merge_video_runtime_history

        requested_seed = scene.seed if scene.seed >= 0 else project.seed
        _seed_res = resolve_execution_seed(requested_seed)
        seed = _seed_res.resolved_seed
        job.history_json = merge_video_runtime_history(
            job.history_json, seed_lineage_patch(_seed_res)
        )
        plan = resolve_render_plan(project)
        from .aspect_fps import resolve_scene_dims, resolve_scene_fps

        sw, sh = resolve_scene_dims(project, scene)
        sfps = resolve_scene_fps(project, scene)
        _job_canvas = self._job_params(job)
        try:
            req_w = int(_job_canvas.get("width") or 0)
            req_h = int(_job_canvas.get("height") or 0)
        except (TypeError, ValueError):
            req_w, req_h = 0, 0
        if req_w > 0 and req_h > 0:
            sw, sh = req_w, req_h
        plan_width, plan_height, plan_fps = sw, sh, sfps

        from .engine_recommend import resolve_engine_id

        original_engine = scene.engine
        # Timeline LTX jobs store engine=ltx in params. Scene.engine often
        # remains the DB default (minimax-h3) and must not win the resolver.
        _tl_params = self._job_params(job)
        if bool(_tl_params.get("timelineGeneration")):
            pref = str(_tl_params.get("engine") or "").strip().lower()
            if pref in {
                "ltx-2.5",
                "minimax-h3",
                "minimax_h3",
                "seedance-2.0",
                "seedance-2.5",
                "fal_seedance",
                "fal_kling",
                "fal_veo",
                "fal_runway",
            }:
                scene.engine = pref
            gen_pref = str(_tl_params.get("generatorId") or "").strip().lower()
            if gen_pref.startswith("minimax-h3"):
                scene.engine = "minimax-h3"
        resolved_engine = resolve_engine_id(scene.engine, project, scene)
        scene.engine = resolved_engine
        job.stage = "preparing"
        job.message = f"Preparing {scene.name} · {resolved_engine}"
        db.commit()
        try:
            if is_fal_engine(scene.engine):
                from .local_first import assert_fal_allowed

                assert_fal_allowed(self._job_params(job), engine=scene.engine)
                return await self._build_and_run_fal_scene(
                    db, project, scene, job, positive, negative, seed, plan
                )

            # Timeline batch jobs must size frames from params.duration (batch),
            # not scene.duration_sec (often B1+B2 sum). Otherwise LTX preflight
            # rejects Scene 11 ~16s while B1 is ~8s.
            _early_params = self._job_params(job)
            if bool(_early_params.get("timelineGeneration")):
                _early_batch_dur = _early_params.get("duration")
                if isinstance(_early_batch_dur, (int, float)) and float(_early_batch_dur) > 0:
                    from .video_runtime.legal_canvas import SpecFidelityError, exact_frame_count

                    try:
                        length = exact_frame_count(float(_early_batch_dur), int(plan_fps))
                    except SpecFidelityError:
                        # Keep a provisional frame count; preflight_spec below
                        # raises the creator-facing illegal-duration message.
                        length = max(1, int(round(float(_early_batch_dur) * float(plan_fps or 24))))
                else:
                    length = self._frames_for_scene(scene, plan_fps)
            else:
                length = self._frames_for_scene(scene, plan_fps)
            frame_clamped = False
            steps = plan.steps
            width, height = plan_width, plan_height
            from .video_runtime.legal_canvas import SpecFidelityError, preflight_spec

            _surface = "r2v" if bool(self._job_params(job).get("timelineGeneration")) else "i2v"
            # MiniMax H3: the scene's raw duration (12.0s = 288 frames) may not
            # be on the 17k+5 grid. Use the legal frame count from the job params
            # (set by request_builder.py) or snap UP via frames_for_duration.
            # This prevents preflight_spec from rejecting ordinary durations
            # that the resolver is designed to handle.
            _job_params = self._job_params(job)
            # Timeline batch jobs must preflight the BATCH duration, not the full
            # scene length (Scene 11 = B1+B2 ~16s while B1 params.duration ~8s).
            _spec_length_seconds = float(
                getattr(scene, "duration_sec", 0) or (length / float(plan_fps or 24))
            )
            if bool(_job_params.get("timelineGeneration")):
                _batch_dur = _job_params.get("duration")
                if isinstance(_batch_dur, (int, float)) and float(_batch_dur) > 0:
                    _spec_length_seconds = float(_batch_dur)
            if _timeline_job_is_h3(_job_params, resolved_engine):
                _legal_frame_count = int(_job_params.get("legalFrameCount") or 0)
                if _legal_frame_count > 0:
                    _spec_length_seconds = _legal_frame_count / float(plan_fps or 24)
                else:
                    from .workflows.h3_ref2v_builder import frames_for_duration

                    _spec_length_seconds = frames_for_duration(_spec_length_seconds) / float(
                        plan_fps or 24
                    )
            _spec = preflight_spec(
                str(resolved_engine),
                width=width,
                height=height,
                length_seconds=_spec_length_seconds,
                fps=int(plan_fps),
                surface=_surface,
            )
            if not _spec["ok"]:
                raise SpecFidelityError(
                    _spec["message"],
                    suggestions=list(_spec.get("suggestions") or []),
                    code="SPEC_FIDELITY",
                )

            # TIMELINE_BATCH_LTX: when this render_scene job was submitted by the
            # LTX Timeline adapter (timelineGeneration=True), override the
            # scene-global prompt/duration/start frame with the per-batch
            # values stored in job params. This makes the LTX render act on the
            # specific BatchBlock instead of the whole scene (BATCH_ISOLATION).
            params = self._job_params(job)
            is_timeline_batch = bool(params.get("timelineGeneration"))
            if is_timeline_batch:
                bp = params.get("prompt")
                if isinstance(bp, str) and bp:
                    positive = bp
                bd = params.get("duration")
                if isinstance(bd, (int, float)) and bd > 0:
                    # MiniMax H3: use legalFrameCount from request_builder if
                    # available (294 for 12.0s). Fall back to frames_for_duration
                    # which snaps UP to legal 17k+5. Other engines use
                    # assert_legal_duration as before.
                    legal_frame_count = int(params.get("legalFrameCount") or 0)
                    if legal_frame_count > 0 and _timeline_job_is_h3(params, resolved_engine):
                        length = legal_frame_count
                    elif _timeline_job_is_h3(params, resolved_engine):
                        from ...workflows.h3_ref2v_builder import frames_for_duration

                        length = frames_for_duration(float(bd))
                    else:
                        from .video_runtime.legal_canvas import assert_legal_duration

                        length = assert_legal_duration(
                            str(resolved_engine),
                            float(bd),
                            int(plan_fps),
                            surface="r2v",
                        )
                bseed = params.get("seed")
                if isinstance(bseed, int) and bseed >= 0:
                    seed = bseed

            if plan.notes:
                job.message = plan.notes
                db.commit()

            if (not is_timeline_batch) and _timeline_job_is_h3(params, resolved_engine):
                dest = await self._build_and_run_h3_i2va(
                    db,
                    project,
                    scene,
                    job,
                    positive=positive,
                    params=params,
                    seed=seed,
                )
                scene.output_path = str(dest)
                db.commit()
                return dest
            start = await self._ensure_comfy_image(self._get_asset(db, scene.start_asset_id))
            middle = await self._ensure_comfy_image(self._get_asset(db, scene.middle_asset_id))
            end = await self._ensure_comfy_image(self._get_asset(db, scene.end_asset_id))
            audio = await self._ensure_comfy_file(self._get_asset(db, scene.audio_asset_id))

            prefix = f"studio/{project.id[:8]}_{scene.index}"
            params = self._job_params(job)
            # TIMELINE_BATCH_LTX: per-batch output prefix so concurrent/sequential
            # batch outputs never share a filename stem (traceability + no
            # reliance on ComfyUI session counters for uniqueness).
            if is_timeline_batch:
                b_id = params.get("batchBlockId")
                if b_id:
                    prefix = f"{prefix}/batch_{str(b_id)[:8]}"
            # Per-job stem so a later take cannot attach a cached leftover file.
            prefix = f"{prefix}/job_{job.id[:8]}"
            # TIMELINE_BATCH_LTX: override start frame with the per-batch
            # startImageAssetId when present (BATCH_ISOLATION).
            if is_timeline_batch:
                b_start_id = params.get("startImageAssetId")
                if not b_start_id:
                    r2v = params.get("r2v") if isinstance(params.get("r2v"), dict) else {}
                    b_start_id = str(r2v.get("mappedStartAssetId") or "").strip() or None
                    if not b_start_id:
                        for item in (r2v.get("slots") or []):
                            if not isinstance(item, dict):
                                continue
                            role = str(item.get("role") or "")
                            aid = str(item.get("assetId") or "").strip()
                            if aid and role not in {"video", "audio"}:
                                b_start_id = aid
                                break
                    if b_start_id:
                        params["startImageAssetId"] = b_start_id
                if b_start_id:
                    b_start_asset = self._get_asset(db, b_start_id)
                    if b_start_asset:
                        start = await self._ensure_comfy_image(b_start_asset)
                b_end_id = params.get("endImageAssetId")
                if b_end_id:
                    b_end_asset = self._get_asset(db, b_end_id)
                    if b_end_asset:
                        end = await self._ensure_comfy_image(b_end_asset)
            if is_timeline_batch and _timeline_job_is_h3(params, resolved_engine):
                dest = await self._build_and_run_h3_ref2v(
                    db,
                    project,
                    scene,
                    job,
                    positive=positive,
                    prefix=prefix,
                    params=params,
                    seed=seed,
                )
                scene.output_path = str(dest)
                db.commit()
                return dest
            # Shared LoRA Registry (video path): resolve the selected LoRA
            # against the ACTIVE video engine. Refuses disabled / incompatible
            # / missing selections with a clear error — never substitutes.
            lora_video_name: Optional[str] = None
            lora_video_strength = 0.8
            lora_sel = params.get("lora")
            if lora_sel is None and isinstance(params.get("loras"), list) and params.get("loras"):
                lora_sel = params["loras"][0]
            if lora_sel is None:
                # Legacy scene-render fallback: Timeline right drawer stores the
                # scene-level LoRA in director_json (W46 batches keep their own).
                try:
                    _dj = json.loads(getattr(scene, "director_json", "") or "{}")
                    if isinstance(_dj, dict) and _dj.get("lora"):
                        lora_sel = _dj["lora"]
                except Exception:
                    lora_sel = None
            if lora_sel is not None:
                from .lora_registry.registry import resolve_comfy_lora_name, resolve_lora_for_generation

                lora_rec = resolve_lora_for_generation(lora_sel, resolved_engine, "video")
                lora_video_name = resolve_comfy_lora_name(lora_rec)
                if isinstance(lora_sel, dict) and lora_sel.get("strength") is not None:
                    try:
                        lora_video_strength = float(lora_sel["strength"])
                    except (TypeError, ValueError):
                        lora_video_strength = float(lora_rec.recommended_strength or 0.8)
                else:
                    lora_video_strength = float(lora_rec.recommended_strength or 0.8)
                params["lora_provenance"] = {
                    "loraId": lora_rec.id,
                    "name": lora_rec.name,
                    "version": lora_rec.version,
                    "modelFamily": lora_rec.model_family,
                    "compatibleModelFamilies": list(lora_rec.compatible_model_families),
                    "strength": lora_video_strength,
                    "baseGenerator": resolved_engine,
                    "sourceTool": "timeline",
                    "filePath": lora_rec.file_path,
                    "category": lora_rec.category,
                    "modality": lora_rec.modality,
                }
                job.message = f"Preparing {scene.name} · {resolved_engine} · LoRA {lora_rec.name}"
                db.commit()

            # M41 4.1B: WorkflowResolver selects leaf workflow — QueueWorker executes only.
            from .video_runtime.workflow_resolver import resolve_from_scene_params
            from .video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
            from .video_runtime.job_model import merge_video_runtime_history

            intent = "shot_render" if job.kind == "render_shot" else "scene_render"
            contract = resolve_from_scene_params(
                engine=scene.engine,
                start_asset_id=scene.start_asset_id or params.get("startImageAssetId"),
                middle_asset_id=scene.middle_asset_id,
                end_asset_id=scene.end_asset_id or params.get("endImageAssetId"),
                audio_asset_id=scene.audio_asset_id,
                paid_fal_approved=bool(params.get("paidFallbackApproved")),
                intent=intent,
                generator_id=str(params.get("generatorId") or params.get("variant") or ""),
            )
            from .video_runtime.workflow_resolver import local_video_identity

            identity = local_video_identity(
                requested_model=str(params.get("generatorId") or params.get("variant") or ""),
                leaf_workflow_key=str(contract.leaf_workflow_key or ""),
                ltx_25_checkpoint=settings.ltx_2_5_checkpoint,
            )
            params = {**params, **identity}
            job.params_json = json.dumps(params)
            for d in contract.disclosures:
                job.message = d
            job.history_json = merge_video_runtime_history(
                job.history_json,
                {"workflowContract": contract.to_dict(), "modelIdentity": identity},
            )
            db.commit()
            if is_timeline_batch and str(contract.leaf_workflow_key or "").endswith(".t2v"):
                raise RuntimeError(
                    "TIMELINE_R2V_REQUIRED: Timeline does not generate text-to-video. "
                    "Assign a character, place, or previous-take picture first."
                )

            # 1F v1.1 model law: only MiniMax H3 and LTX 2.5 are active 1F generators.
            if (
                not is_timeline_batch
                and not (middle or end)
                and contract.leaf_workflow_key in _RETIRED_1F_LEAVES
            ):
                raise RuntimeError(
                    f"{contract.leaf_workflow_key} is retired from 1 Frame. "
                    "Use MiniMax H3 or LTX 2.5 for a single start image."
                )

            if contract.leaf_workflow_key.startswith("ltx_25"):
                from .workflows.ltx_25_builder import ltx_25_runtime_steps

                steps = ltx_25_runtime_steps(
                    fast_mode=params.get("fast_mode") if "fast_mode" in params else None,
                    plan_steps=steps,
                )
                if params.get("width") and params.get("height"):
                    try:
                        width = int(params["width"])
                        height = int(params["height"])
                    except (TypeError, ValueError):
                        pass
                try:
                    await comfy.free_memory(unload_models=True, free_memory=True)
                except Exception:
                    logging.getLogger(__name__).warning("Comfy free_memory before LTX 2.5 failed", exc_info=True)

            if contract.leaf_workflow_key in {"ltx.simple_i2v", "ltx.scene"}:
                raise RuntimeError(
                    "LTX 2.3 is retired from v1.1 generation. Use LTX 2.5 or MiniMax H3."
                )
            if contract.leaf_workflow_key == "ltx_25.i2v" and not start:
                raise RuntimeError(
                    "1 Frame needs a start image. Adept will not invent a first frame."
                )

            async def on_progress(p: float, msg: str) -> None:
                job.progress = p
                job.message = msg
                job.updated_at = datetime.utcnow()
                db.commit()

            async def _run_graph(wf: dict, workflow_key: str):
                # A graph with an explicitly selected LoRA intentionally exercises
                # the declared optional inputs (loraId/loraStrength) and is verified
                # by the LoRA graph tests instead of the baseline topology hash.
                wf = prepare_executable_graph(
                    contract, wf, enforce_certified_fingerprint=not bool(lora_video_name)
                )
                prompt_id = await comfy.queue_prompt(wf, workflow_key=workflow_key)
                job.comfy_prompt_id = prompt_id
                self.bind_prompt(job.id, prompt_id)
                try:
                    from .video_runtime.job_model import merge_video_runtime_history

                    hops = {}
                    try:
                        hist = json.loads(job.history_json or "{}")
                        if isinstance(hist, dict):
                            hops = dict((hist.get("videoRuntime") or {}).get("queueHops") or {})
                    except Exception:
                        hops = {}
                    hops["providerSubmittedAt"] = datetime.utcnow().isoformat()
                    hops["providerPromptId"] = prompt_id
                    hops["providerAccepted"] = True
                    job.history_json = merge_video_runtime_history(
                        job.history_json, {"queueHops": hops}
                    )
                except Exception:
                    pass
                db.commit()
                preview = (
                    "ltx-2.5"
                    if str(workflow_key).startswith("ltx_25")
                    else "minimax-h3"
                    if "minimax" in str(workflow_key) or str(workflow_key).startswith("h3")
                    else None
                )
                return await self._wait_comfy(
                    job, prompt_id, on_progress=on_progress, preview_engine=preview
                )

            wf = build_leaf_graph(
                contract,
                settings=settings,
                positive=positive,
                negative=negative,
                width=width,
                height=height,
                length=length,
                fps=plan_fps,
                seed=seed,
                start_image=start,
                middle_image=middle,
                end_image=end,
                audio_file=audio,
                steps=steps,
                filename_prefix=prefix,
                lora_name=lora_video_name,
                lora_strength=lora_video_strength,
                turbo_lora=bool(params.get("turbo_lora")),
                generate_audio=(
                    bool(params.get("generate_audio", True))
                    if contract.leaf_workflow_key.startswith("ltx_25")
                    else None
                ),
            )
            workflow_key = contract.leaf_workflow_key

            history = await _run_graph(wf, workflow_key)

            if job.id in self._cancel:
                from .comfy_client import JobCancelledError

                raise JobCancelledError("Cancelled by user — discarding ComfyUI output")
            files = comfy.find_output_files(history)
            if not files:
                raise RuntimeError("ComfyUI finished but no output video was found")

            dest_dir = settings.data_dir / "projects" / project.id / "renders"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"scene_{scene.index}_{uuid.uuid4().hex[:8]}{files[0].suffix}"
            shutil.copy2(files[0], dest)
            from .video_runtime.output_gate import comfy_output_predates_job

            if comfy_output_predates_job(dest, job.created_at):
                job.status = "failed"
                job.stage = "stale_comfy_output"
                job.message = (
                    "Comfy returned a leftover render from before this job started. "
                    "Adept refused it instead of placing a previous take."
                )[:4000]
                db.commit()
                raise RuntimeError(job.message)

            from .video_runtime.output_gate import maybe_create_poster, maybe_create_proxy, validate_video_output

            gate = validate_video_output(dest, asset_registered=False)
            if not gate.passed:
                job.status = "failed"
                job.stage = gate.status
                job.message = gate.message[:4000]
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(
                    job.history_json, {"outputGate": gate.to_dict()}
                )
                db.commit()
                raise RuntimeError(gate.message)
            poster = maybe_create_poster(dest)
            proxy = maybe_create_proxy(dest)
            if proxy and proxy != dest:
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(
                    job.history_json,
                    {
                        "outputGate": gate.to_dict(),
                        "posterPath": str(poster) if poster else None,
                        "proxyPath": str(proxy),
                        "masterPath": str(dest),
                    },
                )

            # Optional mux scene audio if not already in video
            audio_asset = self._get_asset(db, scene.audio_asset_id)
            if audio_asset and Path(audio_asset.path).exists() and dest.suffix.lower() in {".mp4", ".webm", ".mov"}:
                muxed = dest.with_name(dest.stem + "_aud" + dest.suffix)
                try:
                    mux_audio(dest, Path(audio_asset.path), muxed)
                    dest = muxed
                except Exception:
                    pass

            scene.output_path = str(dest)
            # Every successful scene render must land in Project Library.
            # Timeline batches also need outputAssetIds for W46 batch binding.
            try:
                from .video_runtime.scene_output_library import register_render_output_asset

                engine_label = (
                    "ltx"
                    if str(scene.engine or "").startswith("ltx")
                    or str(params.get("engine") or "").startswith("ltx")
                    else str(scene.engine or params.get("engine") or "video")
                )
                tag = (
                    f"batch_{str(params.get('batchBlockId') or 'tl')[:8]}"
                    if is_timeline_batch
                    else engine_label
                )
                out_asset = register_render_output_asset(
                    db,
                    project_id=project.id,
                    dest=dest,
                    tag=tag,
                    prompt_meta={
                        "lora": params.get("lora_provenance"),
                        "engine": engine_label,
                        "workflowKey": getattr(contract, "leaf_workflow_key", "") or "",
                        "comfyPromptId": job.comfy_prompt_id or "",
                        "requestedModel": params.get("requestedModel") or params.get("generatorId"),
                        "resolvedRuntimeModel": params.get("resolvedRuntimeModel"),
                    },
                )
                params = {
                    **params,
                    "outputAssetIds": [out_asset.id],
                    "output_asset_id": out_asset.id,
                }
                job.params_json = json.dumps(params)
                db.commit()
            except Exception:
                logging.getLogger(__name__).warning(
                    "Scene render Library registration failed", exc_info=True
                )
            # M3.0h: persist two-stage local provenance + start-frame binding proof.
            try:
                from .local_first import local_first_provenance

                bind = {
                    "startFrameAssetId": scene.start_asset_id,
                    "renderSceneJobId": job.id,
                    "ltxWorkflowInputBinding": {
                        "assetId": scene.start_asset_id,
                        "comfyImageName": start,
                        "role": "start_frame",
                    },
                    "engine": "ltx" if str(params.get("engine") or scene.engine or "").startswith("ltx") else scene.engine,
                    "comfyPromptId": job.comfy_prompt_id,
                    "outputPath": str(dest),
                    "requestedModel": params.get("requestedModel") or params.get("generatorId"),
                    "resolvedRuntimeModel": params.get("resolvedRuntimeModel"),
                }
                start_hash = None
                start_asset = self._get_asset(db, scene.start_asset_id)
                if start_asset and start_asset.path and Path(start_asset.path).is_file():
                    import hashlib

                    h = hashlib.sha256()
                    with open(start_asset.path, "rb") as fh:
                        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                            h.update(chunk)
                    start_hash = h.hexdigest()
                    bind["startFrameFileHash"] = start_hash
                from .video_runtime.workflow_resolver import local_video_identity

                identity = local_video_identity(
                    requested_model=str(params.get("generatorId") or params.get("variant") or ""),
                    leaf_workflow_key=str(getattr(contract, "leaf_workflow_key", "") or ""),
                    ltx_25_checkpoint=settings.ltx_2_5_checkpoint,
                )
                params = {
                    **params,
                    "requestedModel": identity["requestedModel"],
                    "resolvedRuntimeModel": identity["resolvedRuntimeModel"],
                }
                provenance = local_first_provenance(
                    start_frame_provider="comfyui" if scene.start_asset_id else None,
                    start_frame_model=str((params.get("startFrameModel") or params.get("still_model") or "")),
                    video_provider="comfyui",
                    video_model=identity["videoModel"],
                    paid_provider_used=False,
                    current_job_fal_submission_count=0,
                )
                provenance["requestedModel"] = identity["requestedModel"]
                provenance["resolvedRuntimeModel"] = identity["resolvedRuntimeModel"]
                provenance["workflowKey"] = identity["workflowKey"]
                job.params_json = json.dumps(
                    {
                        **params,
                        "localFirstProvenance": provenance,
                        "ltxStartFrameBinding": bind,
                        "executionClass": "REAL_LOCAL_EXECUTION",
                        "lora": params.get("lora_provenance"),
                    }
                )
                if params.get("lora_provenance"):
                    from .video_runtime.job_model import merge_video_runtime_history

                    job.history_json = merge_video_runtime_history(
                        job.history_json, {"lora": params["lora_provenance"]}
                    )
            except Exception:
                pass
            db.commit()
            return dest
        finally:
            scene.engine = original_engine

    async def _build_and_run_h3_ref2v(
        self,
        db: Session,
        project: Project,
        scene: Scene,
        job: Job,
        *,
        positive: str,
        prefix: str,
        params: dict,
        seed: int,
    ) -> Path:
        from .workflows.h3_ref2v_builder import (
            H3_REF2VA_UNET,
            H3_REF2V_HEIGHT,
            H3_REF2V_WIDTH,
            assert_h3_ref2v_graph,
            build_h3_ref2v,
            frames_for_duration,
            resolve_h3_ref_image_size,
        )
        from .video_runtime.job_model import merge_video_runtime_history

        if str(params.get("generationMode") or "") != "reference":
            raise RuntimeError(
                "TIMELINE_R2V_REQUIRED: MiniMax H3 Timeline is Reference-to-Video only."
            )
        r2v = params.get("r2v") if isinstance(params.get("r2v"), dict) else {}
        slots = [item for item in (r2v.get("slots") or []) if isinstance(item, dict)]
        visual = [
            item
            for item in slots
            if str(item.get("role") or "") not in {"video", "audio"}
            and str(item.get("assetId") or "").strip()
            and item.get("pictureIndex") is not None
        ]
        visual.sort(key=lambda item: int(item.get("pictureIndex") or 0))
        if not visual:
            raise RuntimeError(
                "TIMELINE_R2V_REQUIRED: MiniMax H3 needs a character, place, or previous-take picture."
            )
        names: list[str] = []
        bound: list[dict[str, Any]] = []
        for item in visual[:9]:
            asset = self._get_asset(db, str(item.get("assetId") or ""))
            # Guard: visual slots require IMAGE assets. A voice .wav or video in a
            # visual slot is a contract violation — skip it with a warning rather
            # than sending a non-image to Comfy's LoadImage node.
            if asset and str(getattr(asset, "kind", "") or "").lower() not in {"image", "crs", "ers", "prs", ""}:
                raise RuntimeError(
                    f"{item.get('label') or item.get('assetId')} could not be delivered to the selected generator reference input."
                )
            from .director_timeline_w46.generation.direct_reference import has_direct_reference_authority

            if has_direct_reference_authority(params=params):
                staged = await self._stage_direct_visual_asset(asset)
            else:
                staged = await self._stage_h3_visual_asset(asset, str(item.get("role") or ""))
            uploaded = staged.comfy_name if staged is not None else None
            if not uploaded:
                raise RuntimeError(
                    f"H3_REF2V_ASSET_MISSING: could not load {item.get('label') or item.get('assetId')}."
                )
            names.append(uploaded)
            ledger = dict(getattr(staged, "ledger", None) or {})
            bound.append(
                {
                    "role": item.get("role"),
                    "assetId": item.get("assetId"),
                    "label": item.get("label"),
                    "pictureIndex": item.get("pictureIndex"),
                    "comfyName": uploaded,
                    "identityAuthority": ledger.get("identityAuthority") or "reference_image",
                    "uploadedTensor": ledger.get("uploaded") or "library_file",
                }
            )
        audio_items = [
            item
            for item in slots
            if str(item.get("role") or "") == "audio"
            and str(item.get("assetId") or "").strip()
            and item.get("audioIndex") is not None
        ]
        audio_names: list[str] = []
        for item in audio_items[:9]:
            asset = self._get_asset(db, str(item.get("assetId") or ""))
            uploaded = await self._ensure_comfy_file(asset)
            if not uploaded:
                raise RuntimeError(
                    f"H3_REF2V_VOICE_MISSING: could not load {item.get('label') or item.get('assetId')}."
                )
            audio_names.append(uploaded)
            bound.append(
                {
                    "role": "audio",
                    "assetId": item.get("assetId"),
                    "label": item.get("label"),
                    "audioIndex": item.get("audioIndex"),
                    "comfyName": uploaded,
                }
            )
        duration = float(params.get("duration") or 5.0)
        # Use legalFrameCount from request_builder if available (294 for 12.0s).
        # Fall back to frames_for_duration which now snaps UP to legal 17k+5.
        legal_frame_count = int(params.get("legalFrameCount") or 0)
        if legal_frame_count > 0:
            length = legal_frame_count
        else:
            length = frames_for_duration(duration)
        # requestedDurationSec is the creator's requested Timeline duration.
        # The generated video may be longer (12.25s vs 12.0s) and is trimmed
        # after generation to this value. Fall back to params["duration"] if
        # requestedDurationSec is absent (defensive).
        requested_duration_sec = float(
            params.get("requestedDurationSec") or params.get("duration") or 0.0
        )
        # FM5: Timeline H3 canvas comes from the request; default builder canvas is FM4 1152x640.
        # Do not inherit project 1280×704 or the retired 768×448 builder default.
        res = str(params.get("resolution") or "")
        if not params.get("width") and "x" in res.lower():
            try:
                w_s, h_s = res.lower().split("x", 1)
                params["width"] = int(w_s)
                params["height"] = int(h_s)
            except ValueError:
                pass
        width = int(params.get("width") or H3_REF2V_WIDTH)
        height = int(params.get("height") or H3_REF2V_HEIGHT)
        prompt = str(params.get("prompt") or positive or "").strip()
        if not prompt:
            raise RuntimeError("H3 R2V prompt is empty.")
        fast = bool(params.get("draftMode") or params.get("fast_generation"))
        ref_image_size = resolve_h3_ref_image_size(
            params.get("refImageSize") or params.get("ref_image_size")
        )
        # Silence-locked / expectedSpeech=NONE → generate_audio=false (video-only mux).
        gen_audio = True
        if params.get("generate_audio") is not None:
            gen_audio = bool(params.get("generate_audio"))
        elif params.get("audio_generation") is not None:
            gen_audio = bool(params.get("audio_generation"))
        aa = params.get("audioAuthority") if isinstance(params.get("audioAuthority"), dict) else {}
        if aa.get("generateAudio") is False or str(aa.get("nativeAudio") or "").lower() == "disabled":
            gen_audio = False
        wf = build_h3_ref2v(
            prompt=prompt,
            ref_comfy_names=names,
            filename_prefix=f"{prefix}/h3_ref2v",
            seed=seed,  # already resolved in _build_and_run_scene (SEED LAW)
            width=width,
            height=height,
            length=length,
            fast=fast,
            ref_image_size=ref_image_size,
            ref_audio_comfy_names=audio_names if gen_audio else None,
            generate_audio=gen_audio,
        )
        assert_h3_ref2v_graph(
            wf,
            expected_names=names,
            expected_audio_names=audio_names if gen_audio else None,
            expect_fast=fast,
        )
        try:
            await comfy.free_memory(unload_models=True, free_memory=True)
        except Exception:
            logging.getLogger(__name__).warning("Comfy free_memory before H3 Ref2V failed", exc_info=True)
        job.message = "MiniMax H3 Reference-to-Video · Adept Comfy"
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {
                "r2v": {
                    "mechanism": "h3_ref2va",
                    "unet": H3_REF2VA_UNET,
                    "slots": bound,
                    "length": length,
                    "runtime": "adept-comfy-8188",
                    "generate_audio": gen_audio,
                    "fast": fast,
                    "cache": "EasyCache" if fast else "none",
                }
            },
        )
        params = {
            **params,
            "resolvedRuntimeModel": H3_REF2VA_UNET,
            "requestedModel": params.get("generatorId") or "minimax-h3",
        }
        job.params_json = json.dumps(params)
        db.commit()

        async def on_progress(p: float, msg: str) -> None:
            # Intentionally no-op on the outer ORM Job. _wait_comfy persists progress
            # via SessionLocal. Touching this Job would dirty the outer Session and
            # reintroduce the SQLite deadlock that strands writing_output/done.
            return

        prompt_id = await comfy.queue_prompt(wf)
        job.comfy_prompt_id = prompt_id
        job.stage = "preparing_model"
        job.message = "Preparing model"
        from .video_runtime.progress_telemetry import (
            apply_heartbeat,
            extract_progress_telemetry,
            merge_progress_telemetry,
        )

        job.history_json = merge_progress_telemetry(
            job.history_json,
            apply_heartbeat(
                extract_progress_telemetry(job.history_json),
                progress=0.0,
                message="Preparing model",
                stage="preparing_model",
                job_status="running",
                grounded=False,
            ),
        )
        self.bind_prompt(job.id, prompt_id)
        db.commit()
        history = await self._wait_comfy(
            job, prompt_id, on_progress=on_progress, preview_engine="minimax-h3"
        )
        # Refresh after wait so outer session is not stale/locked against Job row.
        db.expire_all()
        job = db.get(Job, job.id) or job
        job.message = "Finalizing MiniMax H3 output"
        job.stage = "writing_output"
        job.progress = max(float(job.progress or 0), 0.97)
        job.updated_at = datetime.utcnow()
        db.commit()
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError("MiniMax H3 Reference-to-Video finished but no output video was found.")
        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"scene_{scene.index}_{uuid.uuid4().hex[:8]}{files[0].suffix}"
        shutil.copy2(files[0], dest)
        from .video_runtime.output_gate import validate_video_output

        gate = validate_video_output(dest, asset_registered=False)
        if not gate.passed:
            raise RuntimeError(gate.message or "MiniMax H3 output gate refused the file.")
        job.history_json = merge_video_runtime_history(
            job.history_json, {"outputGate": gate.to_dict()}
        )
        # Deterministic trim: if MiniMax generated more frames than the
        # creator requested (e.g., 294 frames / 12.25s for a 12.0s request),
        # trim the excess tail so the final clip matches the requested Timeline
        # duration exactly. No padding, no frame duplication, no speed change.
        if requested_duration_sec > 0:
            from .media_clip import trim_video_to_seconds

            trimmed = trim_video_to_seconds(dest, requested_duration_sec)
            if trimmed:
                job.history_json = merge_video_runtime_history(
                    job.history_json,
                    {
                        "durationTrim": {
                            "requestedDurationSec": requested_duration_sec,
                            "trimmed": True,
                            "reason": "MiniMax H3 legal frame count exceeds requested Timeline duration",
                        }
                    },
                )
        # Register native audio provenance: probe the final file for an audio
        # stream and record its metadata in the job history so the UI and
        # Library can display audio provenance (Generator Native vs Timeline).
        try:
            from .minimax_h3.audio_import import register_native_audio_provenance
            import json as _json
            import shutil as _shutil
            import subprocess as _subprocess

            ffprobe = _shutil.which("ffprobe")
            audio_meta: dict[str, Any] = {}
            if ffprobe:
                probe_proc = _subprocess.run(
                    [
                        ffprobe,
                        "-v", "error",
                        "-show_entries",
                        "stream=codec_type,codec_name,channels,sample_rate",
                        "-of", "json",
                        str(dest),
                    ],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                if probe_proc.returncode == 0:
                    probe_data = _json.loads(probe_proc.stdout or "{}")
                    for s in (probe_data.get("streams") or []):
                        if s.get("codec_type") == "audio":
                            sr = s.get("sample_rate")
                            audio_meta = {
                                "channels": s.get("channels"),
                                "sampleRateHz": int(sr) if sr else None,
                            }
                            break
            provenance = register_native_audio_provenance({}, audio_meta)
            job.history_json = merge_video_runtime_history(
                job.history_json,
                {"audioProvenance": provenance.get("audio", {})},
            )
        except Exception:
            logging.getLogger(__name__).warning("Failed to register audio provenance", exc_info=True)
        db.commit()
        return dest

    async def _build_and_run_h3_i2va(
        self,
        db: Session,
        project: Project,
        scene: Scene,
        job: Job,
        *,
        positive: str,
        params: dict,
        seed: int,
    ) -> Path:
        """1 Frame MiniMax — Route A image-to-video. Never LTX. Never Timeline Ref2V."""
        from .minimax_h3.route_a_adapter import RouteARuntimeAdapter, import_output_to_project_library
        from .minimax_h3.service import _ensure_route_a_for_generation
        from .video_runtime.job_model import merge_video_runtime_history

        if scene.middle_asset_id and not scene.end_asset_id:
            raise RuntimeError(
                "MiniMax H3 Middle Frame requires First and Last frames. "
                "Adept will not invent a last frame or fake a middle."
            )
        start_asset = self._get_asset(db, scene.start_asset_id)
        end_asset = self._get_asset(db, scene.end_asset_id) if scene.end_asset_id else None
        middle_asset = self._get_asset(db, scene.middle_asset_id) if scene.middle_asset_id else None
        if not start_asset or not Path(start_asset.path).is_file():
            raise RuntimeError(
                "MiniMax H3 image-to-video needs a start picture. "
                "Add a still, or use Text to Video for words-only MiniMax."
            )
        if scene.end_asset_id and (not end_asset or not Path(end_asset.path).is_file()):
            raise RuntimeError(
                "MiniMax H3 3 Frame needs a readable Last Frame still."
            )
        if scene.middle_asset_id and (not middle_asset or not Path(middle_asset.path).is_file()):
            raise RuntimeError(
                "MiniMax H3 3 Frame Middle Frame path is not readable."
            )

        is_flf = bool(scene.end_asset_id)
        job.message = "Preparing MiniMax 3 Frame" if is_flf else "Preparing MiniMax image-to-video"
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {
                "i2v": {
                    "mechanism": (
                        "route_a_flf3_addguide"
                        if (is_flf and scene.middle_asset_id)
                        else ("route_a_flf2va" if is_flf else "route_a_i2va")
                    ),
                    "runtime": "minimax-route-a",
                    "provenance": (
                        "LOCAL — MiniMax H3 — 3 Frame AddGuide"
                        if (is_flf and scene.middle_asset_id)
                        else (
                            "LOCAL — MiniMax H3 — First Last Frame"
                            if is_flf
                            else "LOCAL — MiniMax H3 — Image to Video"
                        )
                    ),
                    "startAssetId": scene.start_asset_id,
                    "endAssetId": scene.end_asset_id,
                    "middleAssetId": scene.middle_asset_id,
                }
            },
        )
        db.commit()
        prepared, err = await asyncio.to_thread(_ensure_route_a_for_generation)
        if not prepared:
            raise RuntimeError(err or "MiniMax runtime could not start.")

        adapter = RouteARuntimeAdapter()
        state = await asyncio.to_thread(
            adapter.submit_i2va,
            project_id=project.id,
            plan_id=f"{'flf' if is_flf else 'i2v'}-{job.id[:8]}",
            prompt=positive,
            start_image_path=start_asset.path,
            end_image_path=(end_asset.path if end_asset else None),
            middle_image_path=(middle_asset.path if middle_asset else None),
            seed=seed,
            start_image_asset_id=scene.start_asset_id,
            end_image_asset_id=scene.end_asset_id,
            middle_image_asset_id=scene.middle_asset_id,
            duration_sec=float(scene.duration_sec or params.get("duration_sec") or 5),
            width=int(params.get("width") or project.width),
            height=int(params.get("height") or project.height),
            fps=float(params.get("fps") or project.fps or 24),
            steps=int(params.get("steps") or 0) or None,
            studio_job_id=job.id,
        )
        if state.status == "failed":
            raise RuntimeError(state.error_message or "MiniMax image-to-video failed to start.")
        # Persist prompt/status on a short-lived session. Do NOT dirty the caller's
        # ORM Job across the Route A poll span (same class of SQLite stranding as
        # Timeline wait_for_prompt / job 98db381c — BOT B 1F jobs 2d6920be/0baad7da).
        summary = _route_a_graph_summary(state)
        gen_msg = (
            f"MiniMax image-to-video · generating{(' · ' + summary) if summary else ''}"
        )
        if state.prompt_id:
            self.bind_prompt(job.id, state.prompt_id)
        db_bind = SessionLocal()
        try:
            row = db_bind.get(Job, job.id)
            if row is not None:
                row.comfy_prompt_id = (state.prompt_id or "")[:64]
                row.status = "running"
                row.stage = "processing"
                row.progress = max(float(row.progress or 0), 0.12)
                row.message = gen_msg
                row.updated_at = datetime.utcnow()
                db_bind.commit()
        finally:
            db_bind.close()
        # Do not refresh/expire the outer Session here — an open read transaction
        # on journal_mode=DELETE can block SessionLocal writers in on_wait/preview
        # for the entire Route A poll. job.id remains valid for the helper.
        state = await asyncio.to_thread(
            self._poll_route_a_with_preview, adapter, state, job, "minimax-h3", 900.0
        )
        if state.status != "completed" or not state.output_path:
            raise RuntimeError(state.error_message or "MiniMax image-to-video did not finish.")

        dest = Path(state.output_path)
        # Deterministic trim: if MiniMax generated more frames than the creator
        # requested (e.g., 294 frames / 12.25s for a 12.0s request), trim the
        # excess tail so the final clip matches the requested duration exactly.
        requested_duration_sec = float(scene.duration_sec or params.get("duration_sec") or 0)
        if requested_duration_sec > 0:
            from .media_clip import trim_video_to_seconds

            trim_video_to_seconds(dest, requested_duration_sec)
        receipt = import_output_to_project_library(
            project_id=project.id,
            source_mp4=dest,
            tag="minimax-h3",
            db=db,
        )
        params = {
            **params,
            "output_asset_id": receipt.get("assetId"),
            "outputAssetIds": [receipt.get("assetId")],
            "resolvedRuntimeModel": "minimax-h3-route-a-i2va",
            "provenance": "LOCAL — MiniMax H3 — Image to Video",
        }
        job.params_json = json.dumps(params)
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {"libraryImport": receipt, "provenance": "LOCAL — MiniMax H3 — Image to Video"},
        )
        db.commit()
        return Path(str(receipt.get("path") or dest))

    @staticmethod
    def _record_fal_request_id(db: Session, job: Job, *, model_id: str, request_id: str) -> None:
        """Persist the fal queue request id so a render can be traced in the fal dashboard."""
        try:
            history = json.loads(job.history_json or "{}")
            if not isinstance(history, dict):
                history = {}
        except json.JSONDecodeError:
            history = {}
        history["falRequestId"] = request_id
        history["falModelId"] = model_id
        job.history_json = json.dumps(history)
        job.updated_at = datetime.utcnow()
        db.commit()

    async def _build_and_run_fal_scene(
        self,
        db: Session,
        project: Project,
        scene: Scene,
        job: Job,
        positive: str,
        negative: str,
        seed: int,
        plan,
    ) -> Path:
        api_key = get_secret("fal_api_key")
        if not api_key:
            raise RuntimeError(
                "Hosted AI Provider credential not configured for fal.ai. Open Setup → AI Providers "
                "(Kie.ai · WaveSpeed.ai · fal.ai), connect a key, then retry."
            )

        start_asset = self._get_asset(db, scene.start_asset_id)
        end_asset = self._get_asset(db, scene.end_asset_id) or self._get_asset(db, scene.middle_asset_id)

        async def on_progress(p: float, msg: str) -> None:
            job.progress = min(0.95, max(0.05, p))
            job.message = msg[:4000]
            job.updated_at = datetime.utcnow()
            db.commit()

        await on_progress(0.08, f"Uploading references to fal.ai ({scene.engine})")
        image_url = None
        end_url = None
        if start_asset and Path(start_asset.path).exists():
            image_url = await upload_file_to_fal(Path(start_asset.path), api_key)
        if end_asset and Path(end_asset.path).exists() and end_asset.id != (start_asset.id if start_asset else None):
            end_url = await upload_file_to_fal(Path(end_asset.path), api_key)

        # M3.0e: honor Model Intelligence / job params for native audio (default True for compat).
        job_params = self._job_params(job)
        mil_params = job_params.get("modelIntelligence") or job_params.get("mil") or {}
        if not isinstance(mil_params, dict):
            mil_params = {}
        if "generate_audio" in job_params:
            generate_audio = bool(job_params.get("generate_audio"))
        elif "generate_audio" in mil_params:
            generate_audio = bool(mil_params.get("generate_audio"))
        else:
            generate_audio = True
        mil_prompt = mil_params.get("compiledPrompt") or job_params.get("compiledPrompt")
        mil_negative = mil_params.get("negativePrompt") or job_params.get("compiledNegativePrompt")
        fal_positive = str(mil_prompt).strip() if mil_prompt else positive
        fal_negative = str(mil_negative).strip() if mil_negative else negative

        model_id, args = build_fal_arguments(
            engine=scene.engine,
            prompt=fal_positive,
            negative=fal_negative,
            image_url=image_url,
            end_image_url=end_url,
            duration_sec=scene.duration_sec,
            width=plan.width,
            height=plan.height,
            seed=seed,
            generate_audio=generate_audio,
        )
        job.message = f"fal.ai · {model_id}"
        job.comfy_prompt_id = model_id[:64]
        db.commit()

        async def on_request_id(request_id: str) -> None:
            self._record_fal_request_id(db, job, model_id=model_id, request_id=request_id)

        result = await run_fal_model(
            model_id, args, api_key, on_progress=on_progress, on_request_id=on_request_id
        )
        video_url = extract_video_url(result)

        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"scene_{scene.index}_{uuid.uuid4().hex[:8]}_fal.mp4"
        await download_url(video_url, dest)

        scene.output_path = str(dest)
        db.commit()
        await on_progress(1.0, "fal.ai render saved")
        return dest

    async def _render_scene(self, db: Session, job: Job, project: Project) -> None:
        scene = db.get(Scene, job.scene_id) if job.scene_id else None
        if not scene:
            raise RuntimeError("Scene not found")
        path = await self._build_and_run_scene(db, project, scene, job)
        self._set_status(job.id, "done", 1.0, "Scene render complete", str(path))

    async def _render_timeline(
        self, db: Session, job: Job, project: Project, *, batch: bool = False
    ) -> None:
        """Certified orchestration: director.timeline_render / director.batch_timeline."""
        from .editor_mix import (
            collect_timeline_mix_stems,
            mix_stems_onto_video,
            new_mix_output_path,
            resolve_editor_path_factory,
        )
        from .video_runtime.job_model import merge_video_runtime_history
        from .video_runtime.workflow_resolver import resolve_workflow

        orch_intent = "batch_timeline" if batch else "timeline_render"
        try:
            orch = resolve_workflow(orch_intent, engine="director")
            job.history_json = merge_video_runtime_history(
                job.history_json, {"workflowContract": orch.to_dict()}
            )
            db.commit()
        except Exception:
            pass

        scenes = (
            db.query(Scene)
            .filter(Scene.project_id == project.id)
            .order_by(Scene.index.asc())
            .all()
        )
        if not scenes:
            raise RuntimeError("No scenes to render")

        outputs: list[Path] = []
        for i, scene in enumerate(scenes):
            if job.id in self._cancel:
                self._set_status(job.id, "cancelled", i / len(scenes), "Cancelled")
                return
            job.progress = i / max(1, len(scenes))
            # batch_timeline always (re)generates; timeline_render skips scenes with output
            if (
                not batch
                and scene.output_path
                and Path(scene.output_path).is_file()
            ):
                job.message = f"Reusing scene {i + 1}/{len(scenes)} output"
                db.commit()
                outputs.append(Path(scene.output_path))
                continue
            job.message = (
                f"{'Batch' if batch else 'Rendering'} scene {i + 1}/{len(scenes)} ({scene.engine})"
            )
            job.updated_at = datetime.utcnow()
            db.commit()


            path = await self._build_and_run_scene(db, project, scene, job)
            outputs.append(path)

            # Performance Retake quarantine: legacy auto-lipsync after render is
            # disabled unless ADEPT_LEGACY_LIPSYNC=1. Retake is an explicit
            # creator action (mode="performance_retake"), never an implicit
            # post-render LatentSync pass.
            if scene.lipsync_enabled and os.environ.get("ADEPT_LEGACY_LIPSYNC", "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                job.message = f"Lip sync scene {i + 1}"
                db.commit()
                try:
                    synced = await self._lipsync_scene(db, project, scene)
                    if synced:
                        outputs[-1] = synced
                except Exception as exc:
                    job.message = f"Lip sync skipped: {exc}"
                    db.commit()

        job.message = "Stitching timeline"
        job.progress = 0.92
        db.commit()
        out_dir = settings.data_dir / "projects" / project.id / "renders"
        final = out_dir / f"timeline_{uuid.uuid4().hex[:8]}.mp4"
        stitch_videos(outputs, final, fps=project.fps)

        # Timeline music + SFX mix stage: only runs when the Director Timeline
        # carries resolvable audio/sfx stems. Zero behavior change otherwise.
        stems, skipped = collect_timeline_mix_stems(
            db,
            project,
            list(scenes),
            outputs,
            resolve_editor_path_factory(db, project.id),
        )
        mix_meta: dict[str, Any] | None = None
        if stems:
            job.message = "Mixing timeline music/SFX"
            job.progress = 0.96
            db.commit()
            mixed = new_mix_output_path(project.id, settings.data_dir)
            mix_result = mix_stems_onto_video(
                primary_video=final,
                stems=stems,
                out_path=mixed,
            )
            final = mixed
            mix_meta = {
                "timelineMix": {
                    "stemsUsed": len(stems),
                    "skipped": skipped,
                    "filterComplex": mix_result.filter_complex,
                    "output": str(final),
                }
            }

        self._set_status(
            job.id,
            "done",
            1.0,
            "Timeline render complete",
            str(final),
            video_runtime_patch=mix_meta,
        )

    async def _editor_mix(self, db: Session, job: Job, project: Project) -> None:
        """DEPRECATED (P0): legacy Editor mix — refused in favor of MAGI final_render."""
        from .magi.authority import editor_mix_deprecation_detail

        detail = editor_mix_deprecation_detail(project.id)
        raise RuntimeError(detail["message"])

        # Unreachable — retained imports/shape below would dual-authority mix; do not revive.
        from .editor_mix import (  # pragma: no cover
            default_primary_video,
            mix_editor_onto_video,
            new_mix_output_path,
            resolve_editor_path_factory,
        )
        from .editor_sequences import EditorProjectRow, _row_to_editor

        params = self._job_params(job)
        job.message = "Loading Editor tracks"
        job.progress = 0.1
        job.updated_at = datetime.utcnow()
        db.commit()

        ed_row = (
            db.query(EditorProjectRow)
            .filter(EditorProjectRow.project_id == project.id)
            .first()
        )
        if not ed_row:
            raise RuntimeError("No Editor project for this project; add clips before editor_mix")
        editor_data = _row_to_editor(ed_row)

        primary = default_primary_video(db, project.id, editor_data, params)
        if primary is None:
            raise RuntimeError(
                "No primary video for editor_mix; render a timeline/scene first "
                "or pass primary_video_path"
            )

        job.message = "Mixing Editor stems"
        job.progress = 0.4
        db.commit()

        out_path = new_mix_output_path(project.id, settings.data_dir)
        resolve = resolve_editor_path_factory(db, project.id)
        result = mix_editor_onto_video(
            primary_video=primary,
            editor_data=editor_data,
            out_path=out_path,
            resolve_path=resolve,
        )

        meta = {
            **result.prompt_meta,
            "jobId": job.id,
            "projectId": project.id,
            "editorId": ed_row.id,
        }
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tag="editor_mix",
            kind="video",
            filename=out_path.name,
            path=str(out_path),
            comfy_name="",
            scope="project",
            prompt_meta_json=json.dumps(meta),
            labels_json=json.dumps(["editor_mix", "final-mix"]),
            production_approval="none",
        )
        db.add(asset)
        db.flush()
        try:
            from .asset_graph import add_edge

            for stem in result.stems_used:
                if stem.asset_id and db.get(Asset, stem.asset_id):
                    add_edge(db, asset.id, stem.asset_id, relation="uses_audio")
        except Exception:
            pass
        job.params_json = json.dumps({**params, "output_asset_id": asset.id})
        db.commit()

        stem_n = len(result.stems_used)
        skip_n = len(result.skipped)
        msg = f"Editor mix complete ({stem_n} stem(s)"
        if skip_n:
            msg += f", {skip_n} skipped"
        msg += ")"
        self._set_status(job.id, "done", 1.0, msg, str(out_path))

    async def _lipsync_scene(
        self, db: Session, project: Project, scene: Scene, job: Job | None = None
    ) -> Path | None:
        if not scene.output_path or not Path(scene.output_path).exists():
            raise RuntimeError("Scene has no rendered video for lip sync")
        audio_asset = self._get_asset(db, scene.lipsync_audio_asset_id or scene.audio_asset_id)
        if not audio_asset:
            raise RuntimeError("No lip sync audio asset")

        # M41 4.1B-L L-10B: resolve Certified lipsync contract before any builder work.
        from .video_runtime.workflow_resolver import resolve_workflow
        from .video_runtime.job_model import merge_video_runtime_history

        lipsync_contract = resolve_workflow(
            "lipsync",
            present_inputs={
                "audio_asset_id": audio_asset.id,
                "video": True,
            },
        )
        if job is not None:
            job.history_json = merge_video_runtime_history(
                job.history_json,
                {"workflowContract": lipsync_contract.to_dict()},
            )
            job.message = f"lipsync → {lipsync_contract.leaf_workflow_key}@{lipsync_contract.leaf_workflow_version}"
            db.commit()

        # Probe installed LatentSync node (hay86: D_LatentSyncNode; legacy: LatentSyncNode)
        from .workflows.lipsync_builder import preferred_lipsync_node

        node_class: str | None = None
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                available: set[str] = set()
                for candidate in ("D_LatentSyncNode", "LatentSyncNode"):
                    r = await client.get(f"{settings.comfy_url}/object_info/{candidate}")
                    if r.status_code == 200:
                        payload = r.json() or {}
                        if candidate in payload or payload:
                            available.add(candidate)
                node_class = preferred_lipsync_node(available)
                if not node_class:
                    raise RuntimeError(lipsync_available_hint())
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        video_source = Path(scene.output_path)
        job_params = self._job_params(job) if job else {}
        prefer_still_face = bool(
            os.environ.get("STUDIO_LIPSYNC_PREFER_STILL_FACE") == "1"
            or job_params.get("prefer_still_face")
            or "prefer_still_face" in (getattr(job, "message", "") or "").lower()
        )
        for metadata_text in (
            getattr(scene, "director_json", ""),
            getattr(scene, "continuity_json", ""),
        ):
            try:
                metadata = json.loads(metadata_text or "{}")
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            if isinstance(metadata, dict) and metadata.get("prefer_still_face"):
                prefer_still_face = True
            if isinstance(metadata, dict):
                image_id = (
                    metadata.get("face_asset_id")
                    or metadata.get("image_asset_id")
                    or metadata.get("start_asset_id")
                )
                if image_id and not scene.start_asset_id:
                    scene.start_asset_id = image_id

        if prefer_still_face:
            still_asset = self._get_asset(db, scene.start_asset_id)
            if still_asset and still_asset.kind == "image" and Path(still_asset.path).is_file():
                still_dest = (
                    settings.data_dir
                    / "projects"
                    / project.id
                    / "renders"
                    / f"scene_{scene.index}_lipsync_still_{uuid.uuid4().hex[:8]}.mp4"
                )
                video_source = prepare_still_face_video(
                    image_path=Path(still_asset.path),
                    audio_path=Path(audio_asset.path),
                    dest=still_dest,
                    fps=getattr(project, "fps", 25) or 25,
                )

        async def _run_once(source: Path) -> Path:
            v_name = await comfy.upload_file_copy(source, filename=source.name)
            a_name = await self._ensure_comfy_file(audio_asset)
            v_abs = str(settings.comfy_input_dir / v_name.replace("/", "\\"))
            a_abs = str(settings.comfy_input_dir / (a_name or "").replace("/", "\\"))
            graph = build_latentsync_workflow(
                video_path=v_abs,
                audio_path=a_name or a_abs,
                filename_prefix=f"studio/{project.id[:8]}_lipsync_{scene.index}",
                custom_width=plan.lipsync_size,
                custom_height=plan.lipsync_size,
                inference_steps=plan.lipsync_steps,
                node_class=node_class,
                seed=int(uuid.uuid4().int % 2_147_483_647),
            )
            if node_class == "LatentSyncNode":
                graph["1"]["inputs"]["video"] = v_abs
                graph["2"]["inputs"]["audio_file"] = a_name
            elif node_class == "D_LatentSyncNode":
                graph["1"]["inputs"]["audio"] = a_name or a_abs
                graph["2"]["inputs"]["video_path"] = v_abs
            pid = await comfy.queue_prompt(graph, workflow_key="lipsync.latentsync")
            hist = await self._wait_comfy(job, pid)
            found = comfy.find_output_files(hist)
            out_dest = Path(scene.output_path).with_name(Path(scene.output_path).stem + "_lipsync.mp4")
            if found:
                shutil.copy2(found[0], out_dest)
                return out_dest
            recovered = extract_output_path_from_history(hist)
            if recovered:
                shutil.copy2(recovered, out_dest)
                return out_dest
            raise lipsync_no_output_error(hist)

        plan = resolve_render_plan(project)
        use_direct = os.environ.get("STUDIO_LIPSYNC_DIRECT", "").strip() in {"1", "true", "yes"} or bool(
            job_params.get("direct_latentsync")
        )

        async def _direct(source: Path) -> Path:
            out_dest = Path(scene.output_path).with_name(Path(scene.output_path).stem + "_lipsync.mp4")
            return await asyncio.to_thread(
                run_latentsync_direct,
                video_path=source,
                audio_path=Path(audio_asset.path),
                dest=out_dest,
                seed=int(uuid.uuid4().int % 2_147_483_647),
            )

        try:
            dest = await (_direct(video_source) if use_direct else _run_once(video_source))
        except RuntimeError as exc:
            msg = str(exc).lower()
            face_needed = "no detectable face" in msg or "no face" in msg or "produced no output" in msg or "no discoverable output" in msg
            still_asset = self._get_asset(db, scene.start_asset_id or job_params.get("face_asset_id"))
            if (
                face_needed
                and not prefer_still_face
                and still_asset
                and still_asset.kind == "image"
                and Path(still_asset.path).is_file()
            ):
                still_dest = (
                    settings.data_dir
                    / "projects"
                    / project.id
                    / "renders"
                    / f"scene_{scene.index}_lipsync_still_{uuid.uuid4().hex[:8]}.mp4"
                )
                retry_source = prepare_still_face_video(
                    image_path=Path(still_asset.path),
                    audio_path=Path(audio_asset.path),
                    dest=still_dest,
                    fps=getattr(project, "fps", 25) or 25,
                )
                try:
                    dest = await (_direct(retry_source) if use_direct else _run_once(retry_source))
                except RuntimeError:
                    dest = await _direct(retry_source)
            elif "produced no output" in msg or "no discoverable output" in msg or "execution_success" in msg:
                # Comfy node may return a stale cached path; fall back to direct inference.
                dest = await _direct(video_source)
            else:
                raise
        scene.lipsync_output_path = str(dest)
        db.commit()
        return dest

    async def _lipsync(self, db: Session, job: Job, project: Project) -> None:
        scene = db.get(Scene, job.scene_id) if job.scene_id else None
        if not scene:
            raise RuntimeError("Scene not found")
        path = await self._lipsync_scene(db, project, scene, job)
        if path:
            self._register_lipsync_asset(db, project, scene, Path(path), job)
        self._set_status(job.id, "done", 1.0, "Lip sync complete", str(path) if path else None)

    def _register_lipsync_asset(
        self,
        db: Session,
        project: Project,
        scene: Scene,
        dest: Path,
        job: Job,
    ) -> Asset | None:
        """Register a real lipsync MP4 into the project library with lineage."""
        if not dest.is_file() or dest.stat().st_size <= 0:
            return None
        existing = (
            db.query(Asset)
            .filter(Asset.project_id == project.id, Asset.path == str(dest))
            .first()
        )
        if existing:
            return existing
        parent_id = None
        try:
            payload = json.loads(job.params_json or "{}")
        except Exception:
            payload = {}
        face_id = payload.get("face_asset_id") or payload.get("faceAssetId")
        audio_id = (
            payload.get("audio_asset_id")
            or payload.get("audioAssetId")
            or scene.lipsync_audio_asset_id
            or scene.audio_asset_id
        )
        if face_id and db.get(Asset, face_id):
            parent_id = str(face_id)
        meta = {
            "op": "lipsync",
            "sceneId": scene.id,
            "sceneIndex": scene.index,
            "sourceVideo": scene.output_path,
            "audioAssetId": audio_id,
            "faceAssetId": face_id,
            "jobId": job.id,
            "provider": "latentsync",
        }
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tag=f"scene_{scene.index}_lipsync",
            kind="video",
            filename=dest.name,
            path=str(dest),
            comfy_name="",
            scope="project",
            parent_asset_id=parent_id,
            prompt_meta_json=json.dumps(meta),
            labels_json=json.dumps(["lipsync", "final-candidate", f"scene-{scene.index}"]),
            production_approval="none",
        )
        db.add(asset)
        db.flush()
        try:
            from .asset_graph import add_edge

            if audio_id and db.get(Asset, audio_id):
                add_edge(db, asset.id, str(audio_id), relation="uses_audio")
            if parent_id:
                add_edge(db, asset.id, parent_id, relation="derived_from")
        except Exception:
            logging.getLogger(__name__).debug("lipsync lineage edges skipped", exc_info=True)
        project.updated_at = datetime.utcnow()
        db.commit()
        return asset

    async def _image_tool(self, db: Session, job: Job, project: Project) -> None:
        # Prefer params_json — job.message is overwritten with status/error text during execution.
        payload: dict = {}
        try:
            payload = json.loads(job.params_json or "{}") or {}
        except Exception:
            payload = {}
        if not payload.get("source_asset_id"):
            try:
                msg_payload = json.loads(job.message or "{}") or {}
                if isinstance(msg_payload, dict) and msg_payload.get("source_asset_id"):
                    payload = msg_payload
            except Exception:
                pass
        source_id = payload.get("source_asset_id")
        char_name = (payload.get("character_name") or "character").strip().lower()
        char_name = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in char_name) or "character"
        seed = int(payload.get("seed", -1))
        plan = resolve_render_plan(project)
        width = int(payload.get("width") or plan.image_tool_size)
        height = int(payload.get("height") or plan.image_tool_size)
        # Cap image tools to VRAM profile size on ≤24 GB
        if plan.vram_gb < 32:
            width = min(width, plan.image_tool_size)
            height = min(height, plan.image_tool_size)
        extra = (payload.get("extra_prompt") or "").strip()

        source = self._get_asset(db, source_id)
        if not source:
            raise RuntimeError("Source reference image asset not found")
        ref = await self._ensure_comfy_image(source)
        if not ref:
            raise RuntimeError("Could not upload reference image to ComfyUI")

        if job.kind == "multi_angle":
            views = customize_angle_prompts(payload.get("angle_prompts") or [])
        else:
            views = views_for_tool("character_sheet")

        created_paths: list[str] = []
        view_assets: dict[str, dict[str, str]] = {}
        for i, view in enumerate(views):
            if job.id in self._cancel:
                self._set_status(job.id, "cancelled", i / len(views), "Cancelled")
                return

            prompt = view["prompt"]
            if extra:
                prompt = f"{prompt}. {extra}"

            job.progress = i / max(1, len(views))
            job.message = f"Generating {view['label']} ({i + 1}/{len(views)})"
            job.updated_at = datetime.utcnow()
            db.commit()

            view_seed = seed if seed >= 0 else (abs(hash(f"{project.id}:{view['key']}")) % (2**31))
            prefix = f"studio/{project.id[:8]}_{job.kind}_{view['key']}"
            from .image_runtime.contract import resolve_image_workflow
            from .image_runtime.workflow_execute import build_leaf_graph

            sheet_contract = resolve_image_workflow(
                "image.edit",
                engine="zimage",
                force_workflow_key="zimage.ref_edit",
                allow_draft=True,
            )
            wf = build_leaf_graph(
                sheet_contract,
                settings=settings,
                prompt=prompt,
                width=width,
                height=height,
                seed=view_seed + i,
                steps=settings.zimage_steps,
                cfg=settings.zimage_cfg,
                filename_prefix=prefix,
                reference_image=ref,
            )
            from .image_runtime.workflow_execute import legacy_comfy_workflow_key

            prompt_id = await comfy.queue_prompt(
                wf, workflow_key=legacy_comfy_workflow_key("zimage.ref_edit")
            )
            db.commit()
            history = await self._wait_comfy(job, prompt_id)
            files = comfy.find_output_files(history)
            if not files:
                raise RuntimeError(f"No output for {view['label']}")

            asset_id = str(uuid.uuid4())
            dest_dir = settings.data_dir / "assets" / project.id
            dest_dir.mkdir(parents=True, exist_ok=True)
            ext = files[0].suffix or ".png"
            dest = dest_dir / f"{asset_id}{ext}"
            shutil.copy2(files[0], dest)

            tag = f"{char_name}_{view['tag_suffix']}"
            comfy_name = ""
            try:
                comfy_name = await comfy.upload_image(dest, filename=f"{tag}{ext}")
            except Exception:
                comfy_name = ""

            asset = Asset(
                id=asset_id,
                project_id=project.id,
                tag=tag,
                kind="image",
                filename=f"{tag}{ext}",
                path=str(dest),
                comfy_name=comfy_name,
            )
            db.add(asset)
            db.commit()
            created_paths.append(str(dest))
            view_assets[str(view["key"])] = {
                "assetId": asset_id,
                "tag": tag,
                "path": str(dest),
                "label": view.get("label") or view["key"],
            }

        # Persist role-mappable outputs for Character Creator visual sheet attach
        try:
            from .workflows.image_tools import CHARACTER_SHEET_ROLE_MAP

            role_assets = {
                CHARACTER_SHEET_ROLE_MAP[k]: v["assetId"]
                for k, v in view_assets.items()
                if k in CHARACTER_SHEET_ROLE_MAP
            }
        except Exception:
            role_assets = {}
        params = {}
        try:
            params = json.loads(job.params_json or "{}") or {}
        except Exception:
            params = {}
        params.update(
            {
                "output_asset_id": next(iter(view_assets.values()), {}).get("assetId"),
                "output_asset_ids": [v["assetId"] for v in view_assets.values()],
                "view_assets": view_assets,
                "role_assets": role_assets,
                "character_name": char_name,
                "tool": job.kind,
            }
        )
        job.params_json = json.dumps(params)
        db.commit()

        summary = f"Created {len(created_paths)} images as @{char_name}_* assets"
        self._set_status(job.id, "done", 1.0, summary, created_paths[0] if created_paths else None)

    async def _dual_lipsync(self, db: Session, job: Job, project: Project) -> None:
        scene = db.get(Scene, job.scene_id) if job.scene_id else None
        if not scene:
            raise RuntimeError("Scene not found")
        video = scene.output_path
        if not video or not Path(video).exists():
            raise RuntimeError("Scene has no rendered video — generate the scene first")

        tracks = parse_lipsync_tracks(scene.lipsync_tracks_json)
        enabled = [t for t in tracks.tracks if t.enabled]
        if not enabled:
            raise RuntimeError("No enabled lip-sync tracks")

        # Bake sticky paths if missing
        for track in enabled:
            if track.track_path:
                continue
            job.message = f"Baking sticky mouth track for {track.label}"
            job.progress = 0.1
            db.commit()
            seed = Roi(track.roi.x, track.roi.y, track.roi.w, track.roi.h)
            track.track_path = track_mouth_rois(Path(video), seed)

        scene.lipsync_tracks_json = dumps_lipsync_tracks(tracks)
        db.commit()

        # Detect available lipsync node
        import httpx

        use_latent = False
        use_sync = False
        async with httpx.AsyncClient(timeout=10.0) as client:
            r1 = await client.get(f"{settings.comfy_url}/object_info/LatentSyncNode")
            use_latent = r1.status_code == 200
            r2 = await client.get(f"{settings.comfy_url}/object_info/SyncLipSyncNode")
            use_sync = r2.status_code == 200

        if not use_latent and not use_sync:
            # Still succeed on tracking bake so UI is useful before lipsync models are installed
            self._set_status(
                job.id,
                "done",
                1.0,
                "Sticky mouth tracks baked. Install LatentSync (or Sync) to apply audio lip sync.",
                video,
            )
            return

        current_video = Path(video)
        for i, track in enumerate(enabled):
            job.message = f"Lip sync {track.label} ({i + 1}/{len(enabled)})"
            job.progress = 0.3 + 0.5 * (i / max(1, len(enabled)))
            db.commit()
            audio_asset = self._get_asset(db, track.audio_asset_id)
            if not audio_asset:
                raise RuntimeError(f"{track.label} has no audio asset")
            audio_name = await self._ensure_comfy_file(audio_asset)
            video_name = await comfy.upload_file_copy(current_video, filename=current_video.name)

            if use_latent:
                wf = build_latentsync_workflow(
                    video_path=str(settings.comfy_input_dir / video_name.replace("/", "\\")),
                    audio_path=audio_name or "",
                    filename_prefix=f"studio/{project.id[:8]}_dual_ls_{track.slot}",
                )
                wf["2"]["inputs"]["audio_file"] = audio_name
            else:
                # Sync.so API node as fallback when present
                wf = {
                    "1": {
                        "class_type": "LoadVideo",
                        "inputs": {"file": str(settings.comfy_input_dir / video_name.replace("/", "\\"))},
                    },
                    "2": {
                        "class_type": "VHS_LoadAudio",
                        "inputs": {"audio_file": audio_name, "seek_seconds": 0, "duration": 0},
                    },
                    "3": {
                        "class_type": "SyncLipSyncNode",
                        "inputs": {
                            "video": ["1", 0],
                            "audio": ["2", 0],
                            "seed": 42,
                            "model": "sync-3",
                        },
                    },
                    "4": {
                        "class_type": "SaveVideo",
                        "inputs": {
                            "video": ["3", 0],
                            "filename_prefix": f"studio/{project.id[:8]}_dual_ls_{track.slot}",
                            "format": "mp4",
                            "codec": "h264",
                        },
                    },
                }

            prompt_id = await comfy.queue_prompt(
                wf,
                workflow_key="lipsync.latentsync" if use_latent else None,
            )
            db.commit()
            history = await self._wait_comfy(job, prompt_id)
            files = comfy.find_output_files(history)
            if not files:
                raise RuntimeError(f"No lip-sync output for {track.label}")
            dest = (
                settings.data_dir
                / "projects"
                / project.id
                / "renders"
                / f"scene_{scene.index}_lipsync_c{track.slot}_{uuid.uuid4().hex[:6]}.mp4"
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(files[0], dest)
            current_video = dest

        scene.lipsync_output_path = str(current_video)
        db.commit()
        self._set_status(
            job.id,
            "done",
            1.0,
            f"Dual lip sync complete ({len(enabled)} track(s)) with sticky mouth ROIs",
            str(current_video),
        )

    async def _media_retake(self, db: Session, job: Job, project: Project) -> None:
        from .media_retake.executor import run_media_retake

        params = self._job_params(job)
        span = params.get("roomToneSpan") or {}
        room_tone_span = None
        if span.get("start") is not None and span.get("end") is not None:
            room_tone_span = (float(span["start"]), float(span["end"]))

        async def _progress(p: float, msg: str) -> None:
            job.progress = p
            job.message = (msg or "")[:4000]
            db.commit()

        out = await run_media_retake(
            db,
            job,
            project,
            room_tone_span=room_tone_span,
            progress_cb=_progress,
        )
        self._set_status(
            job.id,
            "done",
            1.0,
            f"Media retake complete: {out.name}",
            str(out),
        )

    async def _performance_retake(self, db: Session, job: Job, project: Project) -> None:
        from .performance_retake.contracts import (
            CharacterSheetRef,
            PerformanceRetakeSpec,
            RetakeBeat,
            RetakeReferences,
            RetakeWindow,
            validate_spec,
        )
        from .performance_retake.executor import execute_performance_retake

        params = self._job_params(job)

        def _reconstruct_spec() -> PerformanceRetakeSpec:
            window = RetakeWindow(**params["window"])
            beats = [RetakeBeat(**b) for b in params.get("beats", [])]
            refs = params.get("references", {}) or {}
            references = RetakeReferences(
                characterSheets=[
                    CharacterSheetRef(**c) for c in refs.get("characterSheets", [])
                ],
                sourceVideo=refs.get("sourceVideo", True),
                includeSourceAudio=refs.get("includeSourceAudio", False),
            )
            return PerformanceRetakeSpec(
                projectId=params["projectId"],
                sceneId=params["sceneId"],
                window=window,
                beats=beats,
                references=references,
                masterDurationSec=float(params["masterDurationSec"]),
                generator=params.get("generator", "minimax-h3-r2v-local"),
                quality=params.get("quality", "quality"),
                qwenPreReview=params.get("qwenPreReview", True),
                qwenPostReview=params.get("qwenPostReview", True),
                specVersion=params.get("specVersion", 1),
            )

        spec = _reconstruct_spec()
        validate_spec(spec)

        result = await execute_performance_retake(
            db,
            spec,
            job_id=job.id,
            log=lambda msg: logger.info(msg),
        )

        self._set_status(
            job.id,
            "done",
            1.0,
            f"Performance retake complete: {Path(result['outputPath']).name}",
            result["outputPath"],
            video_runtime_patch={"performanceRetake": result},
        )

    def _job_params(self, job: Job) -> dict:
        try:
            return json.loads(job.params_json or "{}") or {}
        except Exception:
            return {}

    def _checkpoint_for_model(self, model_id: str, custom: str = "") -> str:
        mid = (model_id or "auto").lower()
        if mid == "custom" and custom:
            return custom
        if mid == "hidream":
            return settings.imagegen_hidream_checkpoint
        if mid in ("sd35", "sd3.5"):
            return settings.imagegen_sd35_checkpoint
        if mid == "illustrious":
            return settings.imagegen_illustrious_checkpoint
        if mid in ("sd15", "sd1.5", "sd_1.5", "stable-diffusion-1.5", "stable_diffusion_15"):
            return settings.imagegen_sd15_checkpoint
        if mid in ("qwen2512", "qwen-image-2512", "qwen_image_2512", "qwen"):
            # Qwen Image 2512 runs use the Qwen UNET, not the FLUX checkpoint —
            # job status must name the real checkpoint (CDX-082).
            return settings.qwen_image_2512_unet
        if mid == "custom":
            return settings.imagegen_custom_checkpoint or settings.imagegen_flux_checkpoint
        if mid in ("zimage", "auto"):
            return settings.zimage_unet
        # Explicit flux request keeps the configured FLUX checkpoint name (may be absent).
        return settings.imagegen_flux_checkpoint

    def _zimage_stack_ready(self) -> bool:
        """True when catalogued Z-Image still-image weights verify on disk."""
        try:
            from .setup.diagnostics import verify_component

            return bool(verify_component("zimage_models").healthy)
        except Exception:
            return False

    def _checkpoint_file_present(self, checkpoint_name: str) -> bool:
        name = (checkpoint_name or "").strip()
        if not name:
            return False
        try:
            from .setup.paths import default_models_root

            roots = [default_models_root(), Path(settings.data_dir) / "models"]
            sd15_root = str(getattr(settings, "sd15_model_root", "") or "").strip()
            if sd15_root:
                roots.append(Path(sd15_root))
            for root in roots:
                if not root or not Path(root).exists():
                    continue
                direct = Path(root) / name
                if direct.is_file():
                    return True
                for sub in ("checkpoints", "diffusion_models", "unet"):
                    candidate = Path(root) / sub / name
                    if candidate.is_file():
                        return True
                # Basename search — capped depth via rglob on known folders only.
                for sub in ("checkpoints", "diffusion_models", "unet"):
                    folder = Path(root) / sub
                    if folder.is_dir():
                        for path in folder.rglob(name):
                            if path.is_file():
                                return True
        except Exception:
            return False
        return False

    def _resolve_ready_still_model(self, requested: str) -> tuple[str, list[str]]:
        """Pick preferred or alternate compatible local ImageGen model.

        Z-Image is preferred when GREEN, but not mandatory when another supported
        local still engine is ready.
        """
        reasons: list[str] = []
        mid = (requested or "auto").lower()
        if mid != "auto":
            return mid, reasons

        if self._zimage_stack_ready():
            reasons.append("Preferred local still engine: catalogued Z-Image Turbo (GREEN)")
            return "zimage", reasons

        alternates = (
            ("flux", settings.imagegen_flux_checkpoint),
            ("hidream", settings.imagegen_hidream_checkpoint),
            ("sd35", settings.imagegen_sd35_checkpoint),
            ("custom", settings.imagegen_custom_checkpoint or settings.imagegen_flux_checkpoint),
        )
        for model_id, ckpt in alternates:
            if ckpt and self._checkpoint_file_present(ckpt):
                reasons.append(
                    f"Z-Image unavailable; selected compatible local still engine '{model_id}' "
                    f"({ckpt})"
                )
                return model_id, reasons

        raise RuntimeError(
            "No ready local still-image engine. Install/verify zimage_models or another "
            "supported ImageGen checkpoint (FLUX / HiDream / SD3.5 / custom) in Source Manager."
        )

    def _extract_last_frame(self, video_path: Path, dest: Path) -> Path:
        """Extract last frame of a video for generative continuation (video.extend)."""
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg required to extract last frame for video.extend")
        dest.parent.mkdir(parents=True, exist_ok=True)
        # -sseof seeks from end; one frame PNG
        cmd = [
            ffmpeg,
            "-y",
            "-sseof",
            "-0.05",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(dest),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not dest.is_file():
            # Fallback: first frame if last-frame seek fails on short clips
            cmd2 = [ffmpeg, "-y", "-i", str(video_path), "-frames:v", "1", str(dest)]
            proc2 = subprocess.run(cmd2, capture_output=True, text=True)
            if proc2.returncode != 0 or not dest.is_file():
                raise RuntimeError(
                    f"Failed to extract frame for video.extend: {proc.stderr or proc2.stderr}"
                )
        return dest

    async def _video_extend_local(self, db: Session, job: Job, project: Project) -> None:
        """M41 4.1B: certified video.extend — last frame → local I2V (not fal-only txt2vid)."""
        from .video_runtime.job_model import merge_video_runtime_history
        from .video_runtime.output_gate import validate_video_output
        from .video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
        from .video_runtime.workflow_resolver import resolve_workflow

        params = self._job_params(job)
        source_id = (
            params.get("source_asset_id")
            or params.get("start_asset_id")
            or (params.get("videoRuntime") or {}).get("start_asset_id")
        )
        source = self._get_asset(db, source_id) if source_id else None
        if not source or not source.path or not Path(source.path).is_file():
            raise RuntimeError("video.extend requires a source asset with a readable file")

        src_path = Path(source.path)
        work = settings.data_dir / "projects" / project.id / "extend" / job.id
        work.mkdir(parents=True, exist_ok=True)
        start_frame = work / "last_frame.png"
        if src_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            shutil.copy2(src_path, start_frame)
        else:
            self._extract_last_frame(src_path, start_frame)

        comfy_name = await self._ensure_comfy_image_path(start_frame)
        engine = str(
            (params.get("videoRuntime") or {}).get("engine")
            or params.get("engine")
            or "ltx"
        )
        contract = resolve_workflow(
            "extend",
            engine=engine,
            present_inputs={"start_frame": True, "source_video": True},
        )
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {
                "workflowContract": contract.to_dict(),
                "extend": {"sourceAssetId": source.id, "lastFrame": str(start_frame)},
            },
        )
        job.message = f"video.extend → {contract.leaf_workflow_key}"
        db.commit()

        prompt = (params.get("prompt") or "Continue the motion naturally").strip()
        negative = params.get("negative") or project.negative_prompt or ""
        duration = float(params.get("duration_sec") or 2.0)
        fps = int(project.fps or 24)
        length = max(17, int(duration * fps))
        width = int(getattr(project, "width", None) or 768)
        height = int(getattr(project, "height", None) or 512)
        seed = int(params.get("seed") if params.get("seed") is not None else project.seed)

        wf = build_leaf_graph(
            contract,
            settings=settings,
            positive=prompt,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=comfy_name,
            steps=8,
            filename_prefix=f"studio/extend_{job.id[:8]}",
        )
        wf = prepare_executable_graph(contract, wf)
        prompt_id = await comfy.queue_prompt(wf, workflow_key=contract.leaf_workflow_key)
        job.comfy_prompt_id = prompt_id
        self.bind_prompt(job.id, prompt_id)
        db.commit()

        async def on_progress(p: float, msg: str) -> None:
            job.progress = p
            job.message = msg
            job.updated_at = datetime.utcnow()
            db.commit()

        history = await self._wait_comfy(job, prompt_id, on_progress=on_progress)
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError("video.extend finished but no output video was found")
        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"extend_{uuid.uuid4().hex[:8]}{files[0].suffix}"
        shutil.copy2(files[0], dest)
        gate = validate_video_output(dest, asset_registered=False)
        if not gate.passed:
            raise RuntimeError(gate.message)
        # Register derived asset
        try:
            from .generation_tools.lineage import register_derived_asset

            asset = register_derived_asset(
                db,
                project_id=project.id,
                source_path=dest,
                kind="video",
                tag="video_extend",
                parent_asset_id=source.id,
                op="video_extend",
                model="generative_continuation",
                prompt_meta={"mode": "generative_continuation", "jobId": job.id},
                library_key="video.generated",
            )
            self._set_status(
                job.id, "done", 1.0, "video.extend complete (local I2V)", str(dest)
            )
            job.history_json = merge_video_runtime_history(
                job.history_json, {"assetId": asset.id, "outputGate": gate.to_dict()}
            )
            db.commit()
        except Exception:
            self._set_status(job.id, "done", 1.0, "video.extend complete", str(dest))

    async def _ensure_comfy_image_path(self, path: Path) -> str:
        """Upload a local image path into Comfy input and return the Comfy filename."""
        # Reuse asset helper pattern when possible
        return await comfy.upload_image(path)

    async def _txt2vid(self, db: Session, job: Job, project: Project) -> None:
        """Text-to-video. Local LTX 2.5 / MiniMax first. Hosted only when selected or approved."""
        params = self._job_params(job)
        # TEXT-ONLY CONTRACT: Text to Video is text-only. Strip any reference /
        # image / spatial / start-frame asset IDs that may have leaked in from
        # project state, scene state, or Co-Director bindings. T2V never
        # inherits image references — those belong to 1 Frame / 3 Frame / Timeline.
        for _ref_key in (
            "spatialMapId",
            "spatialMapVersion",
            "spatialCameraId",
            "spatialStartCameraId",
            "spatialEndCameraId",
            "spatialReferenceBundle",
            "spatialReferenceAssetIds",
            "sceneReferenceProvenance",
            "start_asset_id",
            "source_asset_id",
            "reference_asset_ids",
            "referenceAssetIds",
        ):
            params.pop(_ref_key, None)

        prompt = (params.get("prompt") or "").strip() or project.global_prompt
        negative = params.get("negative") or project.negative_prompt
        engine = params.get("engine") or "auto"
        duration = float(params.get("duration_sec") or 5)
        aspect = params.get("aspect") or "16:9"
        seed = int(params.get("seed") if params.get("seed") is not None else project.seed)
        width = int(params.get("width") or project.width)
        height = int(params.get("height") or project.height)
        style = params.get("style") or ""
        if style:
            prompt = f"{prompt}, {style} style".strip(", ")
        creator_prompt = prompt

        from .local_first import assert_fal_allowed, paid_fallback_approved
        from .video_runtime.local_t2v import (
            i2v_only_blocker,
            is_local_ltx25_t2v_engine,
            is_local_minimax_t2v_engine,
            local_t2v_unavailable_blocker,
            resolve_txt2vid_engine,
        )

        resolved = resolve_txt2vid_engine(
            str(engine),
            paid_fal_approved=paid_fallback_approved(params),
        )
        params = {**params, "resolvedEngine": resolved, "engine": resolved if resolved != "auto" else engine}
        job.params_json = json.dumps(params)
        db.commit()
        if resolved not in {"", "auto"}:
            from .video_runtime.legal_canvas import SpecFidelityError, preflight_spec

            spec = preflight_spec(
                str(resolved),
                width=width,
                height=height,
                length_seconds=duration,
                fps=self._txt2vid_fps(params, project),
                surface="t2v",
            )
            if not spec["ok"]:
                raise SpecFidelityError(
                    spec["message"],
                    suggestions=list(spec.get("suggestions") or []),
                    code="SPEC_FIDELITY",
                )

        if is_local_ltx25_t2v_engine(resolved):
            await self._txt2vid_ltx25(
                db,
                job,
                project,
                params=params,
                prompt=prompt,
                negative=negative,
                seed=seed,
                width=width,
                height=height,
                duration=duration,
                creator_prompt=creator_prompt,
            )
            return
        if is_local_minimax_t2v_engine(resolved):
            await self._txt2vid_minimax(
                db,
                job,
                project,
                params=params,
                prompt=prompt,
                seed=seed,
                creator_prompt=creator_prompt,
            )
            return
        if resolved == "auto":
            raise RuntimeError(json.dumps(local_t2v_unavailable_blocker()))
        if is_fal_engine(resolved) or is_fal_engine(str(engine)):
            resolved = resolved if is_fal_engine(resolved) else str(engine)
            assert_fal_allowed(params, engine=resolved)
        else:
            raise RuntimeError(json.dumps(i2v_only_blocker(engine=str(resolved))))

        api_key = get_secret("fal_api_key")
        if not api_key:
            raise RuntimeError(
                "Hosted AI Provider credential not configured. Open Setup → AI Providers "
                "(Kie.ai · WaveSpeed.ai · fal.ai)."
            )

        async def on_progress(p: float, msg: str) -> None:
            job.progress = min(0.95, max(0.05, p))
            job.message = msg[:4000]
            job.stage = "processing"
            job.updated_at = datetime.utcnow()
            db.commit()

        await on_progress(0.1, f"Txt2Vid · {resolved}")
        mil_params = params.get("modelIntelligence") or params.get("mil") or {}
        if not isinstance(mil_params, dict):
            mil_params = {}
        if "generate_audio" in params:
            generate_audio = bool(params.get("generate_audio"))
        elif "generate_audio" in mil_params:
            generate_audio = bool(mil_params.get("generate_audio"))
        else:
            generate_audio = True
        fal_prompt = str(mil_params.get("compiledPrompt") or prompt)
        fal_negative = str(mil_params.get("negativePrompt") or negative)
        # TEXT-ONLY: true T2V submits no image conditioning. image_url=None routes
        # fal_seedance to its text-to-video endpoint and leaves Kling/Veo/Runway
        # in text-only mode. No reference images are uploaded.
        image_url = None
        end_image_url = None
        model_id, args = build_fal_arguments(
            engine=resolved,
            prompt=fal_prompt,
            negative=fal_negative,
            image_url=image_url,
            end_image_url=end_image_url,
            duration_sec=duration,
            width=width,
            height=height,
            seed=seed,
            generate_audio=generate_audio,
        )
        job.comfy_prompt_id = model_id[:64]
        job.history_json = json.dumps(
            {
                "prompt": prompt,
                "creatorPrompt": creator_prompt,
                "negative": negative,
                "seed": seed,
                "model": model_id,
                "engine": resolved,
                "requestedEngineId": str(engine),
                "resolvedEngineId": resolved,
                "provider": "fal",
                "modelVersion": (
                    "2.5" if seedance_product_id(resolved) == "seedance-2.5" else
                    "2.0" if seedance_product_id(resolved) == "seedance-2.0" else None
                ),
                "aspect": aspect,
                "width": width,
                "height": height,
                "duration_sec": duration,
                "style": style,
                "loras": params.get("loras") or [],
            }
        )
        db.commit()

        async def on_request_id(request_id: str) -> None:
            self._record_fal_request_id(db, job, model_id=model_id, request_id=request_id)

        result = await run_fal_model(
            model_id, args, api_key, on_progress=on_progress, on_request_id=on_request_id
        )
        video_url = extract_video_url(result)
        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"txt2vid_{uuid.uuid4().hex[:8]}_fal.mp4"
        await download_url(video_url, dest)

        # Auto-add to library
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tag=params.get("tag") or "txt2vid",
            kind="video",
            filename=dest.name,
            path=str(dest),
            comfy_name="",
            scope="project",
            prompt_meta_json=job.history_json or "{}",
        )
        db.add(asset)
        try:
            from .asset_graph import add_version

            add_version(
                db,
                asset_id=asset.id,
                op="txt2vid",
                path=str(dest),
                seed=seed,
                prompt={"prompt": prompt, "negative": negative},
                model=model_id,
            )
        except Exception:
            pass
        db.commit()
        job.params_json = json.dumps({**params, "output_asset_id": asset.id})
        db.commit()
        self._set_status(job.id, "done", 1.0, "Txt2Vid complete", str(dest))

    def _txt2vid_fps(self, params: dict, project: Project) -> int:
        raw = params.get("fps")
        if raw in (None, "", "auto"):
            return int(getattr(project, "fps", 24) or 24)
        try:
            return max(8, int(float(raw)))
        except (TypeError, ValueError):
            return 24

    async def _txt2vid_ltx25(
        self,
        db: Session,
        job: Job,
        project: Project,
        *,
        params: dict,
        prompt: str,
        negative: str,
        seed: int,
        width: int,
        height: int,
        duration: float,
        creator_prompt: str,
    ) -> None:
        from .video_runtime.job_model import merge_video_runtime_history
        from .video_runtime.output_gate import validate_video_output
        from .video_runtime.scene_output_library import register_render_output_asset
        from .video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
        from .video_runtime.workflow_resolver import local_video_identity, resolve_workflow

        fps = self._txt2vid_fps(params, project)
        from .video_runtime.legal_canvas import assert_legal_duration

        length = assert_legal_duration("ltx-2.5", float(duration), int(fps), surface="t2v")
        generate_audio = bool(params.get("generate_audio", True))
        contract = resolve_workflow(
            "txt2vid",
            engine="ltx-2.5",
            present_inputs={},
            paid_fal_approved=False,
            generator_id="ltx-2.5-distilled",
        )
        if contract.leaf_workflow_key != "ltx_25.t2v":
            raise RuntimeError(
                f"LTX 2.5 Text to Video resolved {contract.leaf_workflow_key}, not ltx_25.t2v."
            )
        identity = local_video_identity(
            requested_model="ltx-2.5-distilled",
            leaf_workflow_key=contract.leaf_workflow_key,
            ltx_25_checkpoint=settings.ltx_2_5_checkpoint,
        )
        job.message = "LTX 2.5 Text to Video · preparing"
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {
                "workflowContract": contract.to_dict(),
                "modelIdentity": identity,
                "provenance": "LOCAL — LTX 2.5 — Text to Video",
            },
        )
        db.commit()
        try:
            await comfy.free_memory(unload_models=True, free_memory=True)
        except Exception:
            logging.getLogger(__name__).warning("Comfy free_memory before LTX 2.5 T2V failed", exc_info=True)

        prefix = f"studio/{project.id[:8]}/txt2vid/job_{job.id[:8]}"
        wf = build_leaf_graph(
            contract,
            settings=settings,
            positive=prompt,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=None,
            steps=int(params.get("steps") or 20),
            filename_prefix=prefix,
            generate_audio=generate_audio,
        )
        wf = prepare_executable_graph(contract, wf, enforce_certified_fingerprint=False)

        async def on_progress(p: float, msg: str) -> None:
            job.progress = min(0.95, max(0.05, p))
            job.message = msg[:4000]
            job.updated_at = datetime.utcnow()
            db.commit()

        prompt_id = await comfy.queue_prompt(wf, workflow_key="ltx_25.t2v")
        job.comfy_prompt_id = prompt_id
        self.bind_prompt(job.id, prompt_id)
        db.commit()
        history = await self._wait_comfy(
            job, prompt_id, on_progress=on_progress, preview_engine="ltx-2.5"
        )
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError("LTX 2.5 Text to Video finished but no output video was found.")
        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"txt2vid_{uuid.uuid4().hex[:8]}_ltx25.mp4"
        shutil.copy2(files[0], dest)
        gate = validate_video_output(dest, asset_registered=False)
        if not gate.passed:
            raise RuntimeError(gate.message or "LTX 2.5 Text to Video output was refused.")
        history_payload = {
            "prompt": prompt,
            "creatorPrompt": creator_prompt,
            "negative": negative,
            "seed": seed,
            "engine": "ltx-2.5",
            "model": identity.get("resolvedRuntimeModel"),
            "provenance": "LOCAL — LTX 2.5 — Text to Video",
            "workflowKey": "ltx_25.t2v",
            "width": width,
            "height": height,
            "duration_sec": duration,
        }
        job.history_json = json.dumps(history_payload)
        job.history_json = merge_video_runtime_history(
            job.history_json, {"outputGate": gate.to_dict(), "provenance": history_payload["provenance"]}
        )
        out_asset = register_render_output_asset(
            db,
            project_id=project.id,
            dest=dest,
            tag=params.get("tag") or "txt2vid",
            prompt_meta=history_payload,
        )
        job.params_json = json.dumps(
            {**params, "output_asset_id": out_asset.id, "resolvedRuntimeModel": identity.get("resolvedRuntimeModel")}
        )
        db.commit()
        self._set_status(job.id, "done", 1.0, "LTX 2.5 Text to Video complete", str(dest))

    async def _txt2vid_minimax(
        self,
        db: Session,
        job: Job,
        project: Project,
        *,
        params: dict,
        prompt: str,
        seed: int,
        creator_prompt: str,
    ) -> None:
        from .minimax_h3.route_a_adapter import RouteARuntimeAdapter, import_output_to_project_library
        from .minimax_h3.service import _ensure_route_a_for_generation
        from .video_runtime.job_model import merge_video_runtime_history

        job.message = "Preparing MiniMax Text to Video"
        job.history_json = merge_video_runtime_history(
            job.history_json,
            {
                "t2v": {
                    "mechanism": "route_a_t2va",
                    "runtime": "minimax-route-a",
                    "provenance": "LOCAL — MiniMax H3 — Text to Video",
                }
            },
        )
        db.commit()
        prepared, err = await asyncio.to_thread(_ensure_route_a_for_generation)
        if not prepared:
            raise RuntimeError(err or "MiniMax runtime could not start.")
        adapter = RouteARuntimeAdapter()
        state = await asyncio.to_thread(
            adapter.submit_t2va,
            project_id=project.id,
            plan_id=f"t2v-{job.id[:8]}",
            prompt=prompt,
            seed=seed,
            duration_sec=float(params.get("duration_sec") or 5),
            width=int(params.get("width") or project.width),
            height=int(params.get("height") or project.height),
            fps=float(params.get("fps") or project.fps or 24),
            steps=int(params.get("steps") or 0) or None,
            studio_job_id=job.id,
        )
        if state.status == "failed":
            raise RuntimeError(state.error_message or "MiniMax Text to Video failed to start.")
        job.comfy_prompt_id = (state.prompt_id or "")[:64]
        job.status = "running"
        job.stage = "processing"
        job.progress = max(float(job.progress or 0), 0.12)
        summary = _route_a_graph_summary(state)
        job.message = (
            f"MiniMax Text to Video · generating{(' · ' + summary) if summary else ''}"
        )
        if state.prompt_id:
            self.bind_prompt(job.id, state.prompt_id)
        db.commit()
        state = await asyncio.to_thread(
            self._poll_route_a_with_preview, adapter, state, job, "minimax-h3", 900.0
        )
        if state.status != "completed" or not state.output_path:
            raise RuntimeError(state.error_message or "MiniMax Text to Video did not finish.")
        dest = Path(state.output_path)
        # Deterministic trim: trim excess generation tail to the requested duration.
        requested_duration_sec = float(params.get("duration_sec") or 0)
        if requested_duration_sec > 0:
            from .media_clip import trim_video_to_seconds

            trim_video_to_seconds(dest, requested_duration_sec)
        receipt = import_output_to_project_library(
            project_id=project.id,
            source_mp4=dest,
            tag=params.get("tag") or "txt2vid",
            db=db,
        )
        history_payload = {
            "prompt": prompt,
            "creatorPrompt": creator_prompt,
            "seed": seed,
            "engine": "minimax-h3",
            "model": "minimax-h3-route-a-t2va",
            "provenance": "LOCAL — MiniMax H3 — Text to Video",
            "libraryAssetId": receipt.get("assetId"),
        }
        job.history_json = json.dumps(history_payload)
        job.params_json = json.dumps({**params, "output_asset_id": receipt.get("assetId")})
        db.commit()
        self._set_status(
            job.id,
            "done",
            1.0,
            "MiniMax Text to Video complete",
            str(receipt.get("path") or dest),
        )

    def _poll_route_a_with_preview(
        self,
        adapter: Any,
        state: Any,
        job: Job,
        engine: str,
        timeout_sec: float,
    ) -> Any:
        """Poll Route A and publish live preview frames via the preview bus."""
        import threading
        import time
        from dataclasses import asdict

        from .minimax_h3.route_a_adapter import route_a_client_id
        from .preview_bus import GenerationPreview, preview_bus
        from .video_runtime.live_preview import tap_comfy_previews_sync
        from .video_runtime.progress import (
            extract_progress_state_fraction,
            route_a_progress_from_executing,
            route_a_progress_from_step,
        )

        import httpx

        stop = threading.Event()
        seq = [0]
        client_id = (
            getattr(state, "client_id", None)
            or route_a_client_id(state.job_id, mode=getattr(state, "mode", "") or "")
        )
        track: dict[str, Any] = {
            "node": None,
            "last_live": max(0.12, float(getattr(job, "progress", 0) or 0)),
            "last_msg": str(getattr(job, "message", "") or "MiniMax Route A"),
            "last_update": time.time(),
            "had_live_step": False,
        }

        def _persist_live(progress: float, message: str, *, stage: str) -> None:
            p = max(float(track["last_live"]), float(progress))
            track["last_live"] = p
            track["last_msg"] = message
            track["last_update"] = time.time()
            self._set_status(job.id, "running", p, message, stage=stage)

        def _persist_preview(preview: GenerationPreview) -> None:
            db = SessionLocal()
            try:
                row = db.get(Job, job.id)
                if not row:
                    return
                row.preview_json = json.dumps(asdict(preview))
                row.updated_at = datetime.utcnow()
                db.commit()
            except Exception:
                pass
            finally:
                db.close()

        def _on_frame(data: bytes) -> None:
            import sys
            try:
                seq[0] += 1
                print(
                    f"[preview-tap] FRAME {seq[0]} job={job.id} bytes={len(data)}",
                    file=sys.stderr,
                    flush=True,
                )
                ext = ".jpg" if data[:2] == b"\xff\xd8" else ".png"
                path = preview_bus.save_bytes(job.id, data, ext)
                preview = GenerationPreview(
                    jobId=job.id,
                    sceneId=str(job.scene_id or ""),
                    engineId=engine,
                    previewId=f"pv_{job.id[:8]}_{seq[0]}",
                    sequenceNumber=seq[0],
                    createdAt=datetime.utcnow().isoformat(),
                    stage="live_preview",
                    mediaType="image",
                    localPath=str(path),
                )
                preview_bus.publish_sync("preview_updated", preview)
                _persist_preview(preview)
                # Preview frames are secondary to Comfy step progress; never regress %.
                frame_p = max(0.25, min(0.90, 0.25 + seq[0] * 0.04))
                frame_p = max(float(track.get("last_live") or 0), frame_p)
                _persist_live(frame_p, f"Draft frame {seq[0]}", stage="sampling")
            except Exception as exc:
                import sys
                print(
                    f"[preview-tap] _on_frame FAILED job={job.id} err={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )

        def _on_event(mtype: str, data: dict[str, Any]) -> None:
            try:
                if mtype == "progress":
                    value = float(data.get("value") or 0)
                    mx = float(data.get("max") or 0) or 1.0
                    p, label = route_a_progress_from_step(
                        value,
                        mx,
                        last_live=float(track["last_live"]),
                        node=str(data.get("node") or track.get("node") or ""),
                    )
                    track["had_live_step"] = True
                    _persist_live(p, label, stage="sampling")
                    return
                if mtype == "progress_state":
                    extracted = extract_progress_state_fraction(data)
                    if not extracted:
                        return
                    frac, label = extracted
                    p = max(float(track["last_live"]), 0.30 + 0.55 * float(frac))
                    track["had_live_step"] = True
                    _persist_live(p, label, stage="sampling")
                    return
                if mtype != "executing":
                    return
                node = data.get("node")
                if node is None:
                    return
                track["node"] = str(node)
                p, label = route_a_progress_from_executing(
                    str(node), last_live=float(track["last_live"])
                )
                _persist_live(p, label, stage="processing")
            except Exception:
                pass

        def _tap() -> None:
            import sys
            try:
                print(
                    f"[preview-tap] START job={job.id} client_id={client_id} "
                    f"prompt_id={state.prompt_id or ''} base={adapter.base_url}",
                    file=sys.stderr,
                    flush=True,
                )
                tap_comfy_previews_sync(
                    adapter.base_url,
                    client_id,
                    state.prompt_id or "",
                    _on_frame,
                    stop,
                    on_event=_on_event,
                )
                print(
                    f"[preview-tap] END job={job.id} frames={seq[0]}",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[preview-tap] FAILED job={job.id} err={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )

        def _on_wait(elapsed: float) -> None:
            """Safety refresh while prompt is queue_running on the owning runtime.

            Never invent wall-clock percentages. Keep the last live Comfy value,
            but re-persist message/updated_at so the UI cannot sit silent for
            multi-minute MiniMax encodes that emit no step events.

            HARD RULE: this callback must not block ``adapter.poll`` — history
            is observed before on_wait, and this body is time-bounded.
            Also propagate Adept cancel into ``state.cancelled`` so Route A
            poll can exit (cancel_and_halt alone does not flip state.cancelled).
            """
            if job.id in self._cancel:
                state.cancelled = True
                return
            if elapsed < 2:
                return

            def _body() -> None:
                if job.id in self._cancel:
                    state.cancelled = True
                    return
                try:
                    queue = adapter._session.get(
                        f"{adapter.base_url}/queue",
                        timeout=httpx.Timeout(3.0, connect=2.0, read=3.0, write=3.0, pool=2.0),
                    ).json()
                except Exception:
                    queue = {}
                running = queue.get("queue_running") or []
                pending = queue.get("queue_pending") or []
                pid = str(state.prompt_id or "").strip()
                in_running = any(len(item) > 1 and item[1] == pid for item in running)
                in_pending = any(len(item) > 1 and item[1] == pid for item in pending)

                db = SessionLocal()
                try:
                    row = db.get(Job, job.id)
                    if not row:
                        return
                    if row.status in {
                        "done",
                        "failed",
                        "cancelled",
                        "canceled",
                        "cancelling",
                        "cancel_requested",
                    }:
                        state.cancelled = True
                        return
                    db_progress = float(row.progress or 0)
                    db_updated = row.updated_at
                    db_message = str(row.message or "")
                finally:
                    db.close()

                if not pid or not (in_running or in_pending):
                    # Prompt left the queue — do not spam; history observation
                    # (runs before on_wait) owns finalize. Still bump a light
                    # heartbeat if Adept has gone silent so UI is not frozen.
                    stale_sec = 8.0
                    try:
                        age = (
                            (datetime.utcnow() - db_updated).total_seconds()
                            if db_updated is not None
                            else stale_sec + 1
                        )
                    except Exception:
                        age = stale_sec + 1
                    if age >= stale_sec:
                        self._set_status(
                            job.id,
                            "running",
                            max(db_progress, float(track.get("last_live") or 0)),
                            "MiniMax Route A · waiting for Comfy history / output",
                            stage="sampling" if track.get("had_live_step") else "processing",
                        )
                    return

                stale_sec = 5.0
                try:
                    age = (
                        (datetime.utcnow() - db_updated).total_seconds()
                        if db_updated is not None
                        else stale_sec + 1
                    )
                except Exception:
                    age = stale_sec + 1
                if age < stale_sec and float(track.get("last_live") or 0) <= db_progress + 1e-6:
                    return

                live_p = max(db_progress, float(track.get("last_live") or 0))
                base_msg = str(track.get("last_msg") or db_message or "MiniMax Route A · generating")
                where = "running" if in_running else "queued"
                summary = _route_a_graph_summary(state)
                msg = (
                    f"{base_msg} · Comfy {where} on Route A ({int(elapsed)}s)"
                    + (f" · {summary}" if summary else "")
                )
                track["last_live"] = live_p
                track["last_update"] = time.time()
                self._set_status(
                    job.id,
                    "running",
                    live_p,
                    msg,
                    stage="sampling" if track.get("had_live_step") else "processing",
                )

            # Bound heartbeat so a wedged HTTP/DB path cannot stall finalize.
            runner = threading.Thread(target=_body, daemon=True, name=f"route-a-on-wait-{job.id[:8]}")
            runner.start()
            runner.join(timeout=6.0)
            if runner.is_alive():
                import sys
                print(
                    f"[route-a-on-wait] TIMEOUT job={job.id} — skipping heartbeat this tick",
                    file=sys.stderr,
                    flush=True,
                )

        tap_thread = threading.Thread(target=_tap, daemon=True)
        tap_thread.start()
        try:
            return adapter.poll(state, timeout_sec=timeout_sec, on_wait=_on_wait)
        finally:
            stop.set()
            tap_thread.join(timeout=5)

    async def _imagegen(self, db: Session, job: Job, project: Project) -> None:
        """Execute-only image path: ImageIntent → pinned contract → LocalComfy submit/poll/download → Output Gate."""
        from .image_runtime.contract import resolve_image_workflow
        from .image_runtime.legacy_adapter import normalize_legacy_image_params
        from .image_runtime.output_gate import validate_image_output
        from .image_runtime.provenance import ImageProvenance
        from .image_runtime.local_comfy_adapter import (
            download as local_comfy_download,
            poll as local_comfy_poll,
            submit as local_comfy_submit,
        )
        from .image_runtime.ref_generate_pixels import (
            choose_imagegen_pixel_asset,
            identity_refs_from_intent,
            scene_asset_id_from_intent,
        )

        params = self._job_params(job)
        edit_op = params.get("edit_op") or ("generate" if job.kind == "imagegen" else "edit")
        fal_image_model = str(params.get("falImageModelId") or "").strip()
        if fal_image_model:
            await self._imagegen_fal(db, job, project, params, fal_image_model, edit_op=edit_op)
            return
        kie_image_model = str(params.get("kieImageModelId") or "").strip()
        if kie_image_model:
            await self._imagegen_kie(db, job, project, params, kie_image_model, edit_op=edit_op)
            return

        # Retry path: reuse validated but unregistered output (no silent regeneration)
        pending = params.get("validated_output_path")
        if params.get("status_detail") == "output_valid_but_unregistered" and pending and Path(pending).is_file():
            gate = validate_image_output(pending, expected_aspect=params.get("aspect"), generate_previews=True)
            if not gate.ok:
                raise RuntimeError(f"Cached validated output failed re-validation: {gate.errors}")
            await self._imagegen_commit_asset(
                db, job, project, params, Path(pending), gate, edit_op=edit_op
            )
            return

        pinned = params.get("imageRuntime") if isinstance(params.get("imageRuntime"), dict) else None
        compatibility = params.get("compatibility") if isinstance(params.get("compatibility"), dict) else None
        intent_block = params.get("imageIntent") if isinstance(params.get("imageIntent"), dict) else None

        if intent_block:
            from .image_runtime.intent import ImageIntent

            intent = ImageIntent.model_validate(intent_block)
            compatibility = compatibility or {"legacyInputUsed": False, "normalizedBy": "caller"}
        else:
            intent, compatibility = normalize_legacy_image_params(
                params, project_id=project.id, job_kind=job.kind
            )

        style = params.get("style") or ""
        prompt = (intent.prompt or params.get("prompt") or "").strip()
        from .character_identity.four_view_sheet import (
            assess_four_view_layout,
            apply_job_four_view_prompt,
        )

        ers_purpose = str(getattr(intent, "purpose", "") or params.get("purpose") or "")
        # Full job params only. Never OR imageIntent/metadata -- purpose=character_sheet
        # is shared with CRS law-view singles and would inject four-panel strengthen.
        params, prompt, four_view = apply_job_four_view_prompt(
            params,
            prompt,
            family=str(intent.enginePreference or params.get("model") or ""),
            ers_purpose=ers_purpose,
        )
        intent.prompt = prompt
        if four_view and isinstance(intent.metadata, dict):
            intent.metadata = {**intent.metadata, **(params.get("characterSheetIntent") or {})}
        if style and isinstance(style, str):
            prompt = f"{prompt}, {style}".strip(", ")
        negative = intent.negativePrompt or params.get("negative") or project.negative_prompt
        seed = int(
            intent.seed
            if intent.seed is not None
            else (params.get("seed") if params.get("seed") is not None else (project.seed if project.seed >= 0 else 0))
        )
        width = int(intent.width or params.get("width") or 1024)
        height = int(intent.height or params.get("height") or 1024)
        steps = int(params.get("steps") or settings.imagegen_default_steps)
        cfg = float(params.get("cfg") or settings.imagegen_default_cfg)
        source_asset_id = intent.sourceAssetId or params.get("source_asset_id")
        _ref_ids, _ref_image_id = identity_refs_from_intent(intent, params)
        has_ref_pixels = bool(source_asset_id or _ref_ids or _ref_image_id)
        meta = intent.metadata or {}
        denoise = float(
            params.get("denoise")
            if params.get("denoise") is not None
            else (meta.get("denoise") if meta.get("denoise") is not None else 0.45)
        )
        grow_mask_by = int(params.get("grow_mask_by") or meta.get("grow_mask_by") or 6)
        model = (params.get("model") or intent.enginePreference or "zimage").lower()
        custom_ckpt = params.get("checkpoint") or ""
        reasons: list[str] = []
        pinned_key = str((pinned or {}).get("workflowKey") or "")
        if pinned_key.startswith("zimage."):
            model = "zimage"

        zimage_ready = self._zimage_stack_ready()
        # CDX-076: never silently substitute an explicit/pinned model. When the
        # selected engine is unavailable at execution time the job FAILS with an
        # actionable creator-facing error instead of swapping engines.
        if model == "auto":
            # Legacy unpinned "auto" path — selecting a ready compatible engine is
            # the designed behavior (no model was pinned), but the swap must be
            # visible in the job status, not only history_json.
            model, reasons = self._resolve_ready_still_model("auto")
        use_zimage = model in ("zimage", "z-image", "z_image") or pinned_key.startswith("zimage.")
        if use_zimage and not zimage_ready:
            raise RuntimeError(
                "Z-Image Turbo is selected for this job but the model is not installed — "
                "component zimage_models verification failed (weights missing or not "
                "linked). No alternate model was substituted. Open Source Manager, link "
                "the shared models root, then retry."
            )
        # First-class disclosure for the designed legacy auto fallback: the actual
        # executed model and the reason appear in job.message, not only history_json.
        alternate_note = ""
        if not use_zimage and reasons:
            alternate_note = "; ".join(reasons)
        if use_zimage:
            steps = int(params.get("steps") or settings.zimage_steps)
            cfg = float(params.get("cfg") if params.get("cfg") is not None else settings.zimage_cfg)
            ckpt = settings.zimage_unet
            intent.enginePreference = intent.enginePreference or "zimage"
        else:
            ckpt = self._checkpoint_for_model(model, custom_ckpt)
            if not intent.enginePreference or intent.enginePreference == "zimage":
                intent.enginePreference = "checkpoint"
            # Illustrious XL uses its own smoke-validated quality defaults (steps/cfg)
            # rather than the generic imagegen defaults — anime/stylized rendering.
            if model == "illustrious":
                steps = int(params.get("steps") or settings.imagegen_illustrious_steps)
                cfg = float(
                    params.get("cfg") if params.get("cfg") is not None else settings.imagegen_illustrious_cfg
                )
            if model in ("sd15", "sd1.5", "sd_1.5"):
                steps = int(params.get("steps") or settings.imagegen_sd15_steps)
                cfg = float(
                    params.get("cfg") if params.get("cfg") is not None else settings.imagegen_sd15_cfg
                )
                if not params.get("width") and not getattr(intent, "width", None):
                    width = int(settings.imagegen_sd15_width)
                if not params.get("height") and not getattr(intent, "height", None):
                    height = int(settings.imagegen_sd15_height)

        # Resolve / revalidate pinned contract — never silently switch certified version
        allow_draft = bool(params.get("allow_draft_cert_harness"))
        if pinned and pinned.get("workflowKey"):
            from .image_runtime.certified_registry import get_workflow

            wf_meta = get_workflow(str(pinned["workflowKey"]))
            if wf_meta is None:
                raise RuntimeError(f"Pinned workflow unknown: {pinned.get('workflowKey')}")
            if pinned.get("workflowVersion") and pinned["workflowVersion"] != wf_meta.workflow_version:
                raise RuntimeError(
                    f"Pinned contract version mismatch: job={pinned.get('workflowVersion')} "
                    f"registry={wf_meta.workflow_version} — refusing silent upgrade"
                )
            if pinned.get("certificationRecordId") and wf_meta.certification_record_id:
                if pinned["certificationRecordId"] != wf_meta.certification_record_id and not allow_draft:
                    # Revalidate same key/version; do not move to a different cert record silently
                    if wf_meta.status == "Certified" and pinned.get("fingerprint"):
                        pass  # fingerprint check below is authoritative
            contract = resolve_image_workflow(
                intent.operation,
                engine=intent.enginePreference or "zimage",
                model_family=pinned.get("modelFamily") or intent.enginePreference,
                force_workflow_key=str(pinned["workflowKey"]),
                allow_draft=allow_draft or wf_meta.status != "Certified",
                present_inputs={"prompt": prompt, "reference_image": has_ref_pixels},
            )
            expected_fp = pinned.get("fingerprint") or (pinned.get("fingerprints") or {}).get("graphHash")
        else:
            contract = resolve_image_workflow(
                intent.operation,
                engine=intent.enginePreference or "zimage",
                model_family=intent.enginePreference,
                force_workflow_key=intent.workflowPreference,
                allow_draft=allow_draft,
                present_inputs={"prompt": prompt, "reference_image": has_ref_pixels},
                provider_preference=intent.providerPreference,
            )
            pinned = contract.to_pinned_snapshot()
            expected_fp = pinned.get("fingerprint")

        from .image_runtime.job_model import ImageJobStage

        job.stage = ImageJobStage.PREPARING.value
        message = f"ImageGen · {contract.workflow_key} · {ckpt}"
        if alternate_note:
            message += f" · {alternate_note}"
        job.message = message
        params = {
            **params,
            "imageRuntime": pinned,
            "imageIntent": intent.model_dump(),
            "compatibility": compatibility,
            "model": model,
            "checkpoint": ckpt,
        }

        # Shared LoRA Registry: resolve the selected LoRA against the ACTIVE
        # model family. Refuses disabled / incompatible / missing selections
        # with a clear error — never silently substitutes another LoRA.
        lora_resolved = None
        lora_comfy_name: Optional[str] = None
        lora_strength = 0.8
        lora_sel = params.get("lora")
        if lora_sel is None and isinstance(params.get("loras"), list) and params.get("loras"):
            lora_sel = params["loras"][0]
        if lora_sel is not None:
            from .lora_registry.registry import resolve_comfy_lora_name, resolve_lora_for_generation

            lora_family = str(
                (pinned or {}).get("modelFamily") or intent.enginePreference or model or ""
            ).strip()
            lora_resolved = resolve_lora_for_generation(lora_sel, lora_family, "image")
            lora_comfy_name = resolve_comfy_lora_name(lora_resolved)
            if isinstance(lora_sel, dict) and lora_sel.get("strength") is not None:
                try:
                    lora_strength = float(lora_sel["strength"])
                except (TypeError, ValueError):
                    lora_strength = float(lora_resolved.recommended_strength or 0.8)
            else:
                lora_strength = float(lora_resolved.recommended_strength or 0.8)
            if lora_resolved.strength_min is not None and lora_strength < float(lora_resolved.strength_min):
                lora_strength = float(lora_resolved.strength_min)
            if lora_resolved.strength_max is not None and lora_strength > float(lora_resolved.strength_max):
                lora_strength = float(lora_resolved.strength_max)
            params["lora_provenance"] = {
                "loraId": lora_resolved.id,
                "name": lora_resolved.name,
                "version": lora_resolved.version,
                "modelFamily": lora_resolved.model_family,
                "compatibleModelFamilies": list(lora_resolved.compatible_model_families),
                "strength": lora_strength,
                "baseGenerator": lora_family,
                "sourceTool": params.get("sourceFeature") or "image-generator",
                "filePath": lora_resolved.file_path,
                "category": lora_resolved.category,
                "modality": lora_resolved.modality,
            }
            job.message = f"ImageGen · {contract.workflow_key} · {ckpt} · LoRA {lora_resolved.name}"
        job.params_json = json.dumps(params)
        db.commit()

        prefix = f"studio/{project.id[:8]}_imagegen"
        reference_image = None
        mask_image = None
        # Generate-with-reference (qwen2512.ref / certified *.ref): identity
        # pixels ride referenceImage / first referenceIds. Never copy CRS into
        # sourceAssetId (prior identity FAIL: CRS-as-canvas on zimage.ref_edit).
        _pixel = choose_imagegen_pixel_asset(
            workflow_key=contract.workflow_key,
            source_asset_id=source_asset_id,
            reference_ids=_ref_ids,
            reference_image=_ref_image_id,
        )
        needs_source = (
            source_asset_id
            or _pixel.is_ref_generate
            or contract.workflow_key.endswith("ref_edit")
            or "img2img" in contract.workflow_key
            or "edit" in contract.workflow_key
            or "reference" in contract.workflow_key
            or "inpaint" in contract.workflow_key
            or "outpaint" in contract.workflow_key
            or contract.workflow_key == "image.upscale"
        )
        if needs_source:
            pixel_id = _pixel.load_asset_id if _pixel.is_ref_generate else source_asset_id
            if pixel_id:
                src = self._get_asset(db, pixel_id)
                reference_image = await self._ensure_comfy_image(src)
                if not reference_image:
                    raise RuntimeError("Edit/reference source image missing or unreadable")
            elif _pixel.is_ref_generate or _pixel.missing_required_pixels:
                raise RuntimeError(f"{contract.workflow_key} requires a source/reference image")
            elif "reference_image" in (contract.required_inputs or []) or "inpaint" in contract.workflow_key:
                raise RuntimeError("Reference image required before queue execution")

        # CIS multi-ref: upload environment / SCENE_REFERENCE as second Comfy LoadImage.
        scene_image = None
        scene_asset_id = scene_asset_id_from_intent(intent, params)
        if scene_asset_id and scene_asset_id != (_pixel.load_asset_id or source_asset_id):
            scene_asset = self._get_asset(db, scene_asset_id)
            scene_image = await self._ensure_comfy_image(scene_asset)
            if not scene_image:
                raise RuntimeError(
                    f"{contract.workflow_key} multi-ref requires scene/environment image "
                    f"({scene_asset_id}) uploaded to Comfy"
                )
            params = {
                **params,
                "sceneReferenceAssetId": scene_asset_id,
                "sceneComfyImage": scene_image,
            }
            job.params_json = json.dumps(params)
            db.commit()

        # Mask for inpaint (from ImageEditIntent metadata or params)
        meta = (intent.metadata if hasattr(intent, "metadata") else None) or params.get("imageIntent", {}).get("metadata") or {}
        mask_specs = params.get("masks") or meta.get("masks") or []
        if mask_specs:
            job.stage = ImageJobStage.PREPARING_MASKS.value
            job.message = "Preparing masks"
            db.commit()
            mid = None
            m0 = mask_specs[0] if isinstance(mask_specs[0], dict) else {"maskAssetId": mask_specs[0]}
            mid = m0.get("maskAssetId") or m0.get("assetId") or m0.get("maskId")
            if mid:
                try:
                    from .image_product.masks import get_mask_path

                    mpath = get_mask_path(project.id, str(mid))
                    if mpath and Path(mpath).is_file():
                        mask_image = await comfy.upload_image(Path(mpath))
                except Exception:
                    logger.debug("Mask store miss for %s; trying project asset", mid)
                if not mask_image:
                    mask_asset = self._get_asset(db, str(mid))
                    if mask_asset:
                        mask_image = await self._ensure_comfy_image(mask_asset)
            if not mask_image and "inpaint" in contract.workflow_key:
                raise RuntimeError("Inpaint requires a persisted mask asset")

        # Keep edit_op in job metadata only. Appending "Edit operation:" to the
        # Comfy prompt caused FLUX to burn those words into the pixels.
        build_prompt = prompt
        negative = (negative or "blurry, low quality, watermark").strip()
        if job.kind == "imagegen_edit" or (edit_op and edit_op not in {"generate", "image.generate"}):
            anti_text = "text, letters, watermark, logo, caption, overlay, typography, writing"
            if "typography" not in negative.lower():
                negative = f"{negative}, {anti_text}"

        # Phase 3 safe accel: skip Comfy free_memory when same-family Prop/CD stills
        # are resident. Never changes steps/CFG/size/model.
        try:
            from .image_runtime.residency import maybe_free_memory, note_still_loaded

            family_hint = str(
                (params.get("modelFamilyPreference") or params.get("modelFamily") or "")
                or getattr(contract, "family", "")
                or ""
            ).strip()
            wf_class = "prop_creator" if "prop" in str(job.purpose or params.get("purpose") or "").lower() or str(contract.workflow_key or "").startswith("qwen_edit_2509") else "codirector_still"
            if str(contract.workflow_key or "").startswith("qwen_edit_2509"):
                family_hint = family_hint or "qwen_edit_2509"
                wf_class = "prop_creator" if "prop" in str(params.get("purpose") or job.purpose or "").lower() or "prop_" in str(params.get("tag") or "") else wf_class
                # Prop Advanced primary/angles tag as prop_*
                if str(params.get("tag") or "").startswith("prop_") or str(params.get("purpose") or "") in {"project_prop", "project_prop_angle"}:
                    wf_class = "prop_creator"
            freed = await maybe_free_memory(
                comfy,
                next_family=family_hint or "qwen_edit_2509",
                next_workflow=wf_class,
                unload_after_render=bool(params.get("unloadAfterRender") or params.get("unload_after_render")),
            )
            if freed:
                job.message = "Freed prior models for family change"
                db.commit()
        except Exception:
            logger.debug("residency maybe_free_memory skipped", exc_info=True)

        job.stage = ImageJobStage.LOADING_MODELS.value
        job.message = "Loading models"
        db.commit()

        outpaint = meta.get("output") or params.get("outpaint") or {}

        async def on_progress(p: float, msg: str) -> None:
            job.progress = p
            job.message = msg
            lower = (msg or "").lower()
            if "sampl" in lower or p >= 0.2:
                job.stage = ImageJobStage.SAMPLING.value
            elif "load" in lower:
                job.stage = ImageJobStage.LOADING_MODELS.value
            else:
                job.stage = ImageJobStage.SAMPLING.value
            job.updated_at = datetime.utcnow()
            db.commit()

        submitted = await local_comfy_submit(
            contract=contract,
            settings=settings,
            expected_graph_hash=expected_fp,
            # Certified baseline graphs stay drift-checked; a graph with an
            # explicitly selected LoRA intentionally exercises the declared
            # optional inputs (loraId/loraStrength) and is verified by the
            # LoRA graph tests instead of the baseline fingerprint.
            enforce_certified_fingerprint=(
                contract.status == "Certified" and not allow_draft and lora_resolved is None
            ),
            prompt=build_prompt,
            negative=negative or "blurry, low quality, watermark",
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=prefix,
            reference_image=reference_image,
            source_image=reference_image,
            mask_image=mask_image,
            checkpoint=ckpt if not use_zimage else None,
            denoise=denoise,
            grow_mask_by=grow_mask_by,
            lora_name=lora_comfy_name,
            lora_strength=lora_strength,
            scene_image=scene_image,
            environment_references=[scene_image] if scene_image else None,
            character_references=[reference_image] if reference_image else None,
            outpaint_left=int(outpaint.get("left") or 0),
            outpaint_top=int(outpaint.get("top") or 0),
            outpaint_right=int(outpaint.get("right") or (256 if "outpaint" in contract.workflow_key else 0)),
            outpaint_bottom=int(outpaint.get("bottom") or (256 if "outpaint" in contract.workflow_key else 0)),
        )
        if not submitted.get("ok") or not submitted.get("taskId"):
            raise RuntimeError(submitted.get("message") or "Local Comfy submit failed")
        prompt_id = str(submitted["taskId"])
        job.comfy_prompt_id = prompt_id
        job.stage = ImageJobStage.SAMPLING.value
        ref_hash = None
        if source_asset_id:
            src_asset = self._get_asset(db, source_asset_id)
            if src_asset and src_asset.path and Path(src_asset.path).is_file():
                from .image_runtime.fingerprints import file_content_hash

                ref_hash = file_content_hash(src_asset.path)
        job.history_json = json.dumps(
            {
                "prompt": prompt,
                "negative": negative,
                "seed": seed,
                "model": model,
                "checkpoint": ckpt,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "style": style,
                "edit_op": edit_op,
                "loras": params.get("loras") or [],
                "lora": params.get("lora_provenance"),
                "aspect": params.get("aspect"),
                "reasons": reasons,
                "workflowKey": contract.workflow_key,
                "workflowVersion": contract.workflow_version,
                "certificationRecordId": contract.certification_record_id,
                "referenceHash": ref_hash,
                "compatibility": compatibility,
            }
        )
        db.commit()
        polled = await local_comfy_poll(
            submitted,
            wait_fn=lambda pid: self._wait_comfy(job, pid, on_progress=on_progress),
        )
        files = list(polled.get("files") or [])
        if not files:
            raise RuntimeError(
                "ComfyUI finished but no image output found. Confirm checkpoint exists and ImageGen workflow nodes are available."
            )

        # Phase 4: ref-encode graph-reuse cache instrumentation (Prop Qwen Edit multi-view).
        # Does not change generation knobs; records Comfy execution_cached + encode key.
        try:
            from .image_runtime.ref_encode_cache import (
                applies_to_workflow,
                build_ref_encode_key,
                note_from_comfy_history,
            )

            purpose = str(params.get("purpose") or getattr(job, "purpose", "") or "")
            tag = str(params.get("tag") or "")
            wf_key = str(getattr(contract, "workflow_key", "") or "")
            if applies_to_workflow(wf_key, purpose=purpose, tag=tag):
                ref_path = None
                if source_asset_id:
                    _src = self._get_asset(db, source_asset_id)
                    if _src is not None:
                        ref_path = getattr(_src, "path", None)
                staged_meta = getattr(self, "_last_staged_comfy", None) or {}
                from .workflows.qwen_image_edit_2509 import (
                    configured_clip,
                    configured_unet,
                    configured_vae,
                    unet_weight_dtype,
                )

                enc_key = build_ref_encode_key(
                    ref_asset_id=str(source_asset_id or staged_meta.get("assetId") or ""),
                    ref_path=ref_path,
                    prompt=str(prompt or ""),
                    negative=str(negative or ""),
                    workflow_key=wf_key,
                    unet_name=configured_unet(),
                    clip_name=configured_clip(),
                    vae_name=configured_vae(),
                    weight_dtype=unet_weight_dtype(),
                    width=int(width or 0),
                    height=int(height or 0),
                )
                enc_report = note_from_comfy_history(
                    key=enc_key,
                    history=polled.get("history"),
                    stage_reused=staged_meta.get("reused"),
                    graph=(submitted.get("graph") if isinstance(submitted, dict) else None),
                )
                try:
                    hist = json.loads(job.history_json or "{}")
                except Exception:
                    hist = {}
                if not isinstance(hist, dict):
                    hist = {}
                hist["refEncodeCache"] = enc_report
                hist["refStage"] = staged_meta or None
                job.history_json = json.dumps(hist)
                db.commit()
        except Exception:
            logger.debug("ref_encode_cache instrumentation skipped", exc_info=True)

        # Temporary output inspection (atomic gate)
        tmp_dir = settings.data_dir / "projects" / project.id / "assets" / ".pending"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"imagegen_{edit_op}_{uuid.uuid4().hex[:8]}{Path(files[0]).suffix or '.png'}"
        await local_comfy_download(files[0], tmp_path)

        try:
            from .image_runtime.residency import note_still_loaded

            purpose = str(params.get("purpose") or getattr(job, "purpose", "") or "")
            tag = str(params.get("tag") or "")
            ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
            objective = str((ctx or {}).get("objective") or "")
            fam = str(params.get("modelFamilyPreference") or params.get("modelFamily") or "").strip()
            wf_key = str(contract.workflow_key or "")
            if wf_key.startswith("qwen_edit_2509"):
                fam = fam or "qwen_edit_2509"
            wf_class = "codirector_still"
            if (
                purpose in {"project_prop", "project_prop_angle"}
                or tag.startswith("prop_")
                or objective in {"project_prop_primary_ref_edit", "project_prop_angle", "project_prop"}
            ):
                wf_class = "prop_creator"
            if fam:
                note_still_loaded(fam, wf_class)
                try:
                    hist = json.loads(job.history_json or "{}")
                except Exception:
                    hist = {}
                if not isinstance(hist, dict):
                    hist = {}
                hist["residency"] = {"family": fam, "workflowClass": wf_class, "kept": True}
                # Phase 5: release sequential angle session flight on success.
                try:
                    from .image_runtime.prop_angle_session import (
                        is_prop_advanced_angle_params,
                        note_angle_completed,
                    )
                    if is_prop_advanced_angle_params(params):
                        ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
                        sess_done = note_angle_completed(
                            job.id,
                            angle=str(ctx.get("angle") or ""),
                        )
                        if sess_done:
                            hist["angleSession"] = sess_done
                except Exception:
                    logger.debug("prop angle session complete skipped", exc_info=True)
                job.history_json = json.dumps(hist)
        except Exception:
            logger.debug("note_still_loaded skipped", exc_info=True)

        job.stage = ImageJobStage.VALIDATING.value
        job.message = "Output Gate validation"
        db.commit()
        edit_operation = str(
            (intent.metadata or {}).get("editOperation")
            or params.get("editOperation")
            or edit_op
            or ""
        )
        source_path_for_gate = None
        if source_asset_id:
            src_a = self._get_asset(db, source_asset_id)
            if src_a and src_a.path:
                source_path_for_gate = src_a.path
        mask_path_for_gate = None
        try:
            from .image_product.masks import get_mask_path

            specs = params.get("masks") or (intent.metadata or {}).get("masks") or []
            if specs:
                m0 = specs[0] if isinstance(specs[0], dict) else {"maskAssetId": specs[0]}
                mid = m0.get("maskAssetId") or m0.get("assetId") or m0.get("maskId")
                if mid:
                    mask_path_for_gate = get_mask_path(project.id, str(mid))
                    if not mask_path_for_gate:
                        mask_asset = self._get_asset(db, str(mid))
                        if mask_asset and mask_asset.path:
                            mask_path_for_gate = mask_asset.path
        except Exception:
            pass
        # Region-edit contract: unmasked pixels must remain the source.
        # Apply after download so leak cannot pass through zimage.inpaint or
        # FLUX img2img without changing certified Comfy fingerprints.
        if (
            source_path_for_gate
            and mask_path_for_gate
            and Path(source_path_for_gate).is_file()
            and Path(str(mask_path_for_gate)).is_file()
            and "outpaint" not in contract.workflow_key
            and contract.workflow_key != "image.upscale"
        ):
            from .image_runtime.output_gate import composite_generated_into_source

            feather = 8
            try:
                feather = int(params.get("featherPx") or (intent.metadata or {}).get("featherPx") or 8)
            except Exception:
                feather = 8
            composite_generated_into_source(
                tmp_path,
                source_path_for_gate,
                mask_path_for_gate,
                tmp_path,
                feather_px=max(0, feather),
            )
            params["regionCompositeApplied"] = True
            job.params_json = json.dumps(params)
            db.commit()
        is_edit_op = bool(
            (edit_operation and edit_operation not in {"generate", "image.generate"})
            or "inpaint" in contract.workflow_key
            or "outpaint" in contract.workflow_key
            or contract.workflow_key == "image.upscale"
        )
        if is_edit_op:
            from .image_runtime.output_gate import validate_edit_output

            gate = validate_edit_output(
                tmp_path,
                operation=edit_operation if edit_operation.startswith("image.") else f"image.{edit_operation}",
                source_path=source_path_for_gate,
                mask_path=mask_path_for_gate,
                require_transparency=bool((intent.metadata or {}).get("output", {}).get("transparentBackground")),
                generate_previews=True,
            )
        else:
            gate = validate_image_output(tmp_path, expected_aspect=params.get("aspect"), generate_previews=True)
        if not gate.ok:
            raise RuntimeError(f"Output Gate failed: {'; '.join(gate.errors)}")
        if four_view:
            assessment = assess_four_view_layout(tmp_path)
            params["characterSheetLayout"] = assessment
            params["layoutAssessment"] = assessment
            params["layoutVerified"] = bool(assessment.get("verified"))
            params["layoutNote"] = assessment.get("note")
            params["layoutNoncompliant"] = bool(assessment.get("layoutNoncompliant"))
            params["layout_noncompliant"] = bool(assessment.get("layoutNoncompliant"))
            job.params_json = json.dumps(params)
            db.commit()
        else:
            from .character_identity.visual_sheet import apply_crs_single_figure_gate_to_job

            apply_crs_single_figure_gate_to_job(db, job, params, str(tmp_path))

        job.stage = ImageJobStage.REGISTERING_ASSET.value
        job.message = "Registering asset"
        db.commit()
        try:
            await self._imagegen_commit_asset(
                db,
                job,
                project,
                params,
                tmp_path,
                gate,
                edit_op=edit_op,
                prompt=prompt,
                negative=negative,
                seed=seed,
                ckpt=ckpt,
                model=model,
                reasons=reasons,
                contract_key=contract.workflow_key,
                contract_version=contract.workflow_version,
                ref_hash=ref_hash,
                source_asset_id=source_asset_id,
                intent_id=intent.intentId,
                note=alternate_note,
            )
            job.stage = ImageJobStage.COMPLETED.value
            db.commit()
        except Exception as reg_exc:
            # Validated output exists but registration/provenance failed — not completed
            params = {
                **params,
                "status_detail": "output_valid_but_unregistered",
                "validated_output_path": str(tmp_path),
                "gate": gate.to_dict(),
                "registration_error": str(reg_exc),
            }
            job.params_json = json.dumps(params)
            job.status = "error"
            job.stage = ImageJobStage.FAILED.value
            job.message = f"output_valid_but_unregistered: {reg_exc}"
            db.commit()
            raise RuntimeError(f"output_valid_but_unregistered: {reg_exc}") from reg_exc


    async def _imagegen_kie(
        self,
        db: Session,
        job: Job,
        project: Project,
        params: dict,
        model_id: str,
        *,
        edit_op: str = "generate",
    ) -> None:
        """Dispatch a still-image job through Kie createTask. Never Comfy/Qwen."""
        import asyncio
        import uuid

        from .hosted_providers.adapters.kie_adapter import (
            KIE_FAIL_STATES,
            KIE_POLL_ATTEMPTS,
            KIE_POLL_INTERVAL_SEC,
            build_kie_create_task_body,
            download,
            extract_kie_image_url,
            kie_fail_message,
            kie_image_model_id_for_dock,
            kie_poll_timeout_message,
            resolve_official_kie_image_model,
            normalize_kie_aspect,
            poll,
            submit,
        )
        from .image_runtime.job_model import ImageJobStage
        from .image_runtime.output_gate import validate_image_output

        api_key = get_secret("kie_api_key")
        if not api_key:
            raise RuntimeError(
                "Hosted AI Provider credential not configured. Open Setup → AI Providers "
                "(Kie.ai · WaveSpeed.ai · fal.ai)."
            )
        prompt = str(params.get("prompt") or "").strip()
        if not prompt and isinstance(params.get("imageIntent"), dict):
            prompt = str(params["imageIntent"].get("prompt") or "").strip()
        if not prompt:
            raise RuntimeError("Kie image generate requires a prompt")
        from .character_identity.four_view_sheet import (
            attach_four_view_sheet_intent,
            assess_four_view_layout,
            four_view_sheet_intent,
            is_sheet_tile_request,
            is_single_image_four_view,
        )
        from .hosted_providers.adapters.kie_adapter import strengthen_kie_character_sheet_prompt
        # Bind official BEFORE strengthen_kie_character_sheet_prompt (UnboundLocalError if later).
        official = resolve_official_kie_image_model(model_id, params)
        four_view = is_single_image_four_view(params)
        if str(params.get("purpose") or "") != "environment_reference_sheet" and four_view:
            params = attach_four_view_sheet_intent(params)
            prompt = strengthen_kie_character_sheet_prompt(prompt, model=official)
        elif str(params.get("purpose") or "") == "character_sheet" or is_sheet_tile_request(params):
            params.setdefault("characterSheetIntent", four_view_sheet_intent())
        width = int(params.get("width") or 1024)
        height = int(params.get("height") or 1024)
        aspect = normalize_kie_aspect(params.get("aspect"), width=width, height=height)
        if four_view and aspect in {"9:16", "3:4", "2:3"}:
            aspect = "1:1"
        ref_urls = []
        for key in ("input_urls", "image_urls", "image_input"):
            raw = params.get(key)
            if isinstance(raw, list):
                ref_urls.extend(str(u).strip() for u in raw if str(u).strip().startswith("http"))
        official = resolve_official_kie_image_model(
            model_id, params, image_to_image=bool(ref_urls)
        )
        purpose = str(params.get("purpose") or "")
        continuity = purpose in {"environment_reference_sheet", "atlas_shot"}
        if continuity and ref_urls and "text-to-image" in str(official or ""):
            raise RuntimeError(
                "Refusing text-to-image Kie createTask for Spatial Map / ERS. "
                "Required operation is image-to-image."
            )
        create_body = build_kie_create_task_body(
            model=official,
            prompt=prompt,
            input_urls=ref_urls or None,
            aspect_ratio=aspect,
            quality=str(params.get("quality") or params.get("kieQuality") or "") or None,
        )
        inp = create_body.get("input") if isinstance(create_body.get("input"), dict) else {}
        params["kieCreateTask"] = {
            "model": create_body.get("model"),
            "input_urls": inp.get("input_urls") or inp.get("image_urls") or inp.get("image_input") or [],
            "url": "https://api.kie.ai/api/v1/jobs/createTask",
        }
        job.params_json = json.dumps(params)
        job.stage = ImageJobStage.SAMPLING.value
        job.message = f"Kie.ai · {official}"
        job.comfy_prompt_id = official[:64]
        db.commit()
        submitted = await submit(
            api_key,
            model=official,
            prompt=prompt,
            input_urls=ref_urls or None,
            aspect_ratio=aspect,
            quality=str(params.get("quality") or params.get("kieQuality") or "") or None,
        )
        if not submitted.get("ok") or not submitted.get("taskId"):
            raise RuntimeError(submitted.get("message") or f"Kie createTask failed for {official}")
        task_id = str(submitted["taskId"])
        params["kieCreateTask"] = {
            **dict(params.get("kieCreateTask") or {}),
            "taskId": task_id,
        }
        job.params_json = json.dumps(params)
        db.commit()
        image_url = None
        last_state = ""
        for _ in range(KIE_POLL_ATTEMPTS):
            polled = await poll(api_key, task_id)
            state = str(polled.get("state") or "").lower()
            last_state = state
            image_url = polled.get("imageUrl") or extract_kie_image_url(polled.get("payload"))
            if image_url:
                break
            if state in KIE_FAIL_STATES:
                raise RuntimeError(
                    polled.get("message") or kie_fail_message(polled.get("payload"), task_id, state)
                )
            job.progress = min(0.9, float(job.progress or 0.05) + 0.02)
            job.message = f"Kie.ai · {official} · {state or 'queued'}"
            job.updated_at = datetime.utcnow()
            db.commit()
            await asyncio.sleep(KIE_POLL_INTERVAL_SEC)
        if not image_url:
            raise RuntimeError(kie_poll_timeout_message(task_id, last_state))
        tmp_dir = settings.data_dir / "projects" / project.id / "assets" / ".pending"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"imagegen_kie_{uuid.uuid4().hex[:8]}.png"
        await download(image_url, tmp_path)
        job.stage = ImageJobStage.VALIDATING.value
        job.message = "Output Gate validation"
        db.commit()
        gate = validate_image_output(tmp_path, expected_aspect=params.get("aspect"), generate_previews=True)
        if not gate.ok:
            raise RuntimeError(f"Kie image failed output validation: {gate.errors}")
        if four_view:
            assessment = assess_four_view_layout(tmp_path)
            params["characterSheetLayout"] = assessment
            params["layoutAssessment"] = assessment
            params["layoutVerified"] = bool(assessment.get("verified"))
            params["layoutNote"] = assessment.get("note")
            params["layoutNoncompliant"] = bool(assessment.get("layoutNoncompliant"))
            params["layout_noncompliant"] = bool(assessment.get("layoutNoncompliant"))
            job.params_json = json.dumps(params)
            db.commit()
        else:
            from .character_identity.visual_sheet import apply_crs_single_figure_gate_to_job

            apply_crs_single_figure_gate_to_job(db, job, params, str(tmp_path))
        await self._imagegen_commit_asset(
            db,
            job,
            project,
            params,
            tmp_path,
            gate,
            edit_op=edit_op,
            prompt=prompt,
            seed=int(params.get("seed") if params.get("seed") is not None else 0),
            model=str(official or params.get("hostedModelId") or ""),
            contract_key=f"kie:{official}",
        )

    async def _imagegen_fal(

        self,
        db: Session,
        job: Job,
        project: Project,
        params: dict,
        model_id: str,
        *,
        edit_op: str = "generate",
    ) -> None:
        """Dispatch a still-image job through the existing fal queue client. Not Comfy."""
        from .image_runtime.output_gate import validate_image_output
        from .image_runtime.job_model import ImageJobStage

        api_key = get_secret("fal_api_key")
        if not api_key:
            raise RuntimeError(
                "Hosted AI Provider credential not configured. Open Setup → AI Providers "
                "(Kie.ai · WaveSpeed.ai · fal.ai)."
            )
        prompt = str(params.get("prompt") or "").strip()
        if not prompt and isinstance(params.get("imageIntent"), dict):
            prompt = str(params["imageIntent"].get("prompt") or "").strip()
        if not prompt:
            raise RuntimeError("Fal image generate requires a prompt")
        try:
            from .character_identity.four_view_sheet import is_single_image_four_view
            from .hosted_providers.adapters.fal_adapter import strengthen_fal_character_sheet_prompt
            if is_single_image_four_view(params):
                prompt = strengthen_fal_character_sheet_prompt(prompt, model=model_id)
        except Exception:
            pass
        width = int(params.get("width") or 1024)
        height = int(params.get("height") or 1024)
        seed = int(params.get("seed") if params.get("seed") is not None else 0)
        intent_block = params.get("imageIntent") if isinstance(params.get("imageIntent"), dict) else {}
        creative = intent_block.get("creativeContext") if isinstance(intent_block.get("creativeContext"), dict) else {}
        ref_ids: list[str] = []
        for raw in (
            params.get("source_asset_id"),
            intent_block.get("sourceAssetId"),
            params.get("referenceImage"),
            params.get("reference_image"),
        ):
            sid = str(raw or "").strip()
            if sid and sid not in ref_ids:
                ref_ids.append(sid)
        for raw_list in (
            intent_block.get("referenceIds"),
            params.get("referenceIds"),
            creative.get("reference_image_ids") if isinstance(creative, dict) else None,
        ):
            if not isinstance(raw_list, list):
                continue
            for item in raw_list:
                sid = str(item or "").strip()
                if sid and sid not in ref_ids:
                    ref_ids.append(sid)
        source_urls: list[str] = []
        source_path = None
        for sid in ref_ids:
            src_asset = self._get_asset(db, sid)
            if src_asset and getattr(src_asset, "path", None) and Path(src_asset.path).is_file():
                source_path = Path(src_asset.path)
                source_urls.append(await upload_file_to_fal(source_path, api_key))
                break
        if source_urls:
            model_id = fal_still_edit_model_id(model_id)
        args = build_fal_image_arguments(
            model_id=model_id,
            prompt=prompt,
            width=width,
            height=height,
            seed=seed,
            image_urls=source_urls or None,
        )
        job.stage = ImageJobStage.SAMPLING.value
        job.message = f"fal.ai · {model_id}"
        job.comfy_prompt_id = model_id[:64]
        db.commit()

        async def on_progress(p: float, msg: str) -> None:
            job.progress = min(0.95, max(0.05, p))
            job.message = (msg or f"fal {model_id}")[:4000]
            job.updated_at = datetime.utcnow()
            db.commit()

        async def on_request_id(request_id: str) -> None:
            self._record_fal_request_id(db, job, model_id=model_id, request_id=request_id)

        from .hosted_providers.adapters import fal_adapter as fal_image_adapter

        submitted = await fal_image_adapter.submit(
            api_key,
            model_id=model_id,
            arguments=args,
            on_progress=on_progress,
            on_request_id=on_request_id,
        )
        polled = await fal_image_adapter.poll(submitted)
        image_url = (
            polled.get("imageUrl")
            or extract_image_url(polled.get("result") or submitted.get("result") or {})
        )
        tmp_dir = settings.data_dir / "projects" / project.id / "assets" / ".pending"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"imagegen_fal_{uuid.uuid4().hex[:8]}.png"
        await fal_image_adapter.download(image_url, tmp_path)
        mask_path_for_gate = None
        try:
            from .image_product.masks import get_mask_path

            specs = params.get("masks") or (intent_block.get("metadata") or {}).get("masks") or []
            if specs:
                m0 = specs[0] if isinstance(specs[0], dict) else {"maskAssetId": specs[0]}
                mid = m0.get("maskAssetId") or m0.get("assetId") or m0.get("maskId")
                if mid:
                    mask_path_for_gate = get_mask_path(project.id, str(mid))
        except Exception:
            mask_path_for_gate = None
        if (
            source_path
            and mask_path_for_gate
            and Path(str(mask_path_for_gate)).is_file()
        ):
            from .image_runtime.output_gate import composite_generated_into_source

            feather = 8
            try:
                feather = int(params.get("featherPx") or 8)
            except Exception:
                feather = 8
            composite_generated_into_source(
                tmp_path,
                source_path,
                mask_path_for_gate,
                tmp_path,
                feather_px=max(0, feather),
            )
            params["regionCompositeApplied"] = True
            job.params_json = json.dumps(params)
            db.commit()
        job.stage = ImageJobStage.VALIDATING.value
        job.message = "Output Gate validation"
        db.commit()
        gate = validate_image_output(tmp_path, expected_aspect=params.get("aspect"), generate_previews=True)
        if not gate.ok:
            raise RuntimeError(f"Fal image failed output validation: {gate.errors}")
        four_view_fal = False
        try:
            from .character_identity.four_view_sheet import is_single_image_four_view

            four_view_fal = bool(is_single_image_four_view(params))
        except Exception:
            four_view_fal = False
        if four_view_fal:
            try:
                from .character_identity.four_view_sheet import assess_four_view_layout

                assessment = assess_four_view_layout(tmp_path)
                params["characterSheetLayout"] = assessment
                params["layoutAssessment"] = assessment
                params["layoutVerified"] = bool(assessment.get("verified"))
                params["layoutNote"] = assessment.get("note")
                params["layoutNoncompliant"] = bool(assessment.get("layoutNoncompliant"))
                params["layout_noncompliant"] = bool(assessment.get("layoutNoncompliant"))
                job.params_json = json.dumps(params)
                db.commit()
            except Exception:
                pass
        else:
            from .character_identity.visual_sheet import apply_crs_single_figure_gate_to_job

            apply_crs_single_figure_gate_to_job(db, job, params, str(tmp_path))
        await self._imagegen_commit_asset(
            db,
            job,
            project,
            params,
            tmp_path,
            gate,
            edit_op=edit_op,
            prompt=prompt,
            seed=seed,
            model=str(params.get("hostedModelId") or model_id),
            contract_key=model_id,
        )

    async def _imagegen_commit_asset(
        self,
        db: Session,
        job: Job,
        project: Project,
        params: dict,
        tmp_path: Path,
        gate: Any,
        *,
        edit_op: str = "generate",
        prompt: str = "",
        negative: str = "",
        seed: int = 0,
        ckpt: str = "",
        model: str = "",
        reasons: list | None = None,
        contract_key: str = "",
        contract_version: str = "",
        ref_hash: str | None = None,
        source_asset_id: str | None = None,
        intent_id: str | None = None,
        note: str = "",
    ) -> None:
        from .image_runtime.provenance import ImageProvenance, executed_image_stamp

        dest_dir = settings.data_dir / "projects" / project.id / "assets"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / tmp_path.name.replace(".pending", "")
        if tmp_path.resolve() != dest.resolve():
            shutil.copy2(tmp_path, dest)
        # ERS visual law: dest is the raw GPT PNG. Do not overwrite in place
        # with stamp_saved_cameras_on_ers / assemble_ers_with_movement_strip
        # on environment_reference_sheet / full_sheet success.
        overlay_meta: dict | None = None

        parent_id = source_asset_id or params.get("source_asset_id")
        if job.kind != "imagegen_edit" and not parent_id:
            parent_id = None

        hist = {}
        try:
            hist = json.loads(job.history_json or "{}")
        except Exception:
            hist = {}

        stamp_provider, stamp_runtime, stamp_model = executed_image_stamp(
            params,
            contract_key=contract_key or str(hist.get("workflowKey") or ""),
            model=model,
        )
        provenance = ImageProvenance(
            workflow=contract_key or hist.get("workflowKey"),
            workflowVersion=contract_version or hist.get("workflowVersion"),
            runtime=stamp_runtime,
            provider=stamp_provider,
            references=[ref_hash] if ref_hash else list(params.get("reference_ids") or []),
            prompt=prompt or hist.get("prompt") or "",
            seed=seed or hist.get("seed"),
            parentImages=[parent_id] if parent_id else [],
            validation=gate.to_dict() if hasattr(gate, "to_dict") else dict(gate or {}),
            intentId=intent_id,
            settings={"checkpoint": ckpt, "model": stamp_model or str((params.get("imageRuntime") or {}).get("officialModelId") or params.get("officialModelId") or "") or model, "checksum": getattr(gate, "checksum", None)},
            # LoRA provenance rides the same asset record — no separate history.
            lora=params.get("lora_provenance"),
        )

        intent_metadata = {}
        if isinstance(params.get("imageIntent"), dict):
            intent_metadata = dict(params["imageIntent"].get("metadata") or {})

        creative_ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}

        prompt_meta = {
            **hist,
            "provenance": provenance.to_dict(),
            "gate": gate.to_dict() if hasattr(gate, "to_dict") else gate,
            "checksum": getattr(gate, "checksum", None),
            "spatialMapId": params.get("spatialMapId") or intent_metadata.get("spatialMapId"),
            "spatialMapVersion": params.get("spatialMapVersion") or intent_metadata.get("spatialMapVersion"),
            "spatialCameraId": params.get("spatialCameraId") or intent_metadata.get("spatialCameraId"),
            # Atlas Scene Intent lineage (semantic anchor + source image refs).
            "sceneIntent": creative_ctx.get("sceneIntent"),
            "originalEnvironmentReferenceAssetIds": creative_ctx.get(
                "originalEnvironmentReferenceAssetIds"
            ),
            "cameraOverlay": overlay_meta,
            "sourceFeature": params.get("sourceFeature") or creative_ctx.get("sourceFeature"),
            "libraryVisible": params.get("commitToLibrary", True) is not False
            and creative_ctx.get("commitToLibrary", True) is not False,
            "miniTakeId": params.get("miniTakeId") or creative_ctx.get("miniTakeId"),
            "miniVariation": params.get("miniVariation") or creative_ctx.get("miniVariation"),
        }
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tag=params.get("tag") or "imagegen",
            kind="image",
            filename=dest.name,
            path=str(dest),
            comfy_name="",
            scope="project",
            labels_json=json.dumps(params.get("labels") or []),
            prompt_meta_json=json.dumps(prompt_meta),
            parent_asset_id=parent_id,
        )
        db.add(asset)
        from .asset_graph import add_edge, add_version

        add_version(
            db,
            asset_id=asset.id,
            op=edit_op,
            path=str(dest),
            seed=seed,
            prompt={"prompt": prompt, "negative": negative},
            model=ckpt,
        )
        if parent_id:
            add_edge(db, parent_id, asset.id, "derived_from", {"op": edit_op, "referenceHash": ref_hash})
            add_edge(db, parent_id, asset.id, "reference_of", {"op": edit_op, "referenceHash": ref_hash})

        # Storyboard / spatial lineage
        try:
            from .script_storyboard import StoryboardPanelRow

            panel_id = params.get("panel_id")
            segment_id = params.get("segment_id")
            if panel_id:
                panel = db.get(StoryboardPanelRow, panel_id)
                if panel:
                    panel.asset_id = asset.id
                    panel.status = "complete"
                    panel.script_sync_status = "ok"
                    panel.approval = panel.approval or "draft"
                    if segment_id:
                        add_edge(db, segment_id, panel_id, "storyboard_of", {})
                    add_edge(db, panel_id, asset.id, "derived_from", {"op": "storyboard"})
            if params.get("spatial_scene_id"):
                add_edge(
                    db,
                    params["spatial_scene_id"],
                    asset.id,
                    "spatial_of",
                    {"state_id": params.get("spatial_state_id"), "camera_id": params.get("camera_avatar_id")},
                )
        except Exception:
            pass

        params = {
            **params,
            "output_asset_id": asset.id,
            "model": model,
            "checkpoint": ckpt,
            "startFrameProvider": "comfyui",
            "startFrameModel": model,
            "selectionReasons": reasons or [],
            "status_detail": "completed",
            "validated_output_path": None,
            "gate": gate.to_dict() if hasattr(gate, "to_dict") else gate,
        }
        job.params_json = json.dumps(params)
        job.history_json = json.dumps(prompt_meta)
        try:
            ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
            intent = params.get("imageIntent") if isinstance(params.get("imageIntent"), dict) else {}
            purpose = str(intent.get("purpose") or ctx.get("objective") or params.get("purpose") or "")
            try:
                from .production_events import ACTOR_SYSTEM, record_production_event

                record_production_event(
                    db,
                    project_id=project.id,
                    scene_id=str(params.get("scene_id") or "") or None,
                    event_type=("ers.generation_completed" if purpose == "environment_reference_sheet" else "candidate.generated"),
                    actor=ACTOR_SYSTEM,
                    actor_detail="queue_worker:imagegen_commit",
                    subject_kind="asset",
                    subject_id=asset.id,
                    summary=f"Generated {params.get('tag') or 'image'} (asset {asset.id[:8]})",
                    payload={"assetId": asset.id, "tag": params.get("tag"), "purpose": purpose},

                )
            except Exception:  # noqa: BLE001 - event recording never breaks the operation
                pass
            if purpose == "environment_reference_sheet":
                from .codirector.capabilities.handlers.ers_generate import persist_ers_composite_asset

                persist_ers_composite_asset(
                    db,
                    project.id,
                    sheet_id=str(ctx.get("environmentReferenceSheetId") or ""),
                    asset_id=asset.id,
                    package_id=str(ctx.get("ersPackageId") or ""),
                )
                # ERS source-asset lineage: ERS -> atlas -> original environment
                # reference. Keeps the origin chain queryable after generation.
                try:
                    atlas_id = str(ctx.get("atlasAssetId") or "").strip()
                    if atlas_id and db.get(Asset, atlas_id):
                        add_edge(db, atlas_id, asset.id, "derived_from", {"op": "ers_composite"})
                    grounding = ctx.get("groundingAssetIds")
                    if isinstance(grounding, list):
                        for gid in grounding:
                            gid = str(gid or "").strip()
                            if gid and gid != atlas_id and db.get(Asset, gid):
                                add_edge(db, gid, asset.id, "derived_from", {"op": "ers_grounding"})
                except Exception:
                    logger.exception("ERS lineage edge write failed for job %s", job.id)
                # Semantic gate (advisory): does the sheet depict the intended
                # environment? Post-persist, never blocks, never auto-retries.
                try:
                    from .codirector.vision.ers_gate import (
                        run_ers_semantic_gate,
                        stamp_ers_gate_verdict,
                    )
                    from .spatial_map.scene_intent import (
                        coerce_scene_intent,
                        environment_intent_summary,
                    )

                    gate_intent = coerce_scene_intent(ctx.get("sceneIntent"))
                    gate_summary = environment_intent_summary(gate_intent)
                    source_ref = ""
                    grounding_ids = ctx.get("groundingAssetIds")
                    if isinstance(grounding_ids, list) and grounding_ids:
                        first = self._get_asset(db, str(grounding_ids[0]))
                        if first is not None:
                            from .config import settings as _settings

                            base = str(getattr(_settings, "public_api_base_url", "") or "").rstrip("/")
                            if base:
                                from .project_security.asset_file import canonical_project_asset_file_url

                                rel = canonical_project_asset_file_url(getattr(first, "project_id", None) or project.id, first.id)
                                source_ref = f"{base}{rel}" if rel else ""
                    verdict = await run_ers_semantic_gate(
                        generated_image_path=str(dest),
                        intent_summary=gate_summary,
                        sheet_name=str(ctx.get("environmentName") or ""),
                        source_image_url=source_ref,
                    )
                    db.commit()
                    stamp_ers_gate_verdict(
                        project_id=project.id,
                        sheet_id=str(ctx.get("environmentReferenceSheetId") or ""),
                        verdict=verdict,
                    )
                except Exception:
                    logger.exception("ERS semantic gate failed for job %s", job.id)
            # Scene Creator Mini candidate validation (production continuity
            # gate). Runs for miniTakeId jobs only; idempotent; never blocks
            # completion or the ERS path. A transient VLM error leaves the
            # result VALIDATING (retried by a later hydrate poll).
            mini_take_id = str(params.get("miniTakeId") or ctx.get("miniTakeId") or "").strip()
            if mini_take_id:
                try:
                    from .spatial_map.mini_validation import (
                        run_candidate_validation_for_job,
                    )

                    await run_candidate_validation_for_job(
                        project_id=project.id,
                        take_id=mini_take_id,
                        job_id=str(job.id),
                        asset_path=str(dest),
                    )
                except Exception:
                    logger.exception("Mini candidate validation failed for job %s", job.id)
        except Exception:
            logger.exception("ERS composite persist failed for job %s", job.id)
        db.commit()
        try:
            from .codirector.world_intelligence.scene_review import review_committed_image

            review_committed_image(db, project, job, asset, dest, params)
            db.commit()
        except Exception:
            logger.exception("World intelligence review skipped for job %s", job.id)
        done_message = f"ImageGen ({edit_op}) complete"
        if note:
            # Visible disclosure of a designed legacy auto-fallback (CDX-076):
            # the final status names the actual executed model + reason.
            done_message += f" · {note}"
        self._set_status(job.id, "done", 1.0, done_message, str(dest))

    async def _export(self, db: Session, job: Job, project: Project) -> None:
        scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.index).all()
        assets = db.query(Asset).filter(Asset.project_id == project.id).all()
        cue_placements: list[dict] = []
        try:
            cue_rows = db.execute(
                text(
                    "SELECT id, scene_id, cue_kind, status, asset_id, start_sec, "
                    "duration_sec, metadata_json FROM m29_audio_cues "
                    "WHERE project_id = :project_id ORDER BY start_sec, id"
                ),
                {"project_id": project.id},
            ).mappings()
            for row in cue_rows:
                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    metadata = {}
                cue_placements.append(
                    {
                        "id": row["id"],
                        "scene_id": row["scene_id"],
                        "kind": row["cue_kind"],
                        "status": row["status"],
                        "asset_id": row["asset_id"],
                        "start_sec": row["start_sec"],
                        "duration_sec": row["duration_sec"],
                        "metadata": metadata,
                    }
                )
        except Exception:  # noqa: BLE001
            logger.debug("M2.9 cue table unavailable while exporting %s", project.id, exc_info=True)

        # M3.0d export enrichment: MAGI sequence.json is editorial authority (P0).
        # legacyEditorSnapshot is forensic-only when present.
        editor_sequence: dict = {}
        try:
            from .magi.authority import MAGI_SEQUENCE_AUTHORITY, MAGI_SEQUENCE_STORE
            from .magi.sequence.store import get_sequence
            from .editor_sequences import EditorProjectRow, _row_to_editor

            seq = get_sequence(project.id)
            editor_sequence = {
                "authority": MAGI_SEQUENCE_AUTHORITY,
                "authorityStore": MAGI_SEQUENCE_STORE,
                "sequence": seq,
            }
            ed_row = (
                db.query(EditorProjectRow)
                .filter(EditorProjectRow.project_id == project.id)
                .first()
            )
            if ed_row:
                snap = _row_to_editor(ed_row)
                snap["notMagiAuthority"] = True
                editor_sequence["legacyEditorSnapshot"] = snap
        except Exception:  # noqa: BLE001
            logger.debug("MAGI/editor sequence unavailable while exporting %s", project.id, exc_info=True)

        generation_jobs: list[dict] = []
        try:
            job_rows = (
                db.query(Job)
                .filter(Job.project_id == project.id)
                .order_by(Job.created_at.desc())
                .limit(50)
                .all()
            )
            for jr in job_rows:
                generation_jobs.append(
                    {
                        "jobId": jr.id,
                        "kind": jr.kind,
                        "status": jr.status,
                        "sceneId": getattr(jr, "scene_id", None),
                        "outputPath": jr.output_path,
                        "comfyPromptId": getattr(jr, "comfy_prompt_id", None),
                        "errorMessage": jr.message if jr.status in ("failed", "cancelled") else None,
                    }
                )
        except Exception:  # noqa: BLE001
            logger.debug("Job provenance unavailable while exporting %s", project.id, exc_info=True)

        payload = {
            "id": project.id,
            "name": project.name,
            "global_prompt": project.global_prompt,
            "engine_default": project.engine_default,
            "width": project.width,
            "height": project.height,
            "fps": project.fps,
            "preset": project.preset,
            "spatial_map_json": json.loads(project.spatial_map_json or "{}"),
            "scenes": [
                {
                    "id": s.id,
                    "index": s.index,
                    "name": s.name,
                    "engine": s.engine,
                    "prompt": s.prompt,
                    "duration_sec": s.duration_sec,
                    "output_path": s.output_path,
                    "lipsync_output_path": s.lipsync_output_path,
                    # B18: approved Director timeline must survive pack re-import.
                    "director_json": getattr(s, "director_json", "") or "",
                    "shot_id": getattr(s, "id", None),
                }
                for s in scenes
            ],
            "assets": [{"id": a.id, "tag": a.tag, "kind": a.kind, "filename": a.filename} for a in assets],
            "cue_placements": cue_placements,
            "editor_sequence_json": editor_sequence,
            "generation_jobs": generation_jobs,
            "export_contract": "m30d-canonical-timeline-v1",
            "sync_model": "director_plan_transformed_into_editor_sequence",
        }
        # M3.0F: language metadata (UTF-8 preserved; display formatting is client-side).
        try:
            settings_obj = json.loads(getattr(project, "settings_json", "") or "{}")
            payload["language"] = settings_obj.get("language") or {
                "canonicalLanguage": "en",
                "exportLocale": "en",
            }
        except Exception:
            payload["language"] = {"canonicalLanguage": "en", "exportLocale": "en"}
        out_dir = settings.data_dir / "exports" / f"{project.name.replace(' ', '_')}_{project.id[:8]}"
        videos = []
        for s in scenes:
            for p in (s.lipsync_output_path, s.output_path):
                if p and Path(p).exists():
                    videos.append(Path(p))
                    break
        # also latest timeline job output
        if job.output_path and Path(job.output_path).exists():
            videos.append(Path(job.output_path))
        asset_paths = [Path(a.path) for a in assets if Path(a.path).exists()]
        export_pack(payload, asset_paths, videos, out_dir)
        self._set_status(job.id, "done", 1.0, "Export pack ready", str(out_dir))


job_queue = JobQueue()
