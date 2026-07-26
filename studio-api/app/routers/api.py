from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..director_references.tags import ensure_tags
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
    chat_ollama,
    ollama_reachable,
    strip_scene_setup_blocks,
)
from ..codirector import service as codirector_service
from ..codirector.errors import CoDirectorError, status_code_for_error
from ..comfy_client import comfy
from ..config import settings
from ..db import Asset, Job, Project, Scene, get_db
from .. import project_service
from ..queue_worker import job_queue
from ..references import resolve_prompt
from ..services.scene_service import SceneService
from ..schemas import (
    AssetOut,
    AssistantApplySetupRequest,
    AssistantApplySetupResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantHealth,
    EngineOptionOut,
    EngineRecommendOut,
    ExecutionPlanOut,
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
    RenderSafetyFlags,
    SceneIn,
    SceneOut,
    SceneSetupOut,
    SpatialMap,
    TagResolveOut,
    TimelineApplyRequest,
    TimelineProposalOut,
    TimelineProposeRequest,
    TimelineSceneProposal,
    VramDetectOut,
    VramProfileOut,
)
from ..spatial import auto_tags_from_spatial, parse_spatial_map

router = APIRouter()


def _project_out(db: Session, project: Project) -> ProjectOut:
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.index).all()
    assets = db.query(Asset).filter(Asset.project_id == project.id).all()
    with_output = sum(1 for s in scenes if getattr(s, "output_path", None))
    render_pct = int(100 * with_output / max(1, len(scenes))) if scenes else 0
    cover = next((a for a in assets if a.kind == "image"), None)
    # Status heuristic for library filters — shared with Co-Director's get_project_status tool.
    status_label = project_service.status_label(
        archived=bool(getattr(project, "archived", 0)),
        active_jobs=project_service.active_job_count(db, project.id),
        scene_count=len(scenes),
        scenes_with_output=with_output,
    )
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
        render_safety_json=getattr(project, "render_safety_json", "") or "",
        learning_json=getattr(project, "learning_json", "") or "",
        learning_enabled_json=getattr(project, "learning_enabled_json", "") or "",
        preview_settings_json=getattr(project, "preview_settings_json", "") or "",
        description=getattr(project, "description", "") or "",
        company=getattr(project, "company", "") or "",
        director_name=getattr(project, "director_name", "") or "",
        version=getattr(project, "version", "1.0") or "1.0",
        tags_json=getattr(project, "tags_json", "[]") or "[]",
        archived=int(getattr(project, "archived", 0) or 0),
        defaults_json=getattr(project, "defaults_json", "") or "",
        settings_json=getattr(project, "settings_json", "") or "",
        created_at=project.created_at,
        updated_at=project.updated_at,
        scenes=[SceneOut.model_validate(s) for s in scenes],
        assets=[AssetOut.model_validate(a) for a in assets],
        scene_count=len(scenes),
        asset_count=len(assets),
        render_pct=render_pct,
        cover_asset_id=cover.id if cover else None,
        status_label=status_label,
    )


@router.get("/health", response_model=HealthOut)
async def health():
    """Structured health.

    The previous implementation probed one developer's hardcoded `%LOCALAPPDATA%` ComfyUI
    model root for three filenames and returned a raw exception string when anything threw.
    Model presence now comes from the same component verifiers the Setup Wizard and Source
    Manager use, so a gap names a real component id that a blocker action can act on.
    `missing_models` is retained as human-readable labels for existing consumers.
    """
    from ..comfy_health import comfy_health

    payload = await comfy_health()
    reachable = bool(payload.get("reachable"))
    models = payload.get("models") or []
    missing = [str(item.get("name") or item.get("componentId")) for item in models if not item.get("present")]

    from ..capabilities import service as capability_service
    from ..codirector import service as codirector_service
    from ..codirector.intelligence.specialist_registry import SpecialistRegistry
    from ..feature_flags import feature_flags

    caps = await capability_service.get_capabilities(force=False)
    provider = await codirector_service.get_health()
    specialist_count = len(SpecialistRegistry().all())
    pack_blockers = [
        {
            "capabilityId": b.capabilityId,
            "message": b.message,
            "recommendedAction": b.recommendedAction,
            "componentIds": list(b.componentIds),
        }
        for b in caps.blockers
        if b.subsystem in ("source_manager", "models", "workflows", "comfyui")
    ]
    operator = {
        "api": "ok",
        "comfy": "reachable" if reachable else "down",
        "provider": {
            "id": provider.provider_id,
            "status": provider.status,
            "reachable": provider.reachable,
            "modelAvailable": provider.model_available,
            "selectedModel": provider.selected_model,
        },
        "bibleStorage": "ready",
        "intelligenceEnabled": bool(feature_flags.codirector_intelligence_v2),
        "visionValidationEnabled": bool(feature_flags.vision_validation_v1),
        "timelineReferencesEnabled": bool(feature_flags.timeline_references_v1),
        "productionExecutiveEnabled": bool(feature_flags.production_executive_v1),
        "modelRadarEnabled": bool(feature_flags.model_radar_v1),
        "sandboxRuntimeEnabled": bool(feature_flags.sandbox_runtime_v1),
        "virtualStageEnabled": bool(feature_flags.virtual_stage_v1),
        "shotProfilesEnabled": bool(feature_flags.shot_profiles_v1),
        "productionRecipeEnabled": bool(feature_flags.production_recipe_v1),
        "locationSpinEnabled": bool(feature_flags.location_spin_v1),
        "specialistCount": specialist_count,
        "registry": {
            "callable": len(caps.callable),
            "blocked": len(caps.blockers),
            "total": len(caps.capabilities),
            "counts": dict(caps.counts),
        },
        "packBlockers": pack_blockers[:12],
        "visualValidationPendingNote": (
            "M2.5 vision validation enabled — review pending assets in Validation Workspace."
            if feature_flags.vision_validation_v1
            else "M2.5 — visual validation flag is off (STUDIO_FEATURE_VISION_VALIDATION_V1)."
        ),
    }
    return HealthOut(
        ok=reachable,
        comfy_reachable=reachable,
        comfy=payload,
        missing_models=missing,
        missing_model_component_ids=list(payload.get("missingModelComponentIds") or []),
        comfy_status=str(payload.get("status") or "unknown"),
        comfy_version=payload.get("version"),
        node_catalog_available=bool(payload.get("nodeCatalogAvailable")),
        reason_code=payload.get("reasonCode"),
        recommended_action=payload.get("recommendedAction"),
        message=str(payload.get("message") or ""),
        operator=operator,
    )


@router.get("/comfy/object-info-count")
async def comfy_object_info_count():
    """Small diagnostic: how many node types the live ComfyUI catalogue exposes."""
    from ..comfy_health import node_types

    names = await node_types()
    return {"available": names is not None, "count": len(names or ())}


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
    # Hide archived from default home list
    projects = [p for p in projects if not getattr(p, "archived", 0)]
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


@router.get("/projects/{project_id}/execution-plan", response_model=ExecutionPlanOut)
def get_execution_plan(
    project_id: str, scene_id: str | None = None, db: Session = Depends(get_db)
):
    from ..aspect_fps import resolve_scene_dims, resolve_scene_fps, validate_engine_aspect
    from ..preview_bus import preview_bus
    from ..vram_profiles import resolve_render_plan
    import json

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    plan = resolve_render_plan(project)
    scene = db.get(Scene, scene_id) if scene_id else None
    if scene and scene.project_id == project_id:
        sw, sh = resolve_scene_dims(project, scene)
        sfps = resolve_scene_fps(project, scene)
        # Prefer scene dims but still respect VRAM clamp from plan
        if plan.vram_gb < 32:
            width, height = min(sw, plan.width), min(sh, plan.height)
            fps = min(sfps, plan.fps)
            clamped = width < sw or height < sh or fps < sfps or plan.clamped
        else:
            width, height, fps = sw, sh, sfps
            clamped = plan.clamped
        aspect = getattr(scene, "aspect_ratio", None) or "16:9"
        fps_mode = getattr(scene, "fps_mode", None) or "auto"
        eng_warn = validate_engine_aspect(scene.engine, aspect)
        caps = preview_bus.capabilities_for(scene.engine if scene.engine != "auto" else "ltx")
    else:
        width, height, fps = plan.width, plan.height, plan.fps
        clamped = plan.clamped
        aspect = "16:9"
        fps_mode = "auto"
        eng_warn = []
        caps = preview_bus.capabilities_for(project.engine_default)

    safety_raw = getattr(project, "render_safety_json", "") or ""
    try:
        safety = RenderSafetyFlags.model_validate(json.loads(safety_raw) if safety_raw.strip() else {})
    except Exception:
        safety = RenderSafetyFlags()
    chunk = (
        f" Chunk assist: {plan.assist_chunk_frames} frames."
        if plan.assist_chunk_frames
        else ""
    )
    live = (
        f"Live execution plan: {width}×{height} @{fps}fps · aspect {aspect} · fps_mode {fps_mode} · "
        f"{plan.steps} steps · max {plan.max_frames} frames (~{plan.max_duration_sec}s) · "
        f"{plan.label} VRAM."
        f"{(' ' + plan.notes) if plan.notes else ''}"
        f"{chunk}"
    )
    if eng_warn:
        live += " " + " ".join(eng_warn)
    if safety.unload_after_render:
        live += " Unload models after render (config)."
    if safety.vae_tiling:
        live += " VAE tiling hint on (config)."
    return ExecutionPlanOut(
        vram_gb=plan.vram_gb,
        label=plan.label,
        width=width,
        height=height,
        fps=fps,
        steps=plan.steps,
        max_frames=plan.max_frames,
        max_duration_sec=plan.max_duration_sec,
        image_tool_size=plan.image_tool_size,
        lipsync_size=plan.lipsync_size,
        lipsync_steps=plan.lipsync_steps,
        assist_chunk_frames=plan.assist_chunk_frames,
        summary=plan.summary,
        assists=plan.assists,
        clamped=clamped,
        notes=plan.notes,
        live_text=live,
        safety=safety,
        aspect_ratio=aspect,
        fps_mode=fps_mode,
        engine_warnings=eng_warn,
        preview_caps=caps,
    )


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/recommend-engine",
    response_model=EngineRecommendOut,
)
def recommend_scene_engine(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    from ..engine_recommend import recommend_engine

    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    return EngineRecommendOut.model_validate(recommend_engine(project=project, scene=scene))


@router.post("/projects/{project_id}/timeline/propose", response_model=TimelineProposalOut)
async def propose_timeline(
    project_id: str, body: TimelineProposeRequest, db: Session = Depends(get_db)
):
    """Ask Ollama for a scene list from a brief. Never mutates scenes."""
    import json
    import re

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    brief = (body.brief or "").strip()
    if not brief:
        raise HTTPException(400, "brief is required")

    warnings: list[str] = []
    scenes: list[TimelineSceneProposal] = []
    summary = ""

    system = (
        "You are Adept UI Video Studio's timeline planner. "
        "Given a short brief/script, propose 2–8 scenes for a video timeline. "
        "Reply with a short prose summary, then a fenced JSON block:\n"
        "```timeline_proposal\n"
        '{"summary":"...","scenes":[{"name":"...","prompt":"...","duration_sec":5,'
        '"engine":"ltx","camera_note":"..."}]}\n'
        "```\n"
        "Use engines: auto, ltx, wan, or fal_* only when cloud is appropriate. "
        "Keep durations between 3 and 10 seconds."
    )
    user = f"Project: {project.name}\nGlobal look: {project.global_prompt or '(none)'}\n\nBrief:\n{brief}"

    if await ollama_reachable():
        try:
            raw = await chat_ollama(
                [{"role": "user", "content": user}],
                model=body.model,
                project_context=system,
            )
            summary = strip_scene_setup_blocks(raw).strip()
            m = re.search(
                r"```timeline_proposal\s*([\s\S]*?)```", raw, flags=re.IGNORECASE
            ) or re.search(r"```json\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
            if m:
                data = json.loads(m.group(1).strip())
                summary = data.get("summary") or summary
                for item in data.get("scenes") or []:
                    scenes.append(TimelineSceneProposal.model_validate(item))
        except Exception as exc:
            warnings.append(f"Ollama propose failed: {exc}")
    else:
        warnings.append("Ollama unreachable — used heuristic split")

    if not scenes:
        # Heuristic: split by blank lines or sentences into up to 6 beats
        parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?])\s+", brief) if p.strip()]
        if len(parts) < 2:
            parts = [brief]
        parts = parts[:6]
        for i, part in enumerate(parts):
            scenes.append(
                TimelineSceneProposal(
                    name=f"Scene {i + 1}",
                    prompt=part[:800],
                    duration_sec=5.0,
                    engine="auto",
                    camera_note="",
                )
            )
        if not summary:
            summary = f"Proposed {len(scenes)} scenes from brief (review before Apply)."

    return TimelineProposalOut(summary=summary[:2000], scenes=scenes, warnings=warnings)


@router.post("/projects/{project_id}/timeline/apply")
async def apply_timeline(
    project_id: str, body: TimelineApplyRequest, db: Session = Depends(get_db)
):
    """Apply a reviewed scene list. Requires explicit call — never auto-overwrite."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not body.scenes:
        raise HTTPException(400, "scenes required")

    scenes = SceneService.create_many(
        db,
        project_id,
        [
            {
                "name": prop.name or "",
                "engine": prop.engine or project.engine_default or "ltx",
                "prompt": prop.prompt or "",
                "duration_sec": float(prop.duration_sec or 5),
                "camera_note": prop.camera_note or "",
                "seed": project.seed,
            }
            for prop in body.scenes
        ],
        replace_existing=body.replace_existing,
    )
    created = [scene.id for scene in scenes]

    job_id = None
    if body.enqueue_render:
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=None,
            kind="render_timeline",
            status="queued",
            progress=0.0,
            message="Queued timeline render",
        )
        db.add(job)
        db.commit()
        await job_queue.enqueue(job.id)
        job_id = job.id

    return {
        "ok": True,
        "created_scene_ids": created,
        "replaced": body.replace_existing,
        "job_id": job_id,
    }


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
    from ..codirector.bible.cleanup import delete_bible_for_project

    delete_bible_for_project(db, project_id)
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.get("/projects/{project_id}/scenes", response_model=list[SceneOut])
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    """Scenes in timeline order. Cheaper than fetching the whole project payload."""
    SceneService.require_project(db, project_id)
    return [SceneOut.model_validate(scene) for scene in SceneService.list_for_project(db, project_id)]


@router.get("/projects/{project_id}/scenes/{scene_id}", response_model=SceneOut)
def get_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    return SceneOut.model_validate(SceneService.get(db, project_id, scene_id))


@router.post("/projects/{project_id}/scenes", response_model=SceneOut)
def add_scene(project_id: str, body: SceneIn, db: Session = Depends(get_db)):
    scene = SceneService.create(db, project_id, body.model_dump(exclude_unset=True))
    return SceneOut.model_validate(scene)


@router.patch("/projects/{project_id}/scenes/{scene_id}", response_model=SceneOut)
def update_scene(project_id: str, scene_id: str, body: SceneIn, db: Session = Depends(get_db)):
    """Partial update: only the fields present in the request body are written."""
    scene = SceneService.update(db, project_id, scene_id, body.model_dump(exclude_unset=True))
    return SceneOut.model_validate(scene)


def _scene_director(scene: Scene) -> DirectorTimeline:
    if scene.director_json and scene.director_json.strip():
        tl = parse_director_timeline(
            scene.director_json,
            fallback_duration=scene.duration_sec,
            fallback_prompt=scene.prompt,
        )
        return ensure_tags(tl)
    return ensure_tags(
        migrate_scene_to_director(
            duration_sec=scene.duration_sec,
            prompt=scene.prompt,
            start_asset_id=scene.start_asset_id,
            middle_asset_id=scene.middle_asset_id,
            end_asset_id=scene.end_asset_id,
            audio_asset_id=scene.audio_asset_id,
            lipsync_tracks_json=scene.lipsync_tracks_json,
        )
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
    body = ensure_tags(body)
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
    SceneService.delete(db, project_id, scene_id)
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
    params: dict = {}
    if body.reference_method:
        params["reference_method"] = body.reference_method
    if body.sheet_id:
        params["sheet_id"] = body.sheet_id
    if body.strength_preset:
        params["strength_preset"] = body.strength_preset
    if body.strength is not None:
        params["strength"] = body.strength
    if body.ingredients_ic_lora is not None:
        params["ingredients_ic_lora"] = body.ingredients_ic_lora
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=body.scene_id,
        kind=kind,
        status="queued",
        message="Queued",
        params_json=json.dumps(params) if params else "",
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


@router.get("/assistant/health", response_model=AssistantHealth)
async def assistant_health():
    """Thin alias over the Co-Director gateway (kept for existing FE call sites)."""
    health = await codirector_service.get_health()
    return AssistantHealth(
        ok=health.status == "Ready",
        ollama_reachable=health.reachable,
        model=health.selected_model or settings.ollama_model,
        available_models=[m.id for m in health.models],
        message=health.message,
    )


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(body: AssistantChatRequest, db: Session = Depends(get_db)):
    """Thin alias over the Co-Director gateway (kept for existing FE call sites)."""
    try:
        result, setup, suggested, _proposal, _manifest, _invocations = await codirector_service.chat_for_project(
            db,
            messages=[{"role": m.role, "content": m.content} for m in body.messages],
            project_id=body.project_id,
            scene_id=body.scene_id,
            mode=body.mode,
            model=body.model,
        )
    except CoDirectorError as err:
        raise HTTPException(status_code=status_code_for_error(err.code), detail=err.to_dict()) from err

    return AssistantChatResponse(
        reply=result.reply,
        model=result.model_id,
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


