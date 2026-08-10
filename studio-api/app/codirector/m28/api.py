"""FastAPI routes for Co-Director M2.8 Capability Intelligence."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from ...v11_scope import raise_deferred_3d
from .compat.service import CompatService
from .location_spin.service import LocationSpinService
from .promote.service import PromoteService
from .radar.service import RadarService
from .recipes.service import RecipeService
from .routing.service import RoutingService
from .sandbox.service import SandboxService
from .shot_profiles.service import ShotProfileService
from .virtual_stage.service import VirtualStageService

router = APIRouter(prefix="/m28", tags=["codirector-m28"])


def _flag(name: str) -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, name, False))


def _require(*flag_names: str) -> None:
    if any(_flag(n) for n in flag_names):
        return
    raise HTTPException(status_code=404, detail="M2.8 capability is not enabled.")


def _require_virtual_stage_v11() -> None:
    """Version 1.1: Virtual Stage execution deferred to Version 1.2 (foundations kept)."""
    raise_deferred_3d(surface="virtual_stage", flag="virtual_stage_v1", flagEnabled=_flag("virtual_stage_v1"))


class DiscoverBody(BaseModel):
    source: str = Field(..., pattern="^(huggingface|github)$")


class WatchlistBody(BaseModel):
    entryId: str
    projectId: Optional[str] = None


class CompatBody(BaseModel):
    entryId: str
    env: Optional[dict[str, Any]] = None


class SandboxCreateBody(BaseModel):
    name: str = "Isolated Sandbox"
    config: Optional[dict[str, Any]] = None


class PlanBody(BaseModel):
    sandboxId: str
    entryId: str


class PlanDecisionBody(BaseModel):
    projectId: str
    owner: str = "user"


class PromoteBody(BaseModel):
    sandboxId: str


class PromoteDecisionBody(BaseModel):
    projectId: str
    owner: str = "user"
    actor: str = "user"


class RouteBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    filmmakingOutcome: str
    currentShotModel: Optional[str] = None
    hardware: Optional[dict[str, Any]] = None


class RecipeCreateBody(BaseModel):
    projectId: str
    name: str = "Fixture Recipe"
    stages: Optional[list[dict[str, Any]]] = None


class RecipeRunBody(BaseModel):
    simulateFailureAt: Optional[int] = None
    owner: str = "user"


class ShotProfileCreateBody(BaseModel):
    projectId: str
    name: str = "Shot Profile"
    payload: Optional[dict[str, Any]] = None


class ShotProfileSaveBody(BaseModel):
    payload: dict[str, Any]
    mode: Optional[str] = None


class CinematicDepthBody(BaseModel):
    suggestions: list[dict[str, Any]]
    acceptIds: list[str] = Field(default_factory=list)


class AssociateBody(BaseModel):
    storyboardShotId: Optional[str] = None
    timelineItemId: Optional[str] = None


class StageCreateBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    name: str = "Stage"
    camera: Optional[dict[str, Any]] = None


class StageCameraBody(BaseModel):
    camera: dict[str, Any]


class LocationPlanBody(BaseModel):
    projectId: str
    locationName: str = "Fixture Location"


class SpinCameraBody(BaseModel):
    angles: Optional[list[float]] = None


@router.get("/status")
def m28_status() -> dict[str, Any]:
    return {
        "modelRadar": _flag("model_radar_v1"),
        "sandboxRuntime": _flag("sandbox_runtime_v1"),
        "virtualStage": _flag("virtual_stage_v1"),
        "shotProfiles": _flag("shot_profiles_v1"),
        "productionRecipe": _flag("production_recipe_v1"),
        "locationSpin": _flag("location_spin_v1"),
    }


@router.post("/radar/discover")
def radar_discover(body: DiscoverBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("model_radar_v1")
    try:
        return RadarService.discover(db, source=body.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/radar/registry")
def radar_registry(db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("model_radar_v1")
    return {"entries": RadarService.registry(db)}


@router.post("/radar/watchlist")
def radar_watchlist(body: WatchlistBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("model_radar_v1")
    try:
        return RadarService.add_to_watchlist(
            db, entry_id=body.entryId, project_id=body.projectId
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/compat/evaluate")
def compat_evaluate(body: CompatBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("model_radar_v1")
    try:
        return CompatService.evaluate(db, entry_id=body.entryId, env_profile=body.env)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox")
def sandbox_create(body: SandboxCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    return SandboxService.create(db, name=body.name, config=body.config)


@router.get("/sandbox/{sandbox_id}")
def sandbox_get(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    sb = SandboxService.get(db, sandbox_id)
    if not sb:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return sb


@router.post("/sandbox/{sandbox_id}/start")
def sandbox_start(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.start(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/{sandbox_id}/stop")
def sandbox_stop(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.stop(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/{sandbox_id}/restart")
def sandbox_restart(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.restart(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sandbox/{sandbox_id}/health")
def sandbox_health(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.health(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/{sandbox_id}/detect")
def sandbox_detect(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.detect(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/{sandbox_id}/validate")
def sandbox_validate(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.validate(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sandbox/{sandbox_id}/remove")
def sandbox_remove(sandbox_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.remove(db, sandbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/plan")
def sandbox_plan(body: PlanBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1", "model_radar_v1")
    try:
        return SandboxService.create_plan(
            db, sandbox_id=body.sandboxId, entry_id=body.entryId
        )
    except (LookupError, ValueError) as exc:
        code = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/sandbox/plan/{plan_id}/reject")
def sandbox_plan_reject(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return SandboxService.reject_plan(db, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sandbox/plan/{plan_id}/approve")
def sandbox_plan_approve(
    plan_id: str, body: PlanDecisionBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    if not _flag("production_executive_v1"):
        raise HTTPException(
            status_code=403,
            detail="Sandbox approve requires Production Executive (M2.7).",
        )
    try:
        return SandboxService.approve_plan(
            db, plan_id=plan_id, project_id=body.projectId, owner=body.owner
        )
    except (LookupError, ValueError) as exc:
        code = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/promote")
def promote_create(body: PromoteBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return PromoteService.create_proposal(db, sandbox_id=body.sandboxId)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/promote/{manifest_id}/reject")
def promote_reject(manifest_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    try:
        return PromoteService.reject(db, manifest_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/promote/{manifest_id}/approve")
def promote_approve(
    manifest_id: str, body: PromoteDecisionBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("sandbox_runtime_v1")
    if not _flag("production_executive_v1"):
        raise HTTPException(
            status_code=403,
            detail="Promotion approve requires Production Executive (M2.7).",
        )
    try:
        return PromoteService.approve(
            db,
            manifest_id=manifest_id,
            project_id=body.projectId,
            owner=body.owner,
            actor=body.actor,
        )
    except (LookupError, ValueError) as exc:
        code = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/routing/recommend")
def routing_recommend(body: RouteBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("model_radar_v1", "production_recipe_v1")
    return RoutingService.recommend(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        filmmaking_outcome=body.filmmakingOutcome,
        current_shot_model=body.currentShotModel,
        hardware=body.hardware,
    )


@router.post("/recipes")
def recipe_create(body: RecipeCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("production_recipe_v1")
    return RecipeService.create(
        db, project_id=body.projectId, name=body.name, stages=body.stages
    )


@router.get("/recipes/{recipe_id}")
def recipe_get(recipe_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("production_recipe_v1")
    recipe = RecipeService.get(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.post("/recipes/{recipe_id}/run")
def recipe_run(
    recipe_id: str, body: RecipeRunBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("production_recipe_v1")
    if not _flag("production_executive_v1"):
        raise HTTPException(
            status_code=403,
            detail="Recipe run requires Production Executive (M2.7).",
        )
    try:
        return RecipeService.run(
            db,
            recipe_id=recipe_id,
            simulate_failure_at=body.simulateFailureAt,
            owner=body.owner,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recipes/{recipe_id}/retry")
def recipe_retry(recipe_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("production_recipe_v1")
    try:
        return RecipeService.retry_failed(db, recipe_id=recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/shot-profiles")
def shot_profile_create(
    body: ShotProfileCreateBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("shot_profiles_v1")
    return ShotProfileService.create(
        db, project_id=body.projectId, name=body.name, payload=body.payload
    )


@router.get("/shot-profiles/{profile_id}")
def shot_profile_get(profile_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("shot_profiles_v1")
    profile = ShotProfileService.get(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Shot profile not found")
    return profile


@router.post("/shot-profiles/{profile_id}/save")
def shot_profile_save(
    profile_id: str, body: ShotProfileSaveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("shot_profiles_v1")
    try:
        return ShotProfileService.save_version(
            db, profile_id=profile_id, payload=body.payload, mode=body.mode
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/shot-profiles/{profile_id}/cinematic-depth")
def shot_profile_depth(
    profile_id: str, body: CinematicDepthBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("shot_profiles_v1")
    try:
        return ShotProfileService.apply_cinematic_depth(
            db,
            profile_id=profile_id,
            suggestions=body.suggestions,
            accept_ids=body.acceptIds,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/shot-profiles/{profile_id}/associate")
def shot_profile_associate(
    profile_id: str, body: AssociateBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("shot_profiles_v1")
    try:
        return ShotProfileService.associate(
            db,
            profile_id=profile_id,
            storyboard_shot_id=body.storyboardShotId,
            timeline_item_id=body.timelineItemId,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/shot-profiles/{profile_id}/export")
def shot_profile_export(profile_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("shot_profiles_v1")
    try:
        return ShotProfileService.export(db, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/virtual-stage")
def virtual_stage_create(
    body: StageCreateBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_virtual_stage_v11()
    return VirtualStageService.create(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        name=body.name,
        camera=body.camera,
    )


@router.get("/virtual-stage/{stage_id}")
def virtual_stage_get(stage_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_virtual_stage_v11()
    stage = VirtualStageService.get(db, stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Virtual stage not found")
    return stage


@router.post("/virtual-stage/{stage_id}/camera")
def virtual_stage_camera(
    stage_id: str, body: StageCameraBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_virtual_stage_v11()
    try:
        return VirtualStageService.update_camera(
            db, stage_id=stage_id, camera=body.camera
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/virtual-stage")
def virtual_stage_list(projectId: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_virtual_stage_v11()
    return {"stages": VirtualStageService.list_for_project(db, projectId)}


@router.post("/location-spin/plan")
def location_spin_plan(
    body: LocationPlanBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("location_spin_v1")
    return LocationSpinService.plan(
        db, project_id=body.projectId, location_name=body.locationName
    )


@router.post("/location-spin/{spin_id}/spin-camera")
def location_spin_camera(
    spin_id: str, body: SpinCameraBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require("location_spin_v1")
    try:
        return LocationSpinService.spin_camera(db, spin_id=spin_id, angles=body.angles)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
