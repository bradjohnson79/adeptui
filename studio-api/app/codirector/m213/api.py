"""FastAPI routes for Co-Director M2.13 Virtual Environment Studio."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from . import blocking as blocking_mod
from . import camera_spin
from . import concepts
from . import persistence
from . import protocol
from . import reconstruction
from . import scene_state
from . import theme as theme_mod
from .flags import FLAG_NAME, virtual_environment_studio_enabled
from .kinds import ASSET_KINDS, CAPABILITY_IDS
from .route_b import approve_environment, normalize_and_register
from .safety import assert_manifest_unchanged, safety_contract
from .store import M213Store

router = APIRouter(prefix="/m213", tags=["codirector-m213"])


def _flag() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))


def _require() -> None:
    if _flag():
        return
    raise HTTPException(status_code=404, detail="M2.13 virtual environment studio capability is not enabled.")


class ImportBody(BaseModel):
    projectId: str
    sourcePath: str
    title: str = "Imported Environment"
    sceneId: Optional[str] = None
    fixture: bool = False


class SpinBody(BaseModel):
    projectId: str
    title: str = "Camera Spin Environment"
    level: str = "C1_panorama"
    fixture: bool = True
    sceneId: Optional[str] = None
    frames: Optional[list[dict[str, Any]]] = None


class ReconstructBody(BaseModel):
    projectId: str
    images: Optional[list[str]] = None
    adapter: str = "fixture"
    title: str = "Reconstructed Environment"
    sceneId: Optional[str] = None
    force: bool = False


class ApproveBody(BaseModel):
    actor: str = "user"
    note: str = ""


class ThemeBody(BaseModel):
    projectId: str
    name: str
    profile: dict[str, Any] = Field(default_factory=dict)
    environmentId: Optional[str] = None
    recommended: bool = False


class BlockingBody(BaseModel):
    projectId: str
    environmentId: str
    state: Optional[dict[str, Any]] = None
    presetId: Optional[str] = None
    surface: str = "floor_plan"


class SceneStateBody(BaseModel):
    projectId: str
    environmentId: str
    kind: str
    state: Optional[dict[str, Any]] = None
    preset: Optional[str] = None


class PlanBody(BaseModel):
    projectId: str
    environmentId: Optional[str] = None
    mode: str = "guided"


class AdvanceBody(BaseModel):
    toStage: Optional[str] = None
    recordApprovalGate: Optional[str] = None
    subjectId: Optional[str] = None
    actor: str = "user"
    note: str = ""


class ConceptBody(BaseModel):
    projectId: str
    environmentId: str
    tier: str = "draft"
    forceMock: Optional[bool] = True


class PublishBody(BaseModel):
    projectId: str
    conceptIds: list[str]
    selective: bool = False


class RestoreBody(BaseModel):
    projectId: str
    environmentId: str
    restore: dict[str, int] = Field(default_factory=dict)
    keep: dict[str, int] = Field(default_factory=dict)


class CapabilityBody(BaseModel):
    projectId: Optional[str] = None
    capabilityId: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    reversible: bool = True


class E2EBody(BaseModel):
    projectId: str
    fixture: bool = True


@router.get("/status")
async def m213_status() -> dict[str, Any]:
    digest = assert_manifest_unchanged()
    return {
        "enabled": virtual_environment_studio_enabled(),
        "flag": FLAG_NAME,
        "flagDefault": False,
        "safety": safety_contract(),
        "manifestSha256": digest,
        "assetKinds": list(ASSET_KINDS),
        "capabilityIds": [
            {"id": c[0], "displayName": c[1], "baselineStatus": c[2]} for c in CAPABILITY_IDS
        ],
        "routes": ["imported_3d", "camera_spin", "reconstruction"],
        "vpcSpecialist": "virtual-production-coordinator",
        "adapters": reconstruction.list_adapters(),
    }


@router.get("/safety")
async def m213_safety() -> dict[str, Any]:
    return {**safety_contract(), "manifestSha256": assert_manifest_unchanged()}


@router.post("/import")
async def m213_import(body: ImportBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return normalize_and_register(
        db,
        project_id=body.projectId,
        source_path=body.sourcePath,
        title=body.title,
        scene_id=body.sceneId,
        fixture=body.fixture,
    )


@router.post("/environments/{environment_id}/approve")
async def m213_approve_env(
    environment_id: str, body: ApproveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return approve_environment(db, environment_id=environment_id, actor=body.actor, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/camera-spin")
async def m213_camera_spin(body: SpinBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return camera_spin.build_camera_spin_environment(
        db,
        project_id=body.projectId,
        title=body.title,
        level=body.level,
        frames=body.frames,
        fixture=body.fixture,
        scene_id=body.sceneId,
    )


@router.get("/reconstruction/adapters")
async def m213_adapters() -> dict[str, Any]:
    _require()
    return {"adapters": reconstruction.list_adapters(), "silentInstall": False}


@router.post("/reconstruction/assess")
async def m213_assess(body: ReconstructBody) -> dict[str, Any]:
    _require()
    return reconstruction.assess_capture(body.images, fixture=body.adapter == "fixture").to_dict()


@router.post("/reconstruction")
async def m213_reconstruct(body: ReconstructBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return reconstruction.reconstruct_environment(
        db,
        project_id=body.projectId,
        images=body.images,
        adapter_name=body.adapter,
        title=body.title,
        scene_id=body.sceneId,
        force=body.force,
    )


@router.get("/themes/recommend")
async def m213_theme_recommend(style: str = Query("")) -> dict[str, Any]:
    _require()
    return {"themes": theme_mod.recommend_themes(style)}


@router.post("/themes")
async def m213_theme_create(body: ThemeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return theme_mod.persist_theme(
        db,
        project_id=body.projectId,
        name=body.name,
        profile=body.profile,
        environment_id=body.environmentId,
        recommended=body.recommended,
    )


@router.post("/themes/{theme_id}/approve")
async def m213_theme_approve(
    theme_id: str, body: ApproveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return theme_mod.approve_theme(db, theme_id=theme_id, actor=body.actor, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/themes/preview-compare")
async def m213_theme_compare(body: dict[str, Any]) -> dict[str, Any]:
    _require()
    return theme_mod.preview_compare(body.get("a") or {}, body.get("b") or {})


@router.post("/blocking")
async def m213_blocking_save(body: BlockingBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    state = body.state or blocking_mod.empty_blocking_state(surface=body.surface)
    if body.presetId:
        state = blocking_mod.apply_preset(state, body.presetId)
    return blocking_mod.save_blocking(
        db, project_id=body.projectId, environment_id=body.environmentId, state=state
    )


@router.post("/blocking/{blocking_id}/approve")
async def m213_blocking_approve(
    blocking_id: str, body: ApproveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return blocking_mod.approve_blocking(db, blocking_id=blocking_id, actor=body.actor, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scene-state")
async def m213_scene_state(body: SceneStateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    if body.kind == "camera":
        state = body.state or scene_state.default_camera_state()
    elif body.kind == "lighting":
        state = body.state or scene_state.default_lighting_state(body.preset or "three_point")
    else:
        raise HTTPException(status_code=400, detail="kind must be camera or lighting")
    return scene_state.save_scene_state(
        db,
        project_id=body.projectId,
        environment_id=body.environmentId,
        kind=body.kind,
        state=state,
    )


@router.post("/scene-state/{state_id}/approve")
async def m213_scene_state_approve(
    state_id: str, body: ApproveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return scene_state.approve_scene_state(db, state_id=state_id, actor=body.actor, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans")
async def m213_plan_create(body: PlanBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return protocol.create_plan(
        db, project_id=body.projectId, environment_id=body.environmentId, mode=body.mode
    )


@router.get("/plans/{plan_id}")
async def m213_plan_get(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    plan = protocol.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    return plan


@router.post("/plans/{plan_id}/advance")
async def m213_plan_advance(
    plan_id: str, body: AdvanceBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return protocol.advance_plan(
            db,
            plan_id=plan_id,
            to_stage=body.toStage,
            record_approval_gate=body.recordApprovalGate,
            subject_id=body.subjectId,
            actor=body.actor,
            note=body.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/plans/{plan_id}/dashboard")
async def m213_plan_dashboard(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    plan = protocol.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    return protocol.coordination_dashboard(plan)


@router.post("/concepts")
async def m213_concept(body: ConceptBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return concepts.generate_concept(
        db,
        project_id=body.projectId,
        environment_id=body.environmentId,
        tier=body.tier,
        force_mock=body.forceMock,
    )


@router.post("/concepts/{concept_id}/approve")
async def m213_concept_approve(
    concept_id: str, body: ApproveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return concepts.approve_concept(db, concept_id=concept_id, actor=body.actor, note=body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/timeline/publish")
async def m213_publish(body: PublishBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return concepts.publish_to_timeline(
        db, project_id=body.projectId, concept_ids=body.conceptIds, selective=body.selective
    )


@router.post("/restore")
async def m213_restore(body: RestoreBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return persistence.selective_restore(
        db,
        project_id=body.projectId,
        environment_id=body.environmentId,
        restore=body.restore,
        keep=body.keep,
    )


@router.get("/recovery")
async def m213_recovery(projectId: str = Query(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return persistence.restart_recovery(db, project_id=projectId)


@router.post("/capabilities/invoke")
async def m213_cap_invoke(body: CapabilityBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    known = {c[0] for c in CAPABILITY_IDS}
    if body.capabilityId not in known:
        raise HTTPException(status_code=400, detail=f"unknown capability {body.capabilityId}")
    log = M213Store.log_capability(
        db,
        capability_id=body.capabilityId,
        action=body.action,
        project_id=body.projectId,
        payload=body.payload,
        reversible=body.reversible,
    )
    return {"ok": True, "logged": log, "schemaValidated": True, "reversible": body.reversible}


@router.post("/e2e/guided")
async def m213_e2e(body: E2EBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return persistence.end_to_end_guided(db, project_id=body.projectId, fixture=body.fixture)
