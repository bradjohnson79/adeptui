from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..director_references.tags import ensure_tags
from ..director_timeline import (
    DirectorTimeline,
    dumps_director_timeline,
    dumps_director_timeline_preserving_embedded,
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
from ..project_cleanup import delete_project_residue
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
    cover = project_service.pick_cover_asset(assets)
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
        storyboard_style=_settings_get(project, "storyboardStyle"),
        preferred_video_generator=_settings_get(project, "preferredVideoGenerator"),
        version=getattr(project, "version", "1.0") or "1.0",
        tags_json=getattr(project, "tags_json", "[]") or "[]",
        archived=int(getattr(project, "archived", 0) or 0),
        defaults_json=getattr(project, "defaults_json", "") or "",
        settings_json=getattr(project, "settings_json", "") or "",
        primary_project_type=getattr(project, "primary_project_type", None) or "custom",
        project_traits_json=getattr(project, "project_traits_json", None) or "[]",
        resolved_profile_json=getattr(project, "resolved_profile_json", None) or "{}",
        project_type_version=int(getattr(project, "project_type_version", 1) or 1),
        created_at=project.created_at,
        updated_at=project.updated_at,
        scenes=[SceneOut.model_validate(s) for s in scenes],
        assets=[AssetOut.model_validate(a) for a in assets],
        scene_count=len(scenes),
        asset_count=len(assets),
        render_pct=render_pct,
        cover_asset_id=cover.id if cover else None,
        cover_kind=project_service.cover_media_kind(cover),
        status_label=status_label,
        password_protected=False,
        password_locked=False,
    )


def _settings_get(project: Project, key: str) -> Optional[str]:
    """Read a value from project.settings_json JSON blob."""
    raw = getattr(project, "settings_json", None)
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
        val = data.get(key)
        return str(val) if val is not None else None
    except Exception:
        return None


def _settings_set(project: Project, key: str, value: Optional[str]) -> None:
    """Store a value in project.settings_json JSON blob."""
    raw = getattr(project, "settings_json", None) or "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}
    if value is not None:
        data[key] = value
    else:
        data.pop(key, None)
    project.settings_json = json.dumps(data, ensure_ascii=False)


def _probe_bible_storage() -> str:
    """Lightweight Production Bible DB reachability — never invents readiness."""
    try:
        from sqlalchemy import inspect, text

        from ..db import SessionLocal, engine

        if not inspect(engine).has_table("production_bibles"):
            return "unavailable"
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return "ready"
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — health probe must not raise
        return "unavailable"


@router.get("/healthz")
async def healthz() -> dict:
    """Lightweight health — no DB, no ComfyUI, no capability check.
    Returns 200 immediately if the uvicorn worker is responsive.
    Used by the frontend health probe for fast ONLINE/OFFLINE detection.
    /health is also liveness-only; Comfy/catalog live on /api/comfy/health."""
    return {"status": "ok"}


@router.get("/health", response_model=HealthOut)
async def health():
    """Fast liveness. Same intent as /healthz.

    The UI and the :8760 proxy poll this route. The previous handler awaited
    comfy_health (Comfy HTTP + object_info + on-disk model verifiers),
    capability_service.get_capabilities, and codirector_service.get_health
    (provider/Ollama). Those probes blocked the uvicorn worker and produced
    Gateway Timeout on GET /api/health.

    Do not run Comfy, catalog, or provider discovery here. Detailed status
    lives on /api/comfy/health and /api/capabilities. Operator flags stay
    in-memory from feature_flags so existing flag-matrix consumers still work.
    """
    from ..feature_flags import feature_flags

    specialist_count = 0
    try:
        from ..codirector.intelligence.specialist_registry import SpecialistRegistry

        specialist_count = len(SpecialistRegistry().all())
    except Exception:  # noqa: BLE001 — health must not raise
        pass

    operator = {
        "api": "ok",
        "comfy": "unknown",
        "provider": {
            "id": None,
            "status": "skipped",
            "reachable": False,
            "modelAvailable": False,
            "selectedModel": None,
        },
        "bibleStorage": "skipped",
        "intelligenceEnabled": bool(feature_flags.codirector_intelligence_v2),
        "visionValidationEnabled": bool(feature_flags.vision_validation_v1),
        "timelineReferencesEnabled": bool(feature_flags.timeline_references_v1),
        "productionExecutiveEnabled": bool(feature_flags.production_executive_v1),
        "modelRadarEnabled": bool(feature_flags.model_radar_v1),
        "sandboxRuntimeEnabled": bool(feature_flags.sandbox_runtime_v1),
        "virtualStageEnabled": False,
        "shotProfilesEnabled": bool(feature_flags.shot_profiles_v1),
        "productionRecipeEnabled": bool(feature_flags.production_recipe_v1),
        "locationSpinEnabled": bool(feature_flags.location_spin_v1),
        "imageProductionEnabled": bool(feature_flags.image_production_v1),
        "frameProductionEnabled": bool(feature_flags.frame_production_v1),
        "videoProductionEnabled": bool(feature_flags.video_production_v1),
        "directorTimelineEnabled": bool(feature_flags.director_timeline_v1),
        "lipsyncProductionEnabled": bool(feature_flags.lipsync_production_v1),
        "audioProductionEnabled": bool(feature_flags.audio_production_v1),
        "editingProductionEnabled": bool(feature_flags.editing_production_v1),
        "renderProductionEnabled": bool(feature_flags.render_production_v1),
        "codirectorProductionControlEnabled": bool(feature_flags.codirector_production_control_v1),
        "productionIntelligenceEnabled": bool(feature_flags.codirector_production_intelligence_v1),
        "adaptiveLearningEnabled": bool(feature_flags.codirector_adaptive_learning_v1),
        "virtualEnvironmentStudioEnabled": False,
        "unifiedExperienceEnabled": bool(feature_flags.codirector_unified_experience_v1),
        "templatesPresetsEnabled": bool(feature_flags.templates_presets_v1),
        "specialistCount": specialist_count,
        "registry": {
            "callable": 0,
            "blocked": 0,
            "total": 0,
            "deferred": 0,
            "counts": {},
        },
        "packBlockers": [],
        "visualValidationPendingNote": (
            "M2.5 vision validation enabled — review pending assets in Validation Workspace."
            if feature_flags.vision_validation_v1
            else "M2.5 — visual validation flag is off (STUDIO_FEATURE_VISION_VALIDATION_V1)."
        ),
        "partialErrors": [],
    }
    return HealthOut(
        ok=True,
        comfy_reachable=True,
        comfy={
            "status": "unknown",
            "reachable": False,
            "message": "liveness only; use /api/comfy/health for Comfy and /api/capabilities for catalog",
        },
        missing_models=[],
        missing_model_component_ids=[],
        missing_optional_models=[],
        missing_optional_model_component_ids=[],
        comfy_status="unknown",
        comfy_version=None,
        node_catalog_available=False,
        reason_code=None,
        recommended_action=None,
        message="ok",
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
async def fal_key_set(body: FalKeyUpdate):
    """Store a fal.ai key only after fal itself accepts it.

    A key that fal rejects is refused outright; a key we could not check (fal unreachable)
    is stored but reported as unverified rather than quietly presented as working.
    """
    from ..fal_client import validate_fal_key
    from ..secrets_store import secret_status, set_secret, set_secret_verification

    key = (body.api_key or "").strip()
    if not key:
        raise HTTPException(400, "api_key is required")

    probe = await validate_fal_key(key)
    if probe.get("valid") is False:
        raise HTTPException(
            400,
            probe.get("message") or "fal.ai rejected this API key.",
        )

    set_secret("fal_api_key", key)
    set_secret_verification(
        "fal_api_key",
        verified=probe.get("valid"),
        message=probe.get("message", ""),
        detail={"httpStatus": probe.get("httpStatus"), "probeEndpoint": probe.get("probeEndpoint")},
    )
    return FalKeyStatus.model_validate(secret_status("fal_api_key"))


@router.post("/fal/key/validate", response_model=FalKeyStatus)
async def fal_key_validate():
    """Re-probe the stored key against fal.ai and refresh its recorded state."""
    from ..fal_client import validate_fal_key
    from ..secrets_store import get_secret, secret_status, set_secret_verification

    key = get_secret("fal_api_key")
    if not key:
        raise HTTPException(404, "No fal.ai API key is configured.")
    probe = await validate_fal_key(key)
    set_secret_verification(
        "fal_api_key",
        verified=probe.get("valid"),
        message=probe.get("message", ""),
        detail={"httpStatus": probe.get("httpStatus"), "probeEndpoint": probe.get("probeEndpoint")},
    )
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
def list_projects(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    # Hide archived from default home list
    projects = [p for p in projects if not getattr(p, "archived", 0)]
    out = []
    try:
        from ..project_security import service as project_security

        for p in projects:
            po = _project_out(db, p)
            redacted = project_security.redact_project_dict(db, po.model_dump(), p.id, request)
            out.append(ProjectOut.model_validate(redacted))
    except Exception:
        out = [_project_out(db, p) for p in projects]
    return out


@router.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    from ..feature_flags import feature_flags

    settings: dict[str, Any] = {}
    if body.storyboard_style:
        settings["storyboardStyle"] = body.storyboard_style
    if body.preferred_video_generator:
        settings["preferredVideoGenerator"] = body.preferred_video_generator

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
        primary_project_type=body.primary_project_type or "custom",
        project_traits_json=json.dumps(list(body.project_traits or [])),
        resolved_profile_json="{}",
        project_type_version=1,
        settings_json=json.dumps(settings) if settings else "{}",
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
    from ..project_library.service import init_project_library

    init_project_library(db, project)
    db.commit()
    db.refresh(project)

    # M3.1a: apply Project Profile when flag is on (or when an explicit type was provided).
    if feature_flags.templates_presets_v1 or body.primary_project_type:
        try:
            from ..templates_presets.db import ensure_m31a_tables
            from ..templates_presets import project_types as project_types_service

            ensure_m31a_tables()
            primary = body.primary_project_type or "custom"
            profile = project_types_service.resolve_project_profile(
                db,
                primary_type=primary,
                traits=list(body.project_traits or []),
                overrides=dict(body.profile_overrides or {}),
            )
            # If caller passed explicit width/height/fps without overrides, keep them
            # unless profile_overrides or primary type implies profile-driven dims.
            update_dims = bool(body.primary_project_type or body.profile_overrides)
            project_types_service.apply_profile_to_project(
                db,
                project,
                profile,
                traits=list(body.project_traits or []),
                seed_units=True,
                update_dims=update_dims,
            )
            db.refresh(project)
        except Exception:
            # Never fail project create if profile seeding has a soft failure.
            pass

    return _project_out(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    # Middleware enforces unlock; still annotate protection flags for UI.
    po = _project_out(db, project)
    try:
        from ..project_security import service as project_security

        redacted = project_security.redact_project_dict(db, po.model_dump(), project_id, request)
        return ProjectOut.model_validate(redacted)
    except Exception:
        return po


@router.get("/projects/{project_id}/project-profile")
def get_project_profile(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    from ..templates_presets.project_types import get_project_profile_payload
    from .. import project_service as project_service_mod

    payload = get_project_profile_payload(project)
    payload["identity"] = project_service_mod.project_profile(project)
    try:
        from ..templates_presets import store as tp_store

        payload["productionUnits"] = tp_store.list_production_units(db, project_id)
    except Exception:
        payload["productionUnits"] = []
    return payload


@router.post("/projects/{project_id}/project-type/preview")
def preview_project_type_change(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..feature_flags import feature_flags
    from ..templates_presets.db import ensure_m31a_tables
    from ..templates_presets import project_types as project_types_service

    if not feature_flags.templates_presets_v1:
        raise HTTPException(404, "Templates & Presets feature disabled")
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_m31a_tables()
    return project_types_service.preview_project_type_change(
        db,
        project,
        primary_type=str(body.get("primaryProjectType") or body.get("primary_project_type") or "custom"),
        traits=list(body.get("projectTraits") or body.get("project_traits") or []),
        overrides=dict(body.get("overrides") or {}),
    )


@router.post("/projects/{project_id}/project-type")
def apply_project_type_change(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..feature_flags import feature_flags
    from ..templates_presets.db import ensure_m31a_tables
    from ..templates_presets import project_types as project_types_service

    if not feature_flags.templates_presets_v1:
        raise HTTPException(404, "Templates & Presets feature disabled")
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_m31a_tables()
    result = project_types_service.apply_project_type_change(
        db,
        project,
        primary_type=str(body.get("primaryProjectType") or body.get("primary_project_type") or "custom"),
        traits=list(body.get("projectTraits") or body.get("project_traits") or []),
        overrides=dict(body.get("overrides") or {}),
        apply_dimension_defaults=bool(body.get("applyDimensionDefaults", True)),
    )
    return {"ok": True, **result, "project": _project_out(db, project)}


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
    # Phase CK — storyboard/video generator stored in settings_json, not direct columns
    for settings_field, settings_key in [("storyboard_style", "storyboardStyle"), ("preferred_video_generator", "preferredVideoGenerator")]:
        if settings_field in data:
            _settings_set(project, settings_key, data.pop(settings_field))
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
    delete_project_residue(db, project_id)
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
    # PUT_DIRECTOR_PRESERVES_MASTER: never replace the entire director_json
    # blob. Merge the incoming DirectorTimeline fields over the existing blob
    # so embedded timelineMaster / timelineWorkspace (W46 batch state) and
    # other non-DirectorTimeline keys survive a legacy track update. Without
    # this, every Visual-track / Inspector / undo-redo save erased
    # timelineMaster and load_master re-migrated to a single Batch 1,
    # destroying all other batches.
    scene.director_json = dumps_director_timeline_preserving_embedded(body, scene.director_json)
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


def _delete_asset_thumbnails(asset_dir: Path, stem: str) -> None:
    thumbs_dir = asset_dir / ".thumbs"
    if not thumbs_dir.is_dir():
        return
    for p in list(thumbs_dir.glob(f"{stem}_*.webp")):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


@router.delete("/projects/{project_id}/assets/{asset_id}")
def delete_asset(project_id: str, asset_id: str, db: Session = Depends(get_db)):
    from ..scene_references import service as scene_ref_service

    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(404, "Asset not found")

    usage = scene_ref_service.asset_usage(db, project_id, asset_id)
    if usage["deleteBlocked"]:
        return {
            "deleteBlocked": True,
            "assetId": asset_id,
            "name": asset.tag or asset.filename,
            "activeBindingCount": usage["activeBindingCount"],
            "bindings": usage["bindings"],
        }

    asset_path = Path(asset.path)
    if asset_path.exists():
        try:
            asset_path.unlink()
        except Exception:
            pass

    asset_dir = asset_path.parent
    stem = asset_path.stem
    _delete_asset_thumbnails(asset_dir, stem)

    db.delete(asset)
    project = db.get(Project, project_id)
    if project:
        project.updated_at = datetime.utcnow()
    db.commit()
    return {"deleted": True, "assetId": asset_id, "name": asset.tag or asset.filename}


@router.post("/projects/{project_id}/assets/bulk-delete")
def bulk_delete_assets(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..scene_references import service as scene_ref_service

    asset_ids: list[str] = body.get("assetIds") or []
    force: bool = bool(body.get("force", False))
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    results: list[dict] = []
    for asset_id in asset_ids:
        try:
            asset = db.get(Asset, asset_id)
            if not asset or asset.project_id != project_id:
                results.append({"assetId": asset_id, "status": "failed", "name": None})
                continue

            if not force:
                usage = scene_ref_service.asset_usage(db, project_id, asset_id)
                if usage["deleteBlocked"]:
                    results.append({
                        "assetId": asset_id,
                        "status": "blocked",
                        "name": asset.tag or asset.filename,
                        "activeBindingCount": usage["activeBindingCount"],
                    })
                    continue

            asset_path = Path(asset.path)
            if asset_path.exists():
                try:
                    asset_path.unlink()
                except Exception:
                    pass

            asset_dir = asset_path.parent
            stem = asset_path.stem
            _delete_asset_thumbnails(asset_dir, stem)

            db.delete(asset)
            results.append({"assetId": asset_id, "status": "deleted", "name": asset.tag or asset.filename})
        except Exception:
            results.append({"assetId": asset_id, "status": "failed", "name": None})

    project.updated_at = datetime.utcnow()
    db.commit()
    return {"results": results}


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
    """Queue a project render.

    Body ``kind``:
      - ``scene`` → job ``render_scene`` (requires ``scene_id``)
      - ``shot`` → job ``render_shot`` (requires ``scene_id``; certified shot render)
      - ``timeline`` → job ``render_timeline`` (reuse scene outputs when present, stitch)
      - ``batch_timeline`` → job ``batch_timeline`` (regenerate all scenes, stitch)
      - ``editor_mix`` → job ``editor_mix`` — ffmpeg final mix of Editor
        dialogue/sfx/ambience/music stems onto a primary video MP4.
        Optional ``primary_video_path``; otherwise resolves latest timeline
        output, Editor video clip, or scene lipsync/output. Result is a
        project Asset (kind=video) with ``prompt_meta_json`` stem provenance.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    kind_map = {
        "scene": "render_scene",
        "shot": "render_shot",
        "timeline": "render_timeline",
        "batch_timeline": "batch_timeline",
        "editor_mix": "editor_mix",
    }
    kind = kind_map.get(body.kind, "render_timeline")
    if kind in {"render_scene", "render_shot"} and not body.scene_id:
        raise HTTPException(400, "scene_id required for scene/shot render")
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
    if body.providerPreference:
        params["providerPreference"] = body.providerPreference
    params["paidFallbackApproved"] = bool(body.paidFallbackApproved)
    if body.startFrameModel:
        params["startFrameModel"] = body.startFrameModel
    if body.generate_audio is not None:
        params["generate_audio"] = bool(body.generate_audio)
    if body.primary_video_path:
        params["primary_video_path"] = body.primary_video_path
    # Production Dock → video resolver (scene/shot renders consume active engine).
    if kind in {"render_scene", "render_shot", "batch_timeline"}:
        try:
            from ..production_control.runtime_map import apply_video_dock_preference

            dock = apply_video_dock_preference(project_id, engine_hint=params.get("engine"))
            if dock.get("engine") and not params.get("engine"):
                params["engine"] = dock["engine"]
            params["productionDock"] = dock
            params["preferenceProvenance"] = dock.get("provenance")
        except HTTPException:
            raise
        except Exception:
            pass

    # Smart Production Gates (SMART_PRODUCTION_GATES): final scene/shot
    # generation is blocked on PRODUCTION_LOCK. Editing remains available —
    # only the generation job is refused with a creator-readable reason.
    if kind in {"render_scene", "render_shot"} and body.scene_id:
        try:
            from ..codirector.timeline_context.smart_gates import can_generate_scene

            allowed, reason, gate = can_generate_scene(
                db, project_id, body.scene_id, action_scope="production"
            )
            params["smartGate"] = {
                "level": gate.get("level"),
                "decision": gate.get("decision"),
                "reason": reason,
            }
            if not allowed:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "SMART_PRODUCTION_GATE_LOCKED",
                        "reason": reason,
                        "gateLevel": gate.get("level"),
                    },
                )
        except HTTPException:
            raise
        except Exception:
            # Gate evaluation must never hard-block on internal failure —
            # allow generation and record the diagnostic.
            params["smartGate"] = {"level": "EXPLORATION", "decision": "ALLOW", "reason": "Gate unavailable"}
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
    if body.face_asset_id:
        scene.start_asset_id = body.face_asset_id
    if body.prefer_still_face or body.face_asset_id:
        try:
            meta = json.loads(scene.director_json or "{}")
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        meta["prefer_still_face"] = True
        if body.face_asset_id:
            meta["face_asset_id"] = body.face_asset_id
        scene.director_json = json.dumps(meta)
    db.commit()
    params: dict = {}
    if body.prefer_still_face or body.face_asset_id:
        params["prefer_still_face"] = True
        if body.face_asset_id:
            params["face_asset_id"] = body.face_asset_id
    if body.direct_latentsync:
        params["direct_latentsync"] = True
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene.id,
        kind="lipsync",
        status="queued",
        message=json.dumps(params) if params else "Queued lip sync",
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/projects/{project_id}/export", response_model=JobOut)
async def export_project(project_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        from ..project_security import audit as security_audit
        from ..project_security import service as project_security

        if project_security.is_protected(db, project_id):
            mode = str((body or {}).get("exportMode") or "without_password")
            security_audit.record_audit(
                db, project_id, "protected_project_export_attempted", {"exportMode": mode}
            )
            db.commit()
            if mode == "encrypted_archive":
                raise HTTPException(
                    501,
                    detail={
                        "code": "ENCRYPTED_EXPORT_UNAVAILABLE",
                        "message": "Encrypted project export is not currently available.",
                    },
                )
            # Default: export without project password (hash never included in portable export)
    except HTTPException:
        raise
    except Exception:
        pass
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
    # Deep cancel: enter cancelling, interrupt+delete, confirm prompt stopped, then cancelled.
    # Does NOT mark cancelled until Comfy confirms the prompt is inactive (or timeout → cancel_failed).
    result = await job_queue.cancel_and_halt(job_id)
    job = db.get(Job, job_id)
    status = (job.status if job else result.get("status")) or "cancelling"
    return {
        "ok": bool(result.get("ok")),
        "status": status,
        "confirmedStopped": bool(result.get("confirmedStopped")),
        "errorCode": result.get("errorCode"),
        "halt": result.get("halt"),
        "promptId": result.get("promptId"),
    }


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
        params_json=_json.dumps(payload),
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


