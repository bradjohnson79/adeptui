"""PoseCraft REST router — project-scoped scene API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .schemas import PoseCraftCustomPose, PoseCraftDocument, PoseCraftExportPreview, PoseCraftRevision, PoseCraftScene, PoseCraftSnapshot
from ..codirector.pose_intelligence.router import router as pose_intelligence_router

router = APIRouter(prefix="/api/posecraft", tags=["posecraft"])
router.include_router(pose_intelligence_router)


def _to_http(exc: service.PoseCraftError) -> HTTPException:
    code = getattr(exc, "args", (None,))
    code_val = code[1] if len(code) > 1 and isinstance(code[1], int) else 400
    return HTTPException(status_code=code_val, detail=str(exc.args[0]) if exc.args else "PoseCraft error")


@router.get("/projects/{project_id}/scene", response_model=PoseCraftDocument)
def get_scene(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.load_scene(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.put("/projects/{project_id}/scene", response_model=PoseCraftDocument)
def put_scene(project_id: str, body: PoseCraftDocument, db: Session = Depends(get_db)):
    try:
        return service.save_scene(project_id, body, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/revisions", response_model=list[PoseCraftRevision])
def get_revisions(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_revisions(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/revisions", response_model=PoseCraftRevision)
def post_revision(project_id: str, body: PoseCraftRevision, db: Session = Depends(get_db)):
    try:
        return service.save_revision(project_id, body.label, body.scene, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/revisions/{revision_id}/restore", response_model=PoseCraftDocument)
def restore_revision(project_id: str, revision_id: str, db: Session = Depends(get_db)):
    try:
        return service.restore_revision(project_id, revision_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/export-preview", response_model=PoseCraftExportPreview)
def get_export_preview(project_id: str, snapshot_id: str | None = None, db: Session = Depends(get_db)):
    try:
        return service.build_export_preview(project_id, db, snapshot_id=snapshot_id)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


# --------------------------------------------------------------------------
# Snapshot CRUD — frozen camera-composition handoff artifacts. Snapshots are
# persisted on the PoseCraftDocument via the existing scene PUT (the client
# appends the frozen snapshot and flushes). These endpoints expose rename /
# duplicate / delete / select and a snapshot-aware export preview so Co-
# Director / Image Gen / Storyboard can read a frozen composition by id.
# --------------------------------------------------------------------------
@router.get("/projects/{project_id}/snapshots", response_model=list[PoseCraftSnapshot])
def list_snapshots_route(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_snapshots(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/snapshots/{snapshot_id}", response_model=PoseCraftSnapshot)
def get_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.get_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


class SnapshotRenameBody(BaseModel):
    name: str


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/rename", response_model=PoseCraftDocument)
def rename_snapshot_route(project_id: str, snapshot_id: str, body: SnapshotRenameBody, db: Session = Depends(get_db)):
    try:
        return service.rename_snapshot(project_id, snapshot_id, body.name, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/duplicate", response_model=PoseCraftDocument)
def duplicate_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.duplicate_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.delete("/projects/{project_id}/snapshots/{snapshot_id}", response_model=PoseCraftDocument)
def delete_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.delete_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


class SnapshotSelectBody(BaseModel):
    snapshotId: str | None = None


@router.post("/projects/{project_id}/snapshots/select", response_model=PoseCraftDocument)
def select_snapshot_route(project_id: str, body: SnapshotSelectBody, db: Session = Depends(get_db)):
    try:
        return service.select_snapshot(project_id, body.snapshotId, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


# Master Program Phase 15–20: project-scoped custom pose CRUD.
@router.get("/projects/{project_id}/poses", response_model=list[PoseCraftCustomPose])
def list_custom_poses(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_custom_poses(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/poses", response_model=PoseCraftCustomPose, status_code=201)
def create_custom_pose(project_id: str, body: PoseCraftCustomPose, db: Session = Depends(get_db)):
    try:
        return service.create_custom_pose(project_id, body.model_dump(), db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.put("/projects/{project_id}/poses/{pose_id}", response_model=PoseCraftCustomPose)
def update_custom_pose(project_id: str, pose_id: str, body: PoseCraftCustomPose, db: Session = Depends(get_db)):
    try:
        return service.update_custom_pose(project_id, pose_id, body.model_dump(), db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.delete("/projects/{project_id}/poses/{pose_id}", status_code=204)
def delete_custom_pose(project_id: str, pose_id: str, db: Session = Depends(get_db)):
    try:
        service.delete_custom_pose(project_id, pose_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


class ReconstructBody(BaseModel):
    sourceAssetId: str
    sourceType: str = "image"
    provider: str = "LOCAL_FIRE3D"


class ImportReconstructionBody(BaseModel):
    reconstructionId: str | None = None
    selectedObjectIds: list[str] | None = None
    includeFailed: bool = False
    environmentName: str | None = None
    ersEnvironmentName: str | None = None
    package: dict | None = None


class HandoffBody(BaseModel):
    snapshotId: str | None = None
    imageAssetId: str | None = None


class AutoPrevizPlanBody(BaseModel):
    description: str = ""
    ersEnvironmentName: str | None = None
    characterIds: list[str] = []
    shotCount: int = 4


class AutoPrevizExecuteBody(BaseModel):
    planId: str
    approved: bool = False


@router.post("/projects/{project_id}/reconstruct")
def start_reconstruct(project_id: str, body: ReconstructBody, db: Session = Depends(get_db)):
    from .reconstruction.runtime import ReconstructionRuntime

    project = service.load_scene(project_id, db)
    _ = project
    runtime = ReconstructionRuntime()
    job = runtime.start(
        project_id=project_id,
        source_asset_id=body.sourceAssetId,
        source_type=body.sourceType,
        provider=body.provider,
    )
    return job.model_dump()


@router.get("/projects/{project_id}/reconstruct/{job_id}")
def get_reconstruct(project_id: str, job_id: str):
    from .reconstruction.runtime import ReconstructionRuntime

    job = ReconstructionRuntime().get(job_id)
    if job is None or job.projectId != project_id:
        raise HTTPException(status_code=404, detail="Reconstruction job not found")
    return job.model_dump()


@router.post("/projects/{project_id}/import-reconstruction", response_model=PoseCraftDocument)
def import_reconstruction_route(project_id: str, body: ImportReconstructionBody, db: Session = Depends(get_db)):
    from .import_adapter import import_reconstruction
    from .reconstruction.contracts import Fire3DReconstructionPackage
    from .reconstruction.runtime import ReconstructionRuntime

    try:
        doc = service.load_scene(project_id, db)
        package = None
        if body.package:
            package = Fire3DReconstructionPackage.model_validate(body.package)
        elif body.reconstructionId:
            job = ReconstructionRuntime().get(body.reconstructionId)
            package = job.package if job else None
        if package is None:
            raise service.PoseCraftError("Reconstruction package not found", 404)
        doc.currentScene = import_reconstruction(
            doc.currentScene,
            package,
            selected_object_ids=body.selectedObjectIds,
            include_failed=body.includeFailed,
            environment_name=body.environmentName,
            ers_environment_name=body.ersEnvironmentName,
        )
        return service.save_scene(project_id, doc, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/handoff/image-generator", response_model=PoseCraftDocument)
def handoff_image_generator(project_id: str, body: HandoffBody, db: Session = Depends(get_db)):
    try:
        doc = service.load_scene(project_id, db)
        snap_id = body.snapshotId or doc.selectedSnapshotId
        if snap_id:
            snap = service.get_snapshot(project_id, snap_id, db)
            if body.imageAssetId and snap.imageAssetId != body.imageAssetId:
                raise service.PoseCraftError("imageAssetId does not match the selected Snapshot", 400)
        doc.igHandoffSnapshotId = snap_id
        return service.save_scene(project_id, doc, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/handoff/image-generator")
def get_ig_handoff(project_id: str, db: Session = Depends(get_db)):
    try:
        doc = service.load_scene(project_id, db)
        snap = None
        if doc.igHandoffSnapshotId:
            snap = service.get_snapshot(project_id, doc.igHandoffSnapshotId, db)
        return {
            "snapshotId": doc.igHandoffSnapshotId,
            "imageAssetId": snap.imageAssetId if snap else None,
            "name": snap.name if snap else None,
            "honestyLabel": "PoseCraft Snapshot — Visual Staging Reference",
        }
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/auto-previz/plan")
def auto_previz_plan(project_id: str, body: AutoPrevizPlanBody, db: Session = Depends(get_db)):
    from .auto_previz import store_plan

    try:
        doc = service.load_scene(project_id, db)
        scene = doc.currentScene
        count = max(2, min(int(body.shotCount or 4), 8))
        names = [f.name for f in scene.figures[:3]] or ["the lead", "the second figure"]
        plan = {
            "planId": f"previz-{scene.revision}-{uuid.uuid4().hex[:8]}",
            "description": body.description,
            "ersEnvironmentName": body.ersEnvironmentName or (scene.environment.ersEnvironmentName if scene.environment else None),
            "approved": False,
            "shots": [],
        }
        templates = [
            ("Shot 01 — Establishing wide", "stage"),
            ("Shot 02 — Medium", "figure"),
            (f"Shot 03 — {names[0]} close-up", "face"),
            (f"Shot 04 — {names[-1]} reverse", "figure"),
        ]
        for index in range(count):
            title, kind = templates[index % len(templates)]
            plan["shots"].append({"name": title, "focusKind": kind, "index": index + 1})
        return store_plan(project_id, plan)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/auto-previz/execute", response_model=PoseCraftDocument)
def auto_previz_execute(project_id: str, body: AutoPrevizExecuteBody, db: Session = Depends(get_db)):
    from . import scene_ops
    from .auto_previz import approve_plan, get_plan

    if not body.approved:
        raise HTTPException(status_code=409, detail="Auto Previz requires creator approval of the shot plan.")
    plan = get_plan(body.planId)
    if plan is None or plan.get("projectId") != project_id:
        raise HTTPException(status_code=404, detail="Auto Previz plan not found. Draft a plan first.")
    approve_plan(body.planId, project_id)
    try:
        doc = service.load_scene(project_id, db)
        scene = doc.currentScene
        for shot in plan.get("shots") or []:
            scene_ops.focus_subject(scene, kind=shot.get("focusKind") or "stage", subject_id=scene.figures[0].id if scene.figures else None)
            scene_ops.save_shot(scene, str(shot.get("name") or "Shot"))
        doc.currentScene = scene
        return service.save_scene(project_id, doc, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc
