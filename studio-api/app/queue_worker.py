from __future__ import annotations

import asyncio
import json
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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


class JobQueue:
    def __init__(self) -> None:
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._cancel: set[str] = set()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

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
        spatial = parse_spatial_map(project.spatial_map_json)
        notes = spatial_prompt_notes(spatial)
        combined = " ".join(x for x in [project.global_prompt, resolved.prompt] if x).strip()
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

        if is_fal_engine(scene.engine):
            return await self._build_and_run_fal_scene(db, project, scene, job, positive, negative, seed, plan)

        length = self._frames_for_scene(scene, plan.fps)
        length, frame_clamped = clamp_frames(length, plan)
        steps = plan.steps
        width, height = plan.width, plan.height

        if plan.notes or frame_clamped:
            bits = [b for b in [plan.notes, f"Frames capped to {length} for {plan.label} VRAM" if frame_clamped else ""] if b]
            if bits:
                job.message = " · ".join(bits)
                db.commit()

        start = await self._ensure_comfy_image(self._get_asset(db, scene.start_asset_id))
        middle = await self._ensure_comfy_image(self._get_asset(db, scene.middle_asset_id))
        end = await self._ensure_comfy_image(self._get_asset(db, scene.end_asset_id))
        audio = await self._ensure_comfy_file(self._get_asset(db, scene.audio_asset_id))

        prefix = f"studio/{project.id[:8]}_{scene.index}"

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
                fps=plan.fps,
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
                fps=plan.fps,
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
                    fps=plan.fps,
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

        model_id, args = build_fal_arguments(
            engine=scene.engine,
            prompt=positive,
            negative=negative,
            image_url=image_url,
            end_image_url=end_url,
            duration_sec=scene.duration_sec,
            width=plan.width,
            height=plan.height,
            seed=seed,
            generate_audio=True,
        )
        job.message = f"fal.ai · {model_id}"
        job.comfy_prompt_id = model_id[:64]
        db.commit()

        result = await run_fal_model(model_id, args, api_key, on_progress=on_progress)
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

    async def _export(self, db: Session, job: Job, project: Project) -> None:
        scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.index).all()
        assets = db.query(Asset).filter(Asset.project_id == project.id).all()
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
                }
                for s in scenes
            ],
            "assets": [{"id": a.id, "tag": a.tag, "kind": a.kind, "filename": a.filename} for a in assets],
        }
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
