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
from typing import Optional

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
    build_zimage_ref_workflow,
    customize_angle_prompts,
    lipsync_available_hint,
    views_for_tool,
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
NON_TERMINAL_STATES: tuple[str, ...] = ("queued", "running")

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

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

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
                self._set_status(job_id, "failed", 0, f"{exc}\n{traceback.format_exc()[-1500:]}")
            finally:
                self._q.task_done()

    def _set_status(self, job_id: str, status: str, progress: float, message: str, output: str | None = None) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            job.status = status
            job.progress = progress
            job.message = message[:4000]
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

            if job.kind == "render_scene":
                await self._render_scene(db, job, project)
            elif job.kind == "render_timeline":
                await self._render_timeline(db, job, project)
            elif job.kind == "lipsync":
                await self._lipsync(db, job, project)
            elif job.kind == "export":
                await self._export(db, job, project)
            elif job.kind in ("character_sheet", "multi_angle"):
                await self._image_tool(db, job, project)
            elif job.kind == "dual_lipsync":
                await self._dual_lipsync(db, job, project)
            elif job.kind == "txt2vid":
                await self._txt2vid(db, job, project)
            elif job.kind in ("imagegen", "imagegen_edit"):
                await self._imagegen(db, job, project)
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
                return await self._build_and_run_fal_scene(
                    db, project, scene, job, positive, negative, seed, plan
                )

            length = self._frames_for_scene(scene, plan_fps)
            length, frame_clamped = clamp_frames(length, plan)
            steps = plan.steps
            width, height = plan_width, plan_height

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
            use_ingredients = scene.engine != "wan" and wants_ingredients_ic_lora(
                params, getattr(scene, "director_json", "") or ""
            )

            if use_ingredients:
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

            if scene.engine == "wan":
                wf = build_wan_flf_workflow(
                    high_noise=settings.wan_high_noise,
                    low_noise=settings.wan_low_noise,
                    vae_name=settings.wan_vae,
                    text_encoder=settings.wan_text_encoder,
                    positive=positive,
                    negative=negative,
                    width=width,
                    height=height,
                    length=length,
                    fps=plan_fps,
                    seed=seed,
                    start_image=start,
                    end_image=end or middle,
                    steps_high=steps // 2 or 2,
                    steps_low=steps // 2 or 2,
                    filename_prefix=prefix,
                )
            else:
                wf = build_ltx_scene_workflow(
                    checkpoint=settings.ltx_checkpoint,
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

            async def on_progress(p: float, msg: str) -> None:
                job.progress = p
                job.message = msg
                job.updated_at = datetime.utcnow()
                db.commit()

            try:
                prompt_id = await comfy.queue_prompt(wf)
            except Exception as first_err:
                # LTX Director fallback to simple I2V if we have a start frame
                if scene.engine == "ltx" and start:
                    job.message = f"Director submit failed, falling back to simple I2V: {first_err}"
                    db.commit()
                    wf = build_ltx_simple_i2v(
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
                    )
                    prompt_id = await comfy.queue_prompt(wf)
                else:
                    raise

            job.comfy_prompt_id = prompt_id
            db.commit()
            history = await comfy.wait_for_prompt(prompt_id, on_progress=on_progress)
            files = comfy.find_output_files(history)
            if not files:
                raise RuntimeError("ComfyUI finished but no output video was found")

            dest_dir = settings.data_dir / "projects" / project.id / "renders"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"scene_{scene.index}_{uuid.uuid4().hex[:8]}{files[0].suffix}"
            shutil.copy2(files[0], dest)

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

        prompt_id = await comfy.queue_prompt(compiled["workflow"])
        job.comfy_prompt_id = prompt_id
        provenance["comfy_prompt_id"] = prompt_id
        job.history_json = json.dumps(provenance)
        job.params_json = json.dumps({**params, "ic_lora_provenance": provenance})
        db.commit()

        history = await comfy.wait_for_prompt(prompt_id, on_progress=on_progress)
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
                "fal.ai API key not configured. Open Advanced → fal.ai API key, paste your key from "
                "https://fal.ai/dashboard/keys, then retry."
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

    async def _render_timeline(self, db: Session, job: Job, project: Project) -> None:
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
            job.message = f"Rendering scene {i + 1}/{len(scenes)} ({scene.engine})"
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

    async def _lipsync_scene(self, db: Session, project: Project, scene: Scene) -> Path | None:
        if not scene.output_path or not Path(scene.output_path).exists():
            raise RuntimeError("Scene has no rendered video for lip sync")
        audio_asset = self._get_asset(db, scene.lipsync_audio_asset_id or scene.audio_asset_id)
        if not audio_asset:
            raise RuntimeError("No lip sync audio asset")

        # Validate LatentSync node exists
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{settings.comfy_url}/object_info/LatentSyncNode")
                if r.status_code != 200:
                    raise RuntimeError(lipsync_available_hint())
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        video_name = await comfy.upload_file_copy(Path(scene.output_path), filename=Path(scene.output_path).name)
        audio_name = await self._ensure_comfy_file(audio_asset)
        plan = resolve_render_plan(project)
        wf = build_latentsync_workflow(
            video_path=str(settings.comfy_input_dir / video_name.replace("/", "\\")),
            audio_path=str(settings.comfy_input_dir / (audio_name or "").replace("/", "\\")),
            filename_prefix=f"studio/{project.id[:8]}_lipsync_{scene.index}",
            custom_width=plan.lipsync_size,
            custom_height=plan.lipsync_size,
            inference_steps=plan.lipsync_steps,
        )
        # Prefer relative paths for VHS loaders
        wf["1"]["inputs"]["video"] = str(settings.comfy_input_dir / video_name.replace("/", "\\"))
        wf["2"]["inputs"]["audio_file"] = audio_name

        prompt_id = await comfy.queue_prompt(wf)
        history = await comfy.wait_for_prompt(prompt_id)
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError("Lip sync produced no output")
        dest = Path(scene.output_path).with_name(Path(scene.output_path).stem + "_lipsync.mp4")
        shutil.copy2(files[0], dest)
        scene.lipsync_output_path = str(dest)
        db.commit()
        return dest

    async def _lipsync(self, db: Session, job: Job, project: Project) -> None:
        scene = db.get(Scene, job.scene_id) if job.scene_id else None
        if not scene:
            raise RuntimeError("Scene not found")
        path = await self._lipsync_scene(db, project, scene)
        self._set_status(job.id, "done", 1.0, "Lip sync complete", str(path) if path else None)

    async def _image_tool(self, db: Session, job: Job, project: Project) -> None:
        try:
            payload = json.loads(job.message or "{}")
        except Exception:
            payload = {}
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
            wf = build_zimage_ref_workflow(
                unet_name=settings.zimage_unet,
                clip_name=settings.zimage_clip,
                vae_name=settings.zimage_vae,
                clip_vision_name=settings.zimage_clip_vision,
                reference_image=ref,
                prompt=prompt,
                width=width,
                height=height,
                seed=view_seed + i,
                steps=settings.zimage_steps,
                cfg=settings.zimage_cfg,
                filename_prefix=prefix,
            )
            prompt_id = await comfy.queue_prompt(wf)
            job.comfy_prompt_id = prompt_id
            db.commit()
            history = await comfy.wait_for_prompt(prompt_id)
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

            prompt_id = await comfy.queue_prompt(wf)
            job.comfy_prompt_id = prompt_id
            db.commit()
            history = await comfy.wait_for_prompt(prompt_id)
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

    async def _txt2vid(self, db: Session, job: Job, project: Project) -> None:
        """Text-to-video: prefer fal T2V; local I2V engines warn and fail clearly."""
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

        from .engine_recommend import resolve_engine_id

        # Temporary scene-like object for resolve
        class _S:
            pass

        s = _S()
        s.engine = engine
        s.prompt = prompt
        s.duration_sec = duration
        s.start_asset_id = None
        resolved = resolve_engine_id(engine, project, s) if engine == "auto" else engine

        if not is_fal_engine(resolved) and resolved in ("ltx", "wan"):
            raise RuntimeError(
                f"Local engine '{resolved}' is image-to-video and needs a start frame. "
                "Use ImageGen or 1 Frame first, or choose a fal T2V-capable engine / Auto."
            )

        # Force fal path for T2V when local
        if not is_fal_engine(resolved):
            resolved = "fal_seedance"

        api_key = get_secret("fal_api_key")
        if not api_key:
            raise RuntimeError(
                "fal.ai API key not configured. Open Project Settings → Integrations or Advanced → fal.ai API key."
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
        model_id, args = build_fal_arguments(
            engine=resolved,
            prompt=fal_prompt,
            negative=fal_negative,
            image_url=None,
            end_image_url=None,
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
                "negative": negative,
                "seed": seed,
                "model": model_id,
                "engine": resolved,
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

    async def _imagegen(self, db: Session, job: Job, project: Project) -> None:
        params = self._job_params(job)
        prompt = (params.get("prompt") or "").strip()
        negative = params.get("negative") or project.negative_prompt
        model = (params.get("model") or "auto").lower()
        custom_ckpt = params.get("checkpoint") or ""
        seed = int(params.get("seed") if params.get("seed") is not None else (project.seed if project.seed >= 0 else 0))
        width = int(params.get("width") or 1024)
        height = int(params.get("height") or 1024)
        steps = int(params.get("steps") or settings.imagegen_default_steps)
        cfg = float(params.get("cfg") or settings.imagegen_default_cfg)
        style = params.get("style") or ""
        edit_op = params.get("edit_op") or ("generate" if job.kind == "imagegen" else "edit")
        source_asset_id = params.get("source_asset_id")
        denoise = float(params.get("denoise") or 0.45)
        if style:
            prompt = f"{prompt}, {style}".strip(", ")

        # Soft Auto reasons — prefer catalogued Z-Image when present; fail honestly otherwise.
        reasons = []
        zimage_ready = self._zimage_stack_ready()
        if model == "auto":
            if zimage_ready:
                reasons.append(
                    "Auto selected catalogued Z-Image Turbo (UNET + Qwen + AE); "
                    "FLUX/HiDream/SD3.5 remain opt-in when installed"
                )
                model = "zimage"
            else:
                raise RuntimeError(
                    "ImageGen auto has no catalogued still-image provider. "
                    "Install/verify zimage_models (Z-Image Turbo stack) in Source Manager, then retry."
                )
        use_zimage = model in ("zimage", "z-image", "z_image")
        if use_zimage and not zimage_ready:
            raise RuntimeError(
                "Z-Image Turbo weights are not verified on disk (component zimage_models). "
                "Open Source Manager, link the shared models root, then retry."
            )
        if use_zimage:
            steps = int(params.get("steps") or settings.zimage_steps)
            cfg = float(params.get("cfg") if params.get("cfg") is not None else settings.zimage_cfg)
            ckpt = settings.zimage_unet
        else:
            ckpt = self._checkpoint_for_model(model, custom_ckpt)
        job.stage = "preparing"
        job.message = f"ImageGen · {model} · {ckpt}" + (f" · {'; '.join(reasons)}" if reasons else "")
        db.commit()

        from .imagegen_workflows import build_img2img_edit_stub, build_txt2img_workflow
        from .workflows.image_tools import build_zimage_ref_workflow, build_zimage_txt2img_workflow

        prefix = f"studio/{project.id[:8]}_imagegen"
        if job.kind == "imagegen_edit" and source_asset_id:
            src = self._get_asset(db, source_asset_id)
            image_name = await self._ensure_comfy_image(src)
            if not image_name:
                raise RuntimeError("Edit source image missing")
            edit_prompt = f"{prompt}. Edit operation: {edit_op}".strip()
            if use_zimage:
                wf = build_zimage_ref_workflow(
                    unet_name=settings.zimage_unet,
                    clip_name=settings.zimage_clip,
                    vae_name=settings.zimage_vae,
                    clip_vision_name=settings.zimage_clip_vision,
                    reference_image=image_name,
                    prompt=edit_prompt,
                    negative=negative or "blurry, low quality",
                    width=width,
                    height=height,
                    seed=seed,
                    steps=steps,
                    cfg=cfg,
                    filename_prefix=prefix,
                )
            else:
                wf = build_img2img_edit_stub(
                    checkpoint=ckpt,
                    positive=edit_prompt,
                    negative=negative,
                    image_name=image_name,
                    denoise=denoise,
                    seed=seed,
                    steps=steps,
                    filename_prefix=prefix,
                )
        elif use_zimage:
            wf = build_zimage_txt2img_workflow(
                unet_name=settings.zimage_unet,
                clip_name=settings.zimage_clip,
                vae_name=settings.zimage_vae,
                positive=prompt,
                negative=negative or "blurry, low quality, watermark",
                width=width,
                height=height,
                seed=seed,
                steps=steps,
                cfg=cfg,
                filename_prefix=prefix,
            )
        else:
            wf = build_txt2img_workflow(
                checkpoint=ckpt,
                positive=prompt,
                negative=negative,
                width=width,
                height=height,
                seed=seed,
                steps=steps,
                cfg=cfg,
                filename_prefix=prefix,
            )

        async def on_progress(p: float, msg: str) -> None:
            job.progress = p
            job.message = msg
            job.stage = "processing"
            job.updated_at = datetime.utcnow()
            db.commit()

        prompt_id = await comfy.queue_prompt(wf)
        job.comfy_prompt_id = prompt_id
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
            }
        )
        db.commit()
        history = await comfy.wait_for_prompt(prompt_id, on_progress=on_progress)
        files = comfy.find_output_files(history)
        if not files:
            raise RuntimeError(
                "ComfyUI finished but no image output found. Confirm checkpoint exists and ImageGen workflow nodes are available."
            )

        dest_dir = settings.data_dir / "projects" / project.id / "assets"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"imagegen_{edit_op}_{uuid.uuid4().hex[:8]}{Path(files[0]).suffix or '.png'}"
        shutil.copy2(files[0], dest)

        parent_id = source_asset_id if job.kind == "imagegen_edit" else None
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
            prompt_meta_json=job.history_json or "{}",
            parent_asset_id=parent_id,
        )
        db.add(asset)
        try:
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
                add_edge(db, parent_id, asset.id, "derived_from", {"op": edit_op})
        except Exception:
            pass
        db.commit()
        job.params_json = json.dumps({**params, "output_asset_id": asset.id})
        db.commit()
        # Link storyboard / spatial lineage when requested
        try:
            from .asset_graph import add_edge
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
                    db.commit()
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
            db.commit()
        except Exception:
            pass
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
