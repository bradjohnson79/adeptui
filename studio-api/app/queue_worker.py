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
from .fal_catalog import build_fal_arguments, is_fal_engine
from .fal_client import download_url, extract_video_url, run_fal_model, upload_file_to_fal
from .secrets_store import get_secret
from .vram_profiles import clamp_frames, resolve_render_plan
from .workflows import (
    build_latentsync_workflow,
    build_ltx_scene_workflow,
    build_ltx_simple_i2v,
    build_wan_flf_workflow,
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
from .workflows.ltx_ingredients_compiler import (
    compile_ingredients_workflow,
    wants_ingredients_ic_lora,
)
from .references.models import (
    ERR_REFERENCE_UPLOAD_FAILED,
    INGREDIENTS_FILENAME,
    IcLoraError,
    ReferenceError,
)

logger = logging.getLogger(__name__)

#: Job states that mean "an earlier process was still carrying this in memory".
#: The queue is an in-process asyncio queue, so any row left in one of these at
#: startup belongs to a process that is gone and will never touch it again.
NON_TERMINAL_STATES: tuple[str, ...] = ("queued", "running", "cancelling", "cancel_requested")

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

_DEFAULT_RECOVERY_MAX_AGE_HOURS = 24.0


def _recovery_max_age_hours() -> float:
    """How old a queued job may be and still be resumed automatically on startup."""
    raw = os.environ.get("STUDIO_JOB_RECOVERY_MAX_AGE_HOURS", "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_RECOVERY_MAX_AGE_HOURS
    return value if value > 0 else _DEFAULT_RECOVERY_MAX_AGE_HOURS


class JobQueue:
    def __init__(self) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._cancel: set[str] = set()
        self._active_prompt: dict[str, str] = {}
        self._heavy_local_active: Optional[str] = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancel

    def bind_prompt(self, job_id: str, prompt_id: str) -> None:
        self._active_prompt[job_id] = prompt_id

    def unbind_prompt(self, job_id: str) -> None:
        self._active_prompt.pop(job_id, None)

    async def _wait_comfy(
        self,
        job: Job,
        prompt_id: str,
        *,
        on_progress: Any = None,
    ) -> dict:
        """Wait for Comfy with cancel observation + prompt binding."""
        self.bind_prompt(job.id, prompt_id)
        job.comfy_prompt_id = prompt_id

        async def _progress(p: float, msg: str, stage: str | None = None) -> None:
            # Never register successful progress once cancel was requested.
            if job.id in self._cancel:
                return
            job.progress = p
            job.message = msg
            if stage:
                job.stage = stage
            job.updated_at = datetime.utcnow()
            db = SessionLocal()
            try:
                row = db.get(Job, job.id)
                if row:
                    if row.status in ("cancelling", "cancel_requested", "cancelled", "cancel_failed_runtime_active"):
                        return
                    row.progress = p
                    row.message = (msg or "")[:4000]
                    if stage:
                        row.stage = stage
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

        return await comfy.wait_for_prompt(
            prompt_id,
            on_progress=_progress,
            cancel_check=lambda: job.id in self._cancel,
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
                if job.status == "queued" and created >= cutoff:
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
        await self._q.put(job_id)

    def cancel(self, job_id: str) -> None:
        self._cancel.add(job_id)

    async def cancel_and_halt(self, job_id: str) -> dict:
        """Verified deep cancel: cancelling → confirm Comfy stopped → cancelled.

        Transitions to ``cancelled`` only after the prompt is confirmed absent from
        Comfy running and pending queues (or there was no prompt yet). If the
        prompt remains active after timeout → ``cancel_failed_runtime_active`` with
        ``COMFY_CANCEL_NOT_CONFIRMED``. Idempotent for repeat cancel requests.
        """
        from .comfy_client import comfy

        self._cancel.add(job_id)
        prompt_id = self._active_prompt.get(job_id)
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return {"ok": False, "error": "job_not_found"}
            # Idempotent: already terminal cancel states
            if job.status == "cancelled" and job.stage == "cancelled":
                return {"ok": True, "alreadyCancelled": True, "promptId": job.comfy_prompt_id}
            if not prompt_id and job.comfy_prompt_id:
                prompt_id = job.comfy_prompt_id
            job.status = "cancelling"
            job.stage = "cancelling"
            job.message = "Cancel requested — waiting for ComfyUI to confirm prompt stopped"
            job.updated_at = datetime.utcnow()
            from .video_runtime.job_model import merge_video_runtime_history

            job.history_json = merge_video_runtime_history(
                job.history_json,
                {
                    "stage": "cancelling",
                    "cancelRequestedAt": datetime.utcnow().isoformat(),
                    "promptId": prompt_id,
                },
            )
            db.commit()
        finally:
            db.close()

        halt = await comfy.halt_prompt(prompt_id, confirm_timeout_sec=20.0)
        confirmed = bool(halt.get("confirmedStopped"))
        if confirmed:
            self._set_status(
                job_id,
                "cancelled",
                0,
                "Cancelled — ComfyUI confirmed prompt is no longer active or queued",
                stage="cancelled",
                video_runtime_patch={
                    "stage": "cancelled",
                    "failureClass": "user_cancellation",
                    "computeConsumed": bool(prompt_id),
                    "halt": halt,
                    "vramFullyReleased": False,
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
            }

        self._set_status(
            job_id,
            "cancel_failed_runtime_active",
            0,
            (
                "Cancel failed — interrupt/delete sent but ComfyUI prompt remained "
                "active or queued (COMFY_CANCEL_NOT_CONFIRMED). Manual Comfy restart may be required."
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
            },
        )
        return {
            "ok": False,
            "status": "cancel_failed_runtime_active",
            "errorCode": "COMFY_CANCEL_NOT_CONFIRMED",
            "promptId": prompt_id,
            "halt": halt,
            "confirmedStopped": False,
        }

    async def _loop(self) -> None:
        while True:
            job_id = await self._q.get()
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
                    payload = failure_payload(fc, message=str(exc)[:500], compute_consumed=True)
                    summary = str(exc).strip().splitlines()[0][:280] or "Job failed"
                    detail = traceback.format_exc()[-1500:]
                    self._set_status(
                        job_id,
                        "failed",
                        0,
                        f"{summary}\n\n--- details ---\n{detail}",
                        video_runtime_patch={
                            "stage": "failed",
                            "failure": payload,
                        },
                    )
            finally:
                self.unbind_prompt(job_id)
                if self._heavy_local_active == job_id:
                    self._heavy_local_active = None
                self._q.task_done()

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
            job.status = status
            job.progress = progress
            job.message = message[:4000]
            if video_runtime_patch:
                from .video_runtime.job_model import merge_video_runtime_history

                job.history_json = merge_video_runtime_history(job.history_json, video_runtime_patch)
            if stage:
                job.stage = stage
            # Infer coarse stage from message when not already set by callers
            low = (message or "").lower()
            if "prepar" in low or "load" in low:
                job.stage = "preparing"
            elif "assembl" in low or "stitch" in low:
                job.stage = "assembling"
            elif "lipsync" in low or "mix" in low or "post" in low:
                job.stage = "post"
            elif status == "running":
                job.stage = job.stage or "processing"
            elif status == "done":
                job.stage = "complete"
            elif status == "failed":
                job.stage = "failed"
            elif status == "cancelled":
                job.stage = "cancelled"
            job.updated_at = datetime.utcnow()
            if output:
                job.output_path = output
            db.commit()
        finally:
            db.close()

    async def _run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            project = db.get(Project, job.project_id)
            if not project:
                raise RuntimeError("Project missing")
            job.status = "running"
            job.progress = 0.05
            job.message = "Starting"
            job.updated_at = datetime.utcnow()
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

    async def _ensure_comfy_image(self, asset: Asset | None) -> str | None:
        if not asset:
            return None
        if asset.comfy_name:
            return asset.comfy_name
        path = Path(asset.path)
        if not path.exists():
            return None
        name = await comfy.upload_image(path, filename=asset.filename)
        # persist
        db = SessionLocal()
        try:
            a = db.get(Asset, asset.id)
            if a:
                a.comfy_name = name
                db.commit()
        finally:
            db.close()
        return name

    async def _ensure_comfy_file(self, asset: Asset | None) -> str | None:
        if not asset:
            return None
        if asset.comfy_name and asset.kind in ("audio", "video"):
            return asset.comfy_name
        path = Path(asset.path)
        if not path.exists():
            return None
        name = await comfy.upload_file_copy(path, filename=asset.filename)
        db = SessionLocal()
        try:
            a = db.get(Asset, asset.id)
            if a:
                a.comfy_name = name
                db.commit()
        finally:
            db.close()
        return name

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
            from .director_timeline import camera_prompt_hint, parse_director_timeline

            tl = parse_director_timeline(
                getattr(scene, "director_json", "") or "",
                fallback_duration=scene.duration_sec,
                fallback_prompt=scene.prompt,
            )
            cam = camera_prompt_hint(tl.camera_clips or [])
            if cam:
                combined = f"{combined} {cam}".strip()
            # Resolve #motion tags from profile library
            import re

            from .profiles import ProfileItem

            tags = re.findall(r"#([A-Za-z0-9_-]+)", " ".join(s.text for s in tl.prompt_segments))
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
        frames = max(9, int(round(scene.duration_sec * fps)))
        # LTX prefers length patterns; keep odd-ish near 8n+1
        return max(9, ((frames - 1) // 8) * 8 + 1)

    async def _build_and_run_scene(self, db: Session, project: Project, scene: Scene, job: Job) -> Path:
        positive = self._scene_prompt(project, scene, db)
        negative = project.negative_prompt
        seed = scene.seed if scene.seed >= 0 else project.seed
        plan = resolve_render_plan(project)
        from .aspect_fps import resolve_scene_dims, resolve_scene_fps

        sw, sh = resolve_scene_dims(project, scene)
        sfps = resolve_scene_fps(project, scene)
        if plan.vram_gb < 32:
            plan_width, plan_height = min(sw, plan.width), min(sh, plan.height)
            plan_fps = min(sfps, plan.fps)
        else:
            plan_width, plan_height, plan_fps = sw, sh, sfps

        from .engine_recommend import resolve_engine_id

        resolved_engine = resolve_engine_id(scene.engine, project, scene)
        original_engine = scene.engine
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

            length = self._frames_for_scene(scene, plan_fps)
            length, frame_clamped = clamp_frames(length, plan)
            # WAN 14B dual-UNET is extremely heavy; keep length in a playable cert band
            # (wan_builder also snaps to 4n+1) so jobs finish and still show camera motion.
            if str(resolved_engine).lower() == "wan" and length > 33:
                length = 33
                frame_clamped = True
            steps = plan.steps
            width, height = plan_width, plan_height
            if str(resolved_engine).lower() == "wan":
                width = min(width, 832)
                height = min(height, 480)

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
                    frames = max(9, int(round(float(bd) * plan_fps)))
                    length = max(9, ((frames - 1) // 8) * 8 + 1)
                    length, frame_clamped = clamp_frames(length, plan)
                bseed = params.get("seed")
                if isinstance(bseed, int) and bseed >= 0:
                    seed = bseed

            if plan.notes or frame_clamped:
                bits = [
                    b
                    for b in [
                        plan.notes,
                        f"Frames capped to {length} for {plan.label} VRAM" if frame_clamped else "",
                    ]
                    if b
                ]
                if bits:
                    job.message = " · ".join(bits)
                    db.commit()

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
            # TIMELINE_BATCH_LTX: override start frame with the per-batch
            # startImageAssetId when present (BATCH_ISOLATION).
            if is_timeline_batch:
                b_start_id = params.get("startImageAssetId")
                if b_start_id:
                    b_start_asset = self._get_asset(db, b_start_id)
                    if b_start_asset:
                        start = await self._ensure_comfy_image(b_start_asset)
            use_ingredients = scene.engine != "wan" and wants_ingredients_ic_lora(
                params, getattr(scene, "director_json", "") or ""
            )

            # M41 4.1B: WorkflowResolver selects leaf workflow — QueueWorker executes only.
            from .video_runtime.workflow_resolver import resolve_from_scene_params
            from .video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
            from .video_runtime.job_model import merge_video_runtime_history

            intent = "shot_render" if job.kind == "render_shot" else "scene_render"
            contract = resolve_from_scene_params(
                engine=scene.engine,
                start_asset_id=scene.start_asset_id,
                middle_asset_id=scene.middle_asset_id,
                end_asset_id=scene.end_asset_id,
                audio_asset_id=scene.audio_asset_id,
                wants_ingredients=use_ingredients,
                paid_fal_approved=bool(params.get("paidFallbackApproved")),
                intent=intent,
            )
            for d in contract.disclosures:
                job.message = d
            job.history_json = merge_video_runtime_history(
                job.history_json,
                {"workflowContract": contract.to_dict()},
            )
            db.commit()

            if use_ingredients and contract.leaf_workflow_key == "ltx.ingredients_ic_lora":
                dest, _provenance = await self._build_and_run_ingredients_scene(
                    db,
                    project,
                    scene,
                    job,
                    positive=positive,
                    negative=negative,
                    seed=seed,
                    width=width,
                    height=height,
                    length=length,
                    fps=plan_fps,
                    steps=steps,
                    prefix=prefix,
                    params=params,
                )
                scene.output_path = str(dest)
                db.commit()
                return dest

            if contract.leaf_workflow_key.startswith("wan."):
                from .setup.paths import default_models_root
                from .workflows.wan_encoder_contract import (
                    WanEncoderContractError,
                    assert_wan_text_encoder_contract,
                )

                try:
                    roots = [default_models_root(), Path(settings.data_dir) / "models"]
                    assert_wan_text_encoder_contract(
                        settings.wan_text_encoder,
                        search_roots=roots,
                        require_file_probe=True,
                    )
                except WanEncoderContractError as exc:
                    raise RuntimeError(f"WAN encoder contract failed (before UNET): {exc}") from exc
                try:
                    await comfy.free_memory(unload_models=True, free_memory=True)
                except Exception:
                    logging.getLogger(__name__).warning("Comfy free_memory before WAN failed", exc_info=True)

            if contract.leaf_workflow_key in {"ltx.simple_i2v", "ltx.scene"} and not start:
                raise RuntimeError(
                    "Local LTX requires a start frame (I2V only). True local T2V is deferred."
                )

            async def on_progress(p: float, msg: str) -> None:
                job.progress = p
                job.message = msg
                job.updated_at = datetime.utcnow()
                db.commit()

            async def _run_graph(wf: dict, workflow_key: str):
                wf = prepare_executable_graph(contract, wf, enforce_certified_fingerprint=True)
                prompt_id = await comfy.queue_prompt(wf, workflow_key=workflow_key)
                job.comfy_prompt_id = prompt_id
                self.bind_prompt(job.id, prompt_id)
                db.commit()
                return await self._wait_comfy(job, prompt_id, on_progress=on_progress)

            # WAN three-frame: dual-segment FLF + stitch (middle never ignored).
            if contract.leaf_workflow_key == "wan.three_frame":
                if not (start and middle and end):
                    raise RuntimeError("wan.three_frame requires start, middle, and end frames")
                job.message = "WAN three-frame: segment start→middle"
                db.commit()
                wf_a = build_leaf_graph(
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
                    steps=steps,
                    filename_prefix=prefix,
                    wan_segment="start_mid",
                )
                hist_a = await _run_graph(wf_a, "wan.three_frame")
                files_a = comfy.find_output_files(hist_a)
                if not files_a:
                    raise RuntimeError("WAN three-frame segment start_mid produced no output")
                job.message = "WAN three-frame: segment middle→end"
                db.commit()
                wf_b = build_leaf_graph(
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
                    steps=steps,
                    filename_prefix=prefix,
                    wan_segment="mid_end",
                )
                hist_b = await _run_graph(wf_b, "wan.three_frame")
                files_b = comfy.find_output_files(hist_b)
                if not files_b:
                    raise RuntimeError("WAN three-frame segment mid_end produced no output")
                dest_dir = settings.data_dir / "projects" / project.id / "renders"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"scene_{scene.index}_{uuid.uuid4().hex[:8]}.mp4"
                stitch_videos([files_a[0], files_b[0]], dest, fps=plan_fps)
                history = hist_b
                files = [dest]
            else:
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
                )
                workflow_key = contract.leaf_workflow_key

                def _simple_i2v_workflow() -> dict:
                    from .workflows.ltx_builder import build_ltx_simple_i2v

                    return build_ltx_simple_i2v(
                        checkpoint=settings.ltx_checkpoint,
                        positive=positive,
                        negative=negative,
                        width=width,
                        height=height,
                        length=length,
                        fps=plan_fps,
                        seed=seed,
                        start_image=start,
                        steps=steps,
                        filename_prefix=prefix,
                        text_encoder=settings.ltx_text_encoder,
                    )

                try:
                    history = await _run_graph(wf, workflow_key)
                except Exception as first_err:
                    if workflow_key == "ltx.scene" and start:
                        job.message = f"Director submit failed, falling back to simple I2V: {first_err}"
                        db.commit()
                        contract.leaf_workflow_key = "ltx.simple_i2v"
                        wf = _simple_i2v_workflow()
                        history = await _run_graph(wf, "ltx.simple_i2v")
                    else:
                        raise

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
            # TIMELINE_BATCH_LTX: for Timeline batches, register the output as
            # a project Asset and record its id in job params so the LTX
            # adapter's collect_result can surface outputAssetIds to the W46
            # watcher, which calls apply_shared_completion to bind the result
            # to the correct BatchBlock. Do NOT leave scene.output_path as the
            # authoritative batch output (that would race batch-level binding).
            if is_timeline_batch:
                try:
                    out_asset = Asset(
                        id=str(uuid4()),
                        project_id=project.id,
                        kind="video",
                        filename=dest.name,
                        path=str(dest),
                        tag=f"batch_{params.get('batchBlockId', 'tl')[:8]}",
                    )
                    db.add(out_asset)
                    db.commit()
                    params = {**params, "outputAssetIds": [out_asset.id]}
                    job.params_json = json.dumps(params)
                    db.commit()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Timeline batch output asset registration failed", exc_info=True
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
                    "engine": scene.engine,
                    "comfyPromptId": job.comfy_prompt_id,
                    "outputPath": str(dest),
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
                provenance = local_first_provenance(
                    start_frame_provider="comfyui" if scene.start_asset_id else None,
                    start_frame_model=str((params.get("startFrameModel") or params.get("still_model") or "")),
                    video_provider="comfyui",
                    video_model="ltx-2.3" if scene.engine == "ltx" else scene.engine,
                    paid_provider_used=False,
                    current_job_fal_submission_count=0,
                )
                job.params_json = json.dumps(
                    {
                        **params,
                        "localFirstProvenance": provenance,
                        "ltxStartFrameBinding": bind,
                        "executionClass": "REAL_LOCAL_EXECUTION",
                    }
                )
            except Exception:
                pass
            db.commit()
            return dest
        finally:
            scene.engine = original_engine

    def _ingredients_refs_from_params(
        self, db: Session, project: Project, scene: Scene, params: dict
    ) -> dict:
        from .references import store as ref_store

        sheet_id = params.get("sheet_id") or params.get("reference_sheet_id")
        director = {}
        raw = getattr(scene, "director_json", "") or ""
        if isinstance(raw, str) and raw.strip():
            try:
                director = json.loads(raw)
            except Exception:
                director = {}
        ref = director.get("reference") or director.get("ic_lora") or {}
        if isinstance(ref, dict):
            sheet_id = sheet_id or ref.get("sheet_id")
        sheet = ref_store.get_sheet(project.id, sheet_id) if sheet_id else None
        strength_preset = (
            params.get("strength_preset")
            or (ref.get("strength_preset") if isinstance(ref, dict) else None)
            or (sheet or {}).get("strength_preset")
            or "balanced"
        )
        source_ids = list(
            params.get("source_asset_ids")
            or [
                r.get("asset_id")
                for r in ((sheet or {}).get("source_references") or [])
                if r.get("asset_id")
            ]
            or (sheet or {}).get("source_asset_ids")
            or []
        )
        return {
            "sheet": sheet,
            "sheet_id": sheet_id,
            "strength_preset": strength_preset,
            "strength": params.get("strength")
            or params.get("strength_value")
            or (ref.get("strength") if isinstance(ref, dict) else None)
            or (ref.get("strength_value") if isinstance(ref, dict) else None),
            "source_asset_ids": source_ids,
            "reference_prompt": params.get("reference_prompt")
            or (sheet or {}).get("reference_prompt")
            or "",
            "image_path": (sheet or {}).get("composite_path") or (sheet or {}).get("image_path"),
            "video_path": (sheet or {}).get("static_video_path") or (sheet or {}).get("video_path"),
            "image_asset_id": (sheet or {}).get("composite_asset_id")
            or (sheet or {}).get("image_asset_id"),
            "video_asset_id": (sheet or {}).get("static_video_asset_id")
            or (sheet or {}).get("video_asset_id"),
        }

    async def _build_and_run_ingredients_scene(
        self,
        db: Session,
        project: Project,
        scene: Scene,
        job: Job,
        *,
        positive: str,
        negative: str,
        seed: int,
        width: int,
        height: int,
        length: int,
        fps: int,
        steps: int,
        prefix: str,
        params: dict,
    ) -> tuple[Path, dict]:
        refs = self._ingredients_refs_from_params(db, project, scene, params)
        image_path = Path(refs["image_path"]) if refs.get("image_path") else None
        video_path = Path(refs["video_path"]) if refs.get("video_path") else None
        if (not image_path or not image_path.exists()) and refs.get("image_asset_id"):
            asset = self._get_asset(db, refs["image_asset_id"])
            if asset and Path(asset.path).exists():
                image_path = Path(asset.path)
        if (not video_path or not video_path.exists()) and refs.get("video_asset_id"):
            asset = self._get_asset(db, refs["video_asset_id"])
            if asset and Path(asset.path).exists():
                video_path = Path(asset.path)
        if not image_path or not image_path.exists():
            raise RuntimeError("Ingredients IC-LoRA requires a built reference sheet image")

        job.stage = "preparing"
        job.message = "Uploading Ingredients reference sheet to ComfyUI"
        db.commit()
        try:
            comfy_image = await comfy.upload_image(image_path, filename=image_path.name)
            comfy_video = None
            if video_path and video_path.exists():
                comfy_video = await comfy.upload_file_copy(video_path, filename=video_path.name)
        except Exception as exc:
            job.status = "failed"
            job.stage = "failed"
            job.message = f"{ERR_REFERENCE_UPLOAD_FAILED}: {exc}"[:4000]
            job.history_json = json.dumps(
                {"error_code": ERR_REFERENCE_UPLOAD_FAILED, "error": str(exc)[:500]}
            )
            db.commit()
            raise RuntimeError(f"{ERR_REFERENCE_UPLOAD_FAILED}: {exc}") from exc

        object_info = await comfy.get_object_info()
        try:
            compiled = compile_ingredients_workflow(
                object_info=object_info,
                checkpoint=settings.ltx_checkpoint,
                positive=positive,
                negative=negative,
                width=width,
                height=height,
                length=length,
                fps=fps,
                seed=seed,
                reference_image=comfy_image,
                reference_video=comfy_video,
                lora_name=INGREDIENTS_FILENAME,
                strength_preset=refs.get("strength_preset") or "balanced",
                strength=refs.get("strength"),
                steps=steps,
                filename_prefix=prefix,
                reference_prompt=refs.get("reference_prompt") or "",
                source_labels=refs.get("source_asset_ids") or [],
                text_encoder=settings.ltx_text_encoder,
            )
        except (IcLoraError, ReferenceError) as exc:
            job.status = "failed"
            job.stage = "failed"
            job.message = f"{exc.code}: {exc.message}"[:4000]
            job.history_json = json.dumps(
                exc.as_dict() if hasattr(exc, "as_dict") else {"code": exc.code, "message": exc.message}
            )
            db.commit()
            raise

        provenance = {
            **compiled["provenance"],
            "sheet_id": refs.get("sheet_id"),
            "source_asset_ids": refs.get("source_asset_ids") or [],
            "sanitized_debug": compiled.get("sanitized_debug"),
        }
        job.params_json = json.dumps({**params, "ic_lora_provenance": provenance})
        job.history_json = json.dumps(provenance)
        job.message = f"Ingredients IC-LoRA · {compiled['strategy']}"
        db.commit()

        async def on_progress(p: float, msg: str) -> None:
            job.progress = p
            job.message = msg
            job.updated_at = datetime.utcnow()
            db.commit()

        prompt_id = await comfy.queue_prompt(
            compiled["workflow"], workflow_key="ltx.ingredients_ic_lora"
        )
        provenance["comfy_prompt_id"] = prompt_id
        job.history_json = json.dumps(provenance)
        job.params_json = json.dumps({**params, "ic_lora_provenance": provenance})
        db.commit()

        history = await self._wait_comfy(job, prompt_id, on_progress=on_progress)
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError("ComfyUI finished but no Ingredients IC-LoRA output was found")

        dest_dir = settings.data_dir / "projects" / project.id / "renders"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"scene_{scene.index}_ingredients_{uuid.uuid4().hex[:8]}{files[0].suffix}"
        shutil.copy2(files[0], dest)

        # Lineage: output → sheet / source refs
        try:
            from .asset_graph import add_edge

            out_asset = Asset(
                id=str(uuid.uuid4()),
                project_id=project.id,
                tag="ingredients_render",
                kind="video",
                filename=dest.name,
                path=str(dest),
                comfy_name="",
                scope="project",
                prompt_meta_json=json.dumps(provenance),
            )
            db.add(out_asset)
            db.flush()
            sheet_asset_id = refs.get("image_asset_id")
            if sheet_asset_id:
                add_edge(
                    db,
                    out_asset.id,
                    sheet_asset_id,
                    "used_in_director",
                    {"sheet_id": refs.get("sheet_id"), "kind": "ic_lora_sheet"},
                )
            for src_id in refs.get("source_asset_ids") or []:
                add_edge(
                    db,
                    out_asset.id,
                    src_id,
                    "used_in_director",
                    {"sheet_id": refs.get("sheet_id"), "kind": "ic_lora_source"},
                )
            provenance["output_asset_id"] = out_asset.id
            job.params_json = json.dumps({**params, "ic_lora_provenance": provenance, "output_asset_id": out_asset.id})
            job.history_json = json.dumps(provenance)
            db.commit()
        except Exception:
            db.commit()

        return dest, provenance

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

            # Continuity: if WAN and no start frame, use previous scene last frame hint via previous output
            if scene.engine == "wan" and not scene.start_asset_id and outputs:
                # extract last frame would be ideal; for now rely on end/start assets
                pass

            path = await self._build_and_run_scene(db, project, scene, job)
            outputs.append(path)

            if scene.lipsync_enabled:
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
        self._set_status(job.id, "done", 1.0, "Timeline render complete", str(final))

    async def _editor_mix(self, db: Session, job: Job, project: Project) -> None:
        """M3.2g Phase 6: mux Editor audio stems onto primary video; register Asset."""
        from .editor_mix import (
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
            for root in roots:
                if not root or not Path(root).exists():
                    continue
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

        if contract.leaf_workflow_key.startswith("wan."):
            length = min(length, 33)
            width = min(width, 832)
            height = min(height, 480)

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
        """Text-to-video under local-first policy.

        Local LTX/WAN are I2V and never silently fall through to fal. Without a start
        frame, raise LOCAL_START_FRAME_REQUIRED (preferred: generate local still).
        fal.ai runs only when paidFallbackApproved is true.
        """
        params = self._job_params(job)
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

        spatial_bundle = None
        spatial_summary: dict[str, Any] | None = None
        spatial_start_camera_id = params.get("spatialStartCameraId") or params.get("spatialCameraId")
        spatial_end_camera_id = params.get("spatialEndCameraId")
        try:
            if params.get("spatialMapId"):
                from .spatial_map.reference_bundle import (
                    preferred_reference_assets,
                    summarize_reference_bundle,
                )
                from .spatial_map.service import build_reference_bundle as build_spatial_reference_bundle

                spatial_bundle = build_spatial_reference_bundle(
                    db,
                    project.id,
                    str(params["spatialMapId"]),
                    target="video",
                    camera_id=str(spatial_start_camera_id) if spatial_start_camera_id else None,
                )
                spatial_summary = summarize_reference_bundle(
                    spatial_bundle,
                    start_camera_id=str(spatial_start_camera_id) if spatial_start_camera_id else None,
                    end_camera_id=str(spatial_end_camera_id) if spatial_end_camera_id else None,
                )
                params["spatialReferenceBundle"] = spatial_bundle.model_dump()
                params["spatialMapVersion"] = params.get("spatialMapVersion") or spatial_bundle.documentVersion
                params["spatialCameraId"] = params.get("spatialCameraId") or (
                    spatial_bundle.primaryCamera.id if spatial_bundle.primaryCamera else None
                )
                params["spatialReferenceAssetIds"] = [
                    item.assetId for item in preferred_reference_assets(spatial_bundle, limit=4)
                ]
            elif isinstance(params.get("spatialReferenceBundle"), dict):
                from .spatial_map.reference_bundle import summarize_reference_bundle
                from .spatial_map.schemas import SpatialReferenceBundle

                spatial_bundle = SpatialReferenceBundle.model_validate(params["spatialReferenceBundle"])
                spatial_summary = summarize_reference_bundle(
                    spatial_bundle,
                    start_camera_id=str(spatial_start_camera_id) if spatial_start_camera_id else None,
                    end_camera_id=str(spatial_end_camera_id) if spatial_end_camera_id else None,
                )
        except Exception:
            spatial_bundle = None
            spatial_summary = None

        if spatial_summary and spatial_summary.get("summary"):
            prompt = f"{prompt}. {str(spatial_summary['summary']).strip()}".strip()

        from .engine_recommend import resolve_engine_id
        from .local_first import (
            assert_fal_allowed,
            local_start_frame_blocker,
            paid_fallback_approved,
            provider_prefers_local,
        )

        # Temporary scene-like object for resolve
        class _S:
            pass

        s = _S()
        s.engine = engine
        s.prompt = prompt
        s.duration_sec = duration
        s.start_asset_id = params.get("start_asset_id") or None
        resolved = resolve_engine_id(engine, project, s) if engine == "auto" else engine
        job.params_json = json.dumps(params)
        db.commit()

        # Explicit fal engine still requires paid approval (no silent submit).
        if is_fal_engine(engine) or (engine != "auto" and is_fal_engine(resolved)):
            resolved = engine if is_fal_engine(engine) else resolved
            assert_fal_allowed(params, engine=resolved)
        elif provider_prefers_local(params) or engine in ("auto", "ltx", "wan") or resolved in ("ltx", "wan"):
            # LOCAL-16: never force fal_seedance. Prefer local start-frame generation.
            preferred = resolved if resolved in ("ltx", "wan") else "ltx"
            if not paid_fallback_approved(params):
                raise RuntimeError(json.dumps(local_start_frame_blocker(preferred_engine=preferred)))
            # User approved paid fal after local start-frame path was declined.
            resolved = "fal_seedance"
            assert_fal_allowed(params, engine=resolved)
        elif not is_fal_engine(resolved):
            raise RuntimeError(json.dumps(local_start_frame_blocker(preferred_engine="ltx")))

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
        image_url = None
        end_image_url = None
        spatial_reference_assets = []
        if spatial_bundle is not None:
            try:
                from .spatial_map.reference_bundle import preferred_reference_assets

                spatial_reference_assets = preferred_reference_assets(spatial_bundle, limit=4)
            except Exception:
                spatial_reference_assets = []
        if spatial_reference_assets:
            first_ref = spatial_reference_assets[0]
            if first_ref.path and Path(first_ref.path).is_file():
                await on_progress(0.08, f"Uploading spatial references to fal.ai ({resolved})")
                image_url = await upload_file_to_fal(Path(first_ref.path), api_key)
            if len(spatial_reference_assets) > 1 and spatial_end_camera_id:
                second_ref = spatial_reference_assets[1]
                if second_ref.path and Path(second_ref.path).is_file():
                    end_image_url = await upload_file_to_fal(Path(second_ref.path), api_key)
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
                "aspect": aspect,
                "width": width,
                "height": height,
                "duration_sec": duration,
                "style": style,
                "spatialMapId": params.get("spatialMapId"),
                "spatialMapVersion": params.get("spatialMapVersion"),
                "spatialCameraId": params.get("spatialCameraId"),
                "spatialStartCameraId": spatial_start_camera_id,
                "spatialEndCameraId": spatial_end_camera_id,
                "spatialSummary": spatial_summary,
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

    async def _imagegen(self, db: Session, job: Job, project: Project) -> None:
        """Execute-only image path: ImageIntent → pinned contract → workflow_execute → Output Gate."""
        from .image_runtime.contract import resolve_image_workflow
        from .image_runtime.legacy_adapter import normalize_legacy_image_params
        from .image_runtime.output_gate import validate_image_output
        from .image_runtime.provenance import ImageProvenance
        from .image_runtime.workflow_execute import (
            build_leaf_graph,
            legacy_comfy_workflow_key,
            prepare_executable_graph,
        )

        params = self._job_params(job)
        edit_op = params.get("edit_op") or ("generate" if job.kind == "imagegen" else "edit")

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
        denoise = float(params.get("denoise") or 0.45)
        model = (params.get("model") or intent.enginePreference or "zimage").lower()
        custom_ckpt = params.get("checkpoint") or ""
        reasons: list[str] = []

        zimage_ready = self._zimage_stack_ready()
        if model == "auto":
            model, reasons = self._resolve_ready_still_model("auto")
        use_zimage = model in ("zimage", "z-image", "z_image")
        if use_zimage and not zimage_ready:
            alt, alt_reasons = self._resolve_ready_still_model("auto")
            if alt not in ("zimage", "z-image", "z_image"):
                model = alt
                use_zimage = False
                reasons.extend(alt_reasons)
                intent.enginePreference = "checkpoint" if not str(alt).startswith("flux") else "flux"
            else:
                raise RuntimeError(
                    "Z-Image Turbo weights are not verified on disk (component zimage_models). "
                    "Open Source Manager, link the shared models root, then retry."
                )
        if use_zimage:
            steps = int(params.get("steps") or settings.zimage_steps)
            cfg = float(params.get("cfg") if params.get("cfg") is not None else settings.zimage_cfg)
            ckpt = settings.zimage_unet
            intent.enginePreference = intent.enginePreference or "zimage"
        else:
            ckpt = self._checkpoint_for_model(model, custom_ckpt)
            if not intent.enginePreference or intent.enginePreference == "zimage":
                intent.enginePreference = "checkpoint"

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
                present_inputs={"prompt": prompt, "reference_image": bool(source_asset_id)},
            )
            expected_fp = pinned.get("fingerprint") or (pinned.get("fingerprints") or {}).get("graphHash")
        else:
            contract = resolve_image_workflow(
                intent.operation,
                engine=intent.enginePreference or "zimage",
                model_family=intent.enginePreference,
                force_workflow_key=intent.workflowPreference,
                allow_draft=allow_draft,
                present_inputs={"prompt": prompt, "reference_image": bool(source_asset_id)},
                provider_preference=intent.providerPreference,
            )
            pinned = contract.to_pinned_snapshot()
            expected_fp = pinned.get("fingerprint")

        from .image_runtime.job_model import ImageJobStage

        job.stage = ImageJobStage.PREPARING.value
        job.message = f"ImageGen · {contract.workflow_key} · {ckpt}"
        params = {
            **params,
            "imageRuntime": pinned,
            "imageIntent": intent.model_dump(),
            "compatibility": compatibility,
            "model": model,
            "checkpoint": ckpt,
        }
        job.params_json = json.dumps(params)
        db.commit()

        prefix = f"studio/{project.id[:8]}_imagegen"
        reference_image = None
        mask_image = None
        needs_source = (
            source_asset_id
            or contract.workflow_key.endswith("ref_edit")
            or "img2img" in contract.workflow_key
            or "edit" in contract.workflow_key
            or "reference" in contract.workflow_key
            or "inpaint" in contract.workflow_key
            or "outpaint" in contract.workflow_key
            or contract.workflow_key == "image.upscale"
        )
        if needs_source:
            if source_asset_id:
                src = self._get_asset(db, source_asset_id)
                reference_image = await self._ensure_comfy_image(src)
                if not reference_image:
                    raise RuntimeError("Edit/reference source image missing or unreadable")
            elif "reference_image" in (contract.required_inputs or []) or "inpaint" in contract.workflow_key:
                raise RuntimeError("Reference image required before queue execution")

        # Mask for inpaint (from ImageEditIntent metadata or params)
        meta = (intent.metadata if hasattr(intent, "metadata") else None) or params.get("imageIntent", {}).get("metadata") or {}
        mask_specs = params.get("masks") or meta.get("masks") or []
        if mask_specs and ("inpaint" in contract.workflow_key or edit_op in {"inpaint", "object_remove", "object_replace"}):
            job.stage = ImageJobStage.PREPARING_MASKS.value
            job.message = "Preparing masks"
            db.commit()
            mid = None
            m0 = mask_specs[0] if isinstance(mask_specs[0], dict) else {"maskAssetId": mask_specs[0]}
            mid = m0.get("maskAssetId") or m0.get("assetId")
            if mid:
                try:
                    from .image_product.masks import get_mask_path

                    mpath = get_mask_path(project.id, str(mid))
                    if mpath and Path(mpath).is_file():
                        mask_image = await comfy.upload_image(Path(mpath))
                except Exception:
                    mask_asset = self._get_asset(db, str(mid))
                    if mask_asset:
                        mask_image = await self._ensure_comfy_image(mask_asset)
            if not mask_image and "inpaint" in contract.workflow_key:
                raise RuntimeError("Inpaint requires a persisted mask asset")

        build_prompt = prompt
        if job.kind == "imagegen_edit" and edit_op:
            build_prompt = f"{prompt}. Edit operation: {edit_op}".strip()

        job.stage = ImageJobStage.LOADING_MODELS.value
        job.message = "Loading models"
        db.commit()

        outpaint = meta.get("output") or params.get("outpaint") or {}
        wf = build_leaf_graph(
            contract,
            settings=settings,
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
            outpaint_left=int(outpaint.get("left") or 0),
            outpaint_top=int(outpaint.get("top") or 0),
            outpaint_right=int(outpaint.get("right") or (256 if "outpaint" in contract.workflow_key else 0)),
            outpaint_bottom=int(outpaint.get("bottom") or (256 if "outpaint" in contract.workflow_key else 0)),
        )
        wf = prepare_executable_graph(
            contract,
            wf,
            expected_graph_hash=expected_fp,
            enforce_certified_fingerprint=contract.status == "Certified" and not allow_draft,
        )

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

        prompt_id = await comfy.queue_prompt(
            wf, workflow_key=legacy_comfy_workflow_key(contract.workflow_key)
        )
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
        history = await self._wait_comfy(job, prompt_id, on_progress=on_progress)
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError(
                "ComfyUI finished but no image output found. Confirm checkpoint exists and ImageGen workflow nodes are available."
            )

        # Temporary output inspection (atomic gate)
        tmp_dir = settings.data_dir / "projects" / project.id / "assets" / ".pending"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"imagegen_{edit_op}_{uuid.uuid4().hex[:8]}{Path(files[0]).suffix or '.png'}"
        shutil.copy2(files[0], tmp_path)

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
        is_edit_op = bool(
            (edit_operation and edit_operation not in {"generate", "image.generate"})
            or "inpaint" in contract.workflow_key
            or "outpaint" in contract.workflow_key
            or contract.workflow_key == "image.upscale"
        )
        if is_edit_op:
            from .image_runtime.output_gate import validate_edit_output

            mask_path_for_gate = None
            try:
                from .image_product.masks import get_mask_path

                specs = params.get("masks") or (intent.metadata or {}).get("masks") or []
                if specs:
                    m0 = specs[0] if isinstance(specs[0], dict) else {"maskAssetId": specs[0]}
                    mid = m0.get("maskAssetId") or m0.get("assetId")
                    if mid:
                        mask_path_for_gate = get_mask_path(project.id, str(mid))
            except Exception:
                pass
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
    ) -> None:
        from .image_runtime.provenance import ImageProvenance

        dest_dir = settings.data_dir / "projects" / project.id / "assets"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / tmp_path.name.replace(".pending", "")
        if tmp_path.resolve() != dest.resolve():
            shutil.copy2(tmp_path, dest)

        parent_id = source_asset_id or params.get("source_asset_id")
        if job.kind != "imagegen_edit" and not parent_id:
            parent_id = None

        hist = {}
        try:
            hist = json.loads(job.history_json or "{}")
        except Exception:
            hist = {}

        provenance = ImageProvenance(
            workflow=contract_key or hist.get("workflowKey"),
            workflowVersion=contract_version or hist.get("workflowVersion"),
            runtime="comfy",
            provider="local",
            references=[ref_hash] if ref_hash else list(params.get("reference_ids") or []),
            prompt=prompt or hist.get("prompt") or "",
            seed=seed or hist.get("seed"),
            parentImages=[parent_id] if parent_id else [],
            validation=gate.to_dict() if hasattr(gate, "to_dict") else dict(gate or {}),
            intentId=intent_id,
            settings={"checkpoint": ckpt, "model": model, "checksum": getattr(gate, "checksum", None)},
        )

        intent_metadata = {}
        if isinstance(params.get("imageIntent"), dict):
            intent_metadata = dict(params["imageIntent"].get("metadata") or {})

        prompt_meta = {
            **hist,
            "provenance": provenance.to_dict(),
            "gate": gate.to_dict() if hasattr(gate, "to_dict") else gate,
            "checksum": getattr(gate, "checksum", None),
            "spatialMapId": params.get("spatialMapId") or intent_metadata.get("spatialMapId"),
            "spatialMapVersion": params.get("spatialMapVersion") or intent_metadata.get("spatialMapVersion"),
            "spatialCameraId": params.get("spatialCameraId") or intent_metadata.get("spatialCameraId"),
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
        db.commit()
        self._set_status(job.id, "done", 1.0, f"ImageGen ({edit_op}) complete", str(dest))

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

        # M3.0d export enrichment: editor sequence + job provenance (best-effort).
        editor_sequence: dict = {}
        try:
            from .editor_sequences import EditorProjectRow, _row_to_editor

            ed_row = (
                db.query(EditorProjectRow)
                .filter(EditorProjectRow.project_id == project.id)
                .first()
            )
            if ed_row:
                editor_sequence = _row_to_editor(ed_row)
        except Exception:  # noqa: BLE001
            logger.debug("Editor sequence unavailable while exporting %s", project.id, exc_info=True)

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
