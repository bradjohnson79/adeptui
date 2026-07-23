from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..director_timeline import (
    DirectorTimeline,
    dumps_director_timeline,
    migrate_scene_to_director,
    parse_director_timeline,
    sync_legacy_fields_from_director,
)
from ..lipsync_tracks import LipSyncTracks, dumps_lipsync_tracks, parse_lipsync_tracks
from ..mouth_tracker import Roi, overlay_track_preview, track_mouth_rois
from ..assistant import (
    SceneSetupProposal,
    apply_scene_setup,
    build_context_block,
    chat_ollama,
    extract_scene_setup,
    extract_suggested_prompt,
    list_ollama_models,
    ollama_reachable,
    strip_scene_setup_blocks,
)
from ..comfy_client import comfy
from ..config import settings
from ..db import Asset, Job, Project, Scene, get_db
from ..queue_worker import job_queue
from ..references import resolve_prompt
from ..schemas import (
    AssetOut,
    AssistantApplySetupRequest,
    AssistantApplySetupResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantHealth,
    EngineOptionOut,
    FalKeyStatus,
    FalKeyUpdate,
    FalModelOut,
    FalUsageOut,
    GpuStatsOut,
    HealthOut,
    ImageToolRequest,
    JobOut,
    LipSyncRequest,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RenderRequest,
    SceneIn,
    SceneOut,
    SceneSetupOut,
    SpatialMap,
    TagResolveOut,
    VramDetectOut,
    VramProfileOut,
)
from ..spatial import auto_tags_from_spatial, parse_spatial_map

router = APIRouter()


def _project_out(db: Session, project: Project) -> ProjectOut:
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.index).all()
    assets = db.query(Asset).filter(Asset.project_id == project.id).all()
    return ProjectOut(
        id=project.id,
        name=project.name,
        engine_default=project.engine_default,
        global_prompt=project.global_prompt,
        negative_prompt=project.negative_prompt,
        width=project.width,
        height=project.height,
        fps=project.fps,
        seed=project.seed,
        preset=project.preset,
        vram_gb=getattr(project, "vram_gb", 32) or 32,
        spatial_map_json=project.spatial_map_json or "{}",
        created_at=project.created_at,
        updated_at=project.updated_at,
        scenes=[SceneOut.model_validate(s) for s in scenes],
        assets=[AssetOut.model_validate(a) for a in assets],
    )


@router.get("/health", response_model=HealthOut)
async def health():
    missing: list[str] = []
    comfy_data = {}
    reachable = False
    try:
        comfy_data = await comfy.health()
        reachable = True
    except Exception as exc:
        return HealthOut(ok=False, comfy_reachable=False, message=str(exc))

    # quick model presence checks via filesystem
    models = Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models")
    checks = {
        "LTX checkpoint": models / "checkpoints" / settings.ltx_checkpoint,
        "WAN high noise": models / "diffusion_models" / settings.wan_high_noise,
        "WAN low noise": models / "diffusion_models" / settings.wan_low_noise,
    }
    for label, path in checks.items():
        if not path.exists():
            # also check nested
            found = list(models.rglob(path.name))
            if not found:
                missing.append(label)
    return HealthOut(
        ok=True,
        comfy_reachable=reachable,
        comfy=comfy_data,
        missing_models=missing,
        message="ready" if not missing else "ready with missing optional models",
    )


@router.get("/vram-presets", response_model=list[VramProfileOut])
def vram_presets():
    from ..vram_profiles import list_profiles

    return [VramProfileOut.model_validate(p) for p in list_profiles()]


@router.get("/vram-detect", response_model=VramDetectOut)
def vram_detect():
    from ..vram_profiles import detect_vram_gb

    tier = detect_vram_gb()
    if tier is None:
        return VramDetectOut(
            detected_gb=None,
            tier=None,
            message="Could not detect GPU VRAM (nvidia-smi unavailable). Pick a tier manually.",
        )
    return VramDetectOut(
        detected_gb=tier,
        tier=tier,
        message=f"Detected approximately {tier} GB class GPU — recommended preset applied when you confirm.",
    )


@router.get("/gpu/stats", response_model=GpuStatsOut)
def gpu_stats():
    from ..vram_profiles import query_gpu_stats

    data = query_gpu_stats()
    return GpuStatsOut.model_validate(data)


@router.get("/engines", response_model=list[EngineOptionOut])
def list_engines():
    from ..fal_catalog import list_engines_for_ui

    return [EngineOptionOut.model_validate(e) for e in list_engines_for_ui()]


@router.get("/fal/models", response_model=list[FalModelOut])
def fal_models():
    from ..fal_catalog import list_fal_models

    return [FalModelOut.model_validate(m) for m in list_fal_models()]


@router.get("/fal/key", response_model=FalKeyStatus)
def fal_key_status():
    from ..secrets_store import secret_status

    return FalKeyStatus.model_validate(secret_status("fal_api_key"))


@router.put("/fal/key", response_model=FalKeyStatus)
def fal_key_set(body: FalKeyUpdate):
    from ..secrets_store import secret_status, set_secret

    key = (body.api_key or "").strip()
    if not key:
        raise HTTPException(400, "api_key is required")
    set_secret("fal_api_key", key)
    return FalKeyStatus.model_validate(secret_status("fal_api_key"))


@router.delete("/fal/key", response_model=FalKeyStatus)
def fal_key_clear():
    from ..secrets_store import clear_secret, secret_status

    clear_secret("fal_api_key")
    return FalKeyStatus.model_validate(secret_status("fal_api_key"))


@router.get("/fal/usage", response_model=FalUsageOut)
async def fal_usage(days: int = 30):
    from ..fal_client import fetch_fal_account_usage
    from ..secrets_store import get_secret

    key = get_secret("fal_api_key")
    if not key:
        return FalUsageOut(
            ok=False,
            configured=False,
            message="Save a fal.ai API key above to see balance and usage.",
            manage_url="https://fal.ai/dashboard/usage",
            billing_url="https://fal.ai/dashboard/billing",
            keys_url="https://fal.ai/dashboard/keys",
            login_url="https://fal.ai/login",
        )
    data = await fetch_fal_account_usage(key, days=days)
    return FalUsageOut.model_validate(data)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return [_project_out(db, p) for p in projects]


@router.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        engine_default=body.engine_default,
        global_prompt=body.global_prompt,
        negative_prompt=body.negative_prompt,
        width=body.width,
        height=body.height,
        fps=body.fps,
        seed=body.seed,
        preset=body.preset,
        vram_gb=body.vram_gb,
        spatial_map_json="{}",
    )
    db.add(project)
    # default first scene
    scene = Scene(
        id=str(uuid.uuid4()),
        project_id=project.id,
        index=0,
        name="Scene 1",
        engine=body.engine_default,
        duration_sec=5.0,
    )
    db.add(scene)
    from ..vram_profiles import apply_profile_to_project, detect_vram_gb, normalize_vram_tier

    # Prefer live GPU detection for new projects; fall back to requested tier.
    tier = detect_vram_gb() or normalize_vram_tier(body.vram_gb)
    apply_profile_to_project(project, tier)
    db.commit()
    db.refresh(project)
    return _project_out(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _project_out(db, project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    data = body.model_dump(exclude_unset=True)
    apply_vram = bool(data.pop("apply_vram_profile", False))
    for field, value in data.items():
        setattr(project, field, value)
    if apply_vram:
        from ..vram_profiles import apply_profile_to_project, normalize_vram_tier

        tier = normalize_vram_tier(getattr(project, "vram_gb", 32))
        apply_profile_to_project(project, tier)
    project.updated_at = datetime.utcnow()
    db.commit()
    return _project_out(db, project)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/scenes", response_model=SceneOut)
def add_scene(project_id: str, body: SceneIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    count = db.query(Scene).filter(Scene.project_id == project_id).count()
    scene = Scene(
        id=str(uuid.uuid4()),
        project_id=project_id,
        index=count,
        name=body.name or f"Scene {count + 1}",
        engine=body.engine,
        prompt=body.prompt,
        duration_sec=body.duration_sec,
        start_asset_id=body.start_asset_id,
        middle_asset_id=body.middle_asset_id,
        end_asset_id=body.end_asset_id,
        audio_asset_id=body.audio_asset_id,
        lipsync_enabled=1 if body.lipsync_enabled else 0,
        lipsync_audio_asset_id=body.lipsync_audio_asset_id,
        camera_note=body.camera_note,
        seed=body.seed,
    )
    db.add(scene)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return SceneOut.model_validate(scene)


@router.patch("/projects/{project_id}/scenes/{scene_id}", response_model=SceneOut)
def update_scene(project_id: str, scene_id: str, body: SceneIn, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    data = body.model_dump()
    data["lipsync_enabled"] = 1 if body.lipsync_enabled else 0
    tracks_json = data.pop("lipsync_tracks_json", None)
    director_json = data.pop("director_json", None)
    for k, v in data.items():
        setattr(scene, k, v)
    if tracks_json is not None:
        scene.lipsync_tracks_json = tracks_json
    if director_json is not None:
        scene.director_json = director_json
    db.commit()
    db.refresh(scene)
    return SceneOut.model_validate(scene)


def _scene_director(scene: Scene) -> DirectorTimeline:
    if scene.director_json and scene.director_json.strip():
        return parse_director_timeline(
            scene.director_json,
            fallback_duration=scene.duration_sec,
            fallback_prompt=scene.prompt,
        )
    return migrate_scene_to_director(
        duration_sec=scene.duration_sec,
        prompt=scene.prompt,
        start_asset_id=scene.start_asset_id,
        middle_asset_id=scene.middle_asset_id,
        end_asset_id=scene.end_asset_id,
        audio_asset_id=scene.audio_asset_id,
        lipsync_tracks_json=scene.lipsync_tracks_json,
    )


@router.get("/projects/{project_id}/scenes/{scene_id}/director", response_model=DirectorTimeline)
def get_director(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    return _scene_director(scene)


@router.put("/projects/{project_id}/scenes/{scene_id}/director", response_model=DirectorTimeline)
def put_director(project_id: str, scene_id: str, body: DirectorTimeline, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    scene.director_json = dumps_director_timeline(body)
    legacy = sync_legacy_fields_from_director(body)
    for k, v in legacy.items():
        setattr(scene, k, v)
    db.commit()
    return body



@router.get("/projects/{project_id}/scenes/{scene_id}/lipsync-tracks", response_model=LipSyncTracks)
def get_lipsync_tracks(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    return parse_lipsync_tracks(scene.lipsync_tracks_json)


@router.put("/projects/{project_id}/scenes/{scene_id}/lipsync-tracks", response_model=LipSyncTracks)
def put_lipsync_tracks(project_id: str, scene_id: str, body: LipSyncTracks, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    # Normalize to 2 tracks
    normalized = parse_lipsync_tracks(body.model_dump_json())
    # Keep incoming values for slots 1-2
    by_slot = {t.slot: t for t in body.tracks if t.slot in (1, 2)}
    for t in normalized.tracks:
        if t.slot in by_slot:
            normalized.tracks[t.slot - 1] = by_slot[t.slot]
    scene.lipsync_tracks_json = dumps_lipsync_tracks(normalized)
    # Enable scene lipsync if any track enabled
    scene.lipsync_enabled = 1 if any(t.enabled for t in normalized.tracks) else scene.lipsync_enabled
    db.commit()
    return normalized


@router.post("/projects/{project_id}/scenes/{scene_id}/lipsync-tracks/bake")
def bake_lipsync_tracks(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Bake sticky mouth paths for enabled tracks from the scene render video."""
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    video = scene.lipsync_output_path or scene.output_path
    if not video or not Path(video).exists():
        raise HTTPException(400, "Render the scene first so mouth tracking has a video to follow")

    tracks = parse_lipsync_tracks(scene.lipsync_tracks_json)
    preview_dir = settings.data_dir / "projects" / project_id / "lipsync_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for track in tracks.tracks:
        if not track.enabled:
            continue
        seed = Roi(track.roi.x, track.roi.y, track.roi.w, track.roi.h)
        try:
            path = track_mouth_rois(Path(video), seed)
        except Exception as exc:
            raise HTTPException(500, f"Tracking failed for {track.label}: {exc}") from exc
        track.track_path = path
        try:
            overlay_track_preview(
                Path(video),
                path,
                preview_dir / f"scene{scene.index}_slot{track.slot}.mp4",
                label=track.label[:12] or f"C{track.slot}",
            )
        except Exception:
            pass

    scene.lipsync_tracks_json = dumps_lipsync_tracks(tracks)
    db.commit()
    return {
        "ok": True,
        "tracks": tracks.model_dump(),
        "preview_dir": str(preview_dir),
    }


@router.post("/projects/{project_id}/scenes/{scene_id}/lipsync-tracks/apply", response_model=JobOut)
async def apply_dual_lipsync(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    tracks = parse_lipsync_tracks(scene.lipsync_tracks_json)
    enabled = [t for t in tracks.tracks if t.enabled]
    if not enabled:
        raise HTTPException(400, "Enable at least one lip-sync track")
    for t in enabled:
        if not t.audio_asset_id:
            raise HTTPException(400, f"{t.label} needs an audio asset")
    import json as _json

    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        kind="dual_lipsync",
        status="queued",
        message=_json.dumps({"scene_id": scene_id}),
    )
    db.add(job)
    scene.lipsync_enabled = 1
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)



@router.delete("/projects/{project_id}/scenes/{scene_id}")
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    db.delete(scene)
    # reindex
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()
    for i, s in enumerate(scenes):
        s.index = i
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/assets", response_model=AssetOut)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    tag: str = Form(""),
    kind: str = Form("image"),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    asset_id = str(uuid.uuid4())
    ext = Path(file.filename or "bin").suffix
    safe_tag = tag.lstrip("@").strip()
    filename = f"{safe_tag or asset_id[:8]}{ext}"
    dest_dir = settings.data_dir / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}{ext}"
    content = await file.read()
    dest.write_bytes(content)

    comfy_name = ""
    try:
        if kind == "image":
            comfy_name = await comfy.upload_image(dest, filename=filename)
        else:
            comfy_name = await comfy.upload_file_copy(dest, filename=filename)
    except Exception:
        comfy_name = ""

    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=safe_tag,
        kind=kind,
        filename=file.filename or filename,
        path=str(dest),
        comfy_name=comfy_name,
    )
    db.add(asset)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


@router.patch("/projects/{project_id}/assets/{asset_id}", response_model=AssetOut)
def update_asset_tag(project_id: str, asset_id: str, tag: str = Form(...), db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(404, "Asset not found")
    asset.tag = tag.lstrip("@").strip()
    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


@router.post("/projects/{project_id}/resolve-tags", response_model=TagResolveOut)
def resolve_tags(project_id: str, prompt: str = Form(...), db: Session = Depends(get_db)):
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    tag_map = {a.tag: (a.id, a.filename) for a in assets if a.tag}
    result = resolve_prompt(prompt, tag_map)
    return TagResolveOut(
        prompt=result.prompt,
        resolved_tags=result.resolved_tags,
        missing_tags=result.missing_tags,
        attached_asset_ids=result.attached_asset_ids,
    )


@router.get("/projects/{project_id}/spatial", response_model=SpatialMap)
def get_spatial(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return parse_spatial_map(project.spatial_map_json)


@router.put("/projects/{project_id}/spatial", response_model=SpatialMap)
def put_spatial(project_id: str, body: SpatialMap, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.spatial_map_json = body.model_dump_json()
    project.updated_at = datetime.utcnow()
    # auto-create tags for labeled points
    tags = auto_tags_from_spatial(body)
    for tag, asset_id in tags.items():
        asset = db.get(Asset, asset_id)
        if asset and asset.project_id == project_id and not asset.tag:
            asset.tag = tag
    db.commit()
    return body


@router.post("/projects/{project_id}/render", response_model=JobOut)
async def render_project(project_id: str, body: RenderRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    kind = "render_scene" if body.kind == "scene" else "render_timeline"
    if kind == "render_scene" and not body.scene_id:
        raise HTTPException(400, "scene_id required for scene render")
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=body.scene_id,
        kind=kind,
        status="queued",
        message="Queued",
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/projects/{project_id}/lipsync", response_model=JobOut)
async def lipsync(project_id: str, body: LipSyncRequest, db: Session = Depends(get_db)):
    scene = db.get(Scene, body.scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    if body.audio_asset_id:
        scene.lipsync_audio_asset_id = body.audio_asset_id
        scene.lipsync_enabled = 1
        db.commit()
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene.id,
        kind="lipsync",
        status="queued",
        message="Queued lip sync",
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/projects/{project_id}/export", response_model=JobOut)
async def export_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind="export",
        status="queued",
        message="Queued export",
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
def list_jobs(project_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(50).all()
    return [JobOut.model_validate(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobOut.model_validate(job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job_queue.cancel(job_id)
    try:
        await comfy.interrupt()
    except Exception:
        pass
    job.status = "cancelled"
    job.message = "Cancel requested"
    job.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


def _extract_suggested_prompt(reply: str) -> str | None:
    """Pull a fenced prompt or a PROMPT: block if the assistant provided one."""
    return extract_suggested_prompt(reply)


@router.get("/assistant/health", response_model=AssistantHealth)
async def assistant_health():
    reachable = await ollama_reachable()
    models: list[str] = []
    if reachable:
        try:
            models = await list_ollama_models()
        except Exception:
            models = []
    has_model = settings.ollama_model in models or any(
        m.startswith(settings.ollama_model.split(":")[0]) for m in models
    )
    return AssistantHealth(
        ok=reachable and (has_model or bool(models)),
        ollama_reachable=reachable,
        model=settings.ollama_model,
        available_models=models,
        message=(
            "ready"
            if reachable and models
            else ("Ollama offline" if not reachable else "No models installed")
        ),
    )


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(body: AssistantChatRequest, db: Session = Depends(get_db)):
    if not await ollama_reachable():
        raise HTTPException(503, "Ollama is not reachable at " + settings.ollama_url)

    project_payload = None
    director_payload = None
    if body.project_id:
        project = db.get(Project, body.project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        project_payload = _project_out(db, project).model_dump(mode="json")
        if body.scene_id:
            scene = db.get(Scene, body.scene_id)
            if scene and scene.project_id == body.project_id:
                director_payload = _scene_director(scene).model_dump(mode="json")

    context = build_context_block(project_payload, body.scene_id, director_payload)
    messages = [{"role": m.role, "content": m.content} for m in body.messages if m.role != "system"]

    # Mode nudges for better answers
    if body.mode == "setup" and messages:
        messages[-1]["content"] = (
            "Build a complete SCENE_SETUP for the selected scene in Adept UI Video Studio. "
            "Use only asset tags/ids listed in context. Fill engine, duration, media_mode, "
            "global_prompt (look/feel), motion prompt or prompt_segments, and image_slots when "
            "image assets exist. Place audio_ref/sfx only if audio assets exist. "
            "Write a short plan for the user, then end with a ```scene_setup JSON fence.\n\n"
            "User request:\n" + messages[-1]["content"]
        )
    elif body.mode == "prompt" and messages:
        messages[-1]["content"] = (
            "Write or improve a ready-to-paste video prompt for the selected scene. "
            "Put the final prompt in a ```prompt fenced block. "
            "Also give a 1-2 sentence tip.\n\nUser request:\n" + messages[-1]["content"]
        )
    elif body.mode == "guide" and messages:
        messages[-1]["content"] = (
            "Explain how to do this in Adept UI Video Studio with numbered UI steps.\n\n"
            + messages[-1]["content"]
        )
    elif body.mode == "chat" and messages:
        # Auto-promote scene-building requests to setup behavior
        last = messages[-1]["content"].lower()
        if any(
            k in last
            for k in (
                "build the scene",
                "build a scene",
                "set up the scene",
                "setup the scene",
                "set up this scene",
                "configure the scene",
                "create the scene",
                "fill the scene",
                "assemble the scene",
                "scene setup",
            )
        ):
            messages[-1]["content"] = (
                "Build a complete SCENE_SETUP for the selected scene. "
                "Short plan + ```scene_setup JSON fence. Use only listed assets.\n\n"
                "User request:\n" + messages[-1]["content"]
            )

    try:
        reply = await chat_ollama(messages, model=body.model, project_context=context)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc

    setup = extract_scene_setup(reply)
    display = strip_scene_setup_blocks(reply) if setup else reply
    suggested = None if setup else _extract_suggested_prompt(reply)

    return AssistantChatResponse(
        reply=display or reply,
        model=body.model or settings.ollama_model,
        suggested_prompt=suggested,
        scene_setup=SceneSetupOut.model_validate(setup.model_dump()) if setup else None,
    )


@router.post("/assistant/apply-setup", response_model=AssistantApplySetupResponse)
def assistant_apply_setup(body: AssistantApplySetupRequest, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = db.get(Scene, body.scene_id)
    if not scene or scene.project_id != body.project_id:
        raise HTTPException(404, "Scene not found")

    assets = db.query(Asset).filter(Asset.project_id == body.project_id).all()
    asset_dicts = [
        {
            "id": a.id,
            "tag": a.tag,
            "kind": a.kind,
            "filename": a.filename,
        }
        for a in assets
    ]
    setup = SceneSetupProposal.model_validate(body.setup.model_dump())
    result = apply_scene_setup(project=project, scene=scene, setup=setup, assets=asset_dicts)
    project.updated_at = datetime.utcnow()
    db.commit()
    return AssistantApplySetupResponse(
        ok=result.ok,
        applied=result.applied,
        warnings=result.warnings,
        scene_id=result.scene_id,
        project_id=result.project_id,
    )


async def _enqueue_image_tool(project_id: str, kind: str, body: ImageToolRequest, db: Session) -> JobOut:
    import json as _json

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    asset = db.get(Asset, body.source_asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(400, "source_asset_id must be an image asset in this project")
    if asset.kind != "image":
        raise HTTPException(400, "Source asset must be an image")

    payload = {
        "source_asset_id": body.source_asset_id,
        "character_name": body.character_name,
        "seed": body.seed,
        "width": body.width,
        "height": body.height,
        "angle_prompts": body.angle_prompts,
        "extra_prompt": body.extra_prompt,
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind=kind,
        status="queued",
        message=_json.dumps(payload),
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/projects/{project_id}/tools/character-sheet", response_model=JobOut)
async def character_sheet(project_id: str, body: ImageToolRequest, db: Session = Depends(get_db)):
    """Generate front/side/back + close-up character sheet views from one reference image."""
    return await _enqueue_image_tool(project_id, "character_sheet", body, db)


@router.post("/projects/{project_id}/tools/multi-angle", response_model=JobOut)
async def multi_angle(project_id: str, body: ImageToolRequest, db: Session = Depends(get_db)):
    """Generate 3 consistent camera angles from a single shot."""
    return await _enqueue_image_tool(project_id, "multi_angle", body, db)


