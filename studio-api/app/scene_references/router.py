"""HTTP API for Scene Reference Bindings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db

from . import service
from .production_gate import evaluate_m42_w6p_scene_reference_gate
from .schemas import (
    ApplyRequest,
    CopyFromSceneRequest,
    PreflightRequest,
    ReorderRequest,
    ResolveRequest,
    SceneReferenceBindingCreate,
    SceneReferenceBindingUpdate,
)

router = APIRouter(tags=["scene-references"])


@router.get("/m42-product/gate/wave6p/scene-references")
def scene_reference_gate():
    g = evaluate_m42_w6p_scene_reference_gate()
    return {**g, "ok": bool(g.get("sceneReferenceAddendumGo")), "passed": bool(g.get("sceneReferenceAddendumGo"))}


@router.get("/scene-references/capabilities")
def get_capabilities():
    return {"items": service.capabilities()}


@router.get("/projects/{project_id}/references")
def list_references(
    project_id: str,
    scope_type: str | None = None,
    scope_id: str | None = None,
    include_inherited: bool = Query(False),
    sequence_id: str | None = None,
    scene_id: str | None = None,
    shot_id: str | None = None,
    db: Session = Depends(get_db),
):
    if scope_type and scope_id:
        items = service.list_for_scope(
            db,
            project_id,
            scope_type,
            scope_id,
            include_inherited=include_inherited,
            sequence_id=sequence_id,
            scene_id=scene_id,
            shot_id=shot_id,
        )
    else:
        from . import repository as repo
        from .permissions import require_project

        require_project(db, project_id)
        items = [repo.binding_to_dict(r) for r in repo.list_bindings(db, project_id)]
    return {"items": items, "count": len(items)}


@router.post("/projects/{project_id}/references")
def create_reference(
    project_id: str,
    body: SceneReferenceBindingCreate,
    db: Session = Depends(get_db),
):
    return service.attach(db, project_id, body.model_dump(), actor="user")


@router.patch("/projects/{project_id}/references/{binding_id}")
def patch_reference(
    project_id: str,
    binding_id: str,
    body: SceneReferenceBindingUpdate,
    db: Session = Depends(get_db),
):
    return service.update(db, project_id, binding_id, body.model_dump(exclude_unset=True), actor="user")


@router.delete("/projects/{project_id}/references/{binding_id}")
def delete_reference(project_id: str, binding_id: str, db: Session = Depends(get_db)):
    return service.remove(db, project_id, binding_id, actor="user")


@router.post("/projects/{project_id}/references/reorder")
def reorder_references(project_id: str, body: ReorderRequest, db: Session = Depends(get_db)):
    return {"items": service.reorder(db, project_id, body.binding_ids, actor="user")}


@router.post("/projects/{project_id}/references/copy")
def copy_references(project_id: str, body: CopyFromSceneRequest, db: Session = Depends(get_db)):
    items = service.copy_scope(
        db,
        project_id,
        source_scope_type=body.source_scope_type,
        source_scope_id=body.source_scope_id,
        target_scope_type=body.target_scope_type,
        target_scope_id=body.target_scope_id,
        actor="user",
    )
    return {"items": items, "count": len(items)}


@router.post("/projects/{project_id}/references/apply")
def apply_references(project_id: str, body: ApplyRequest, db: Session = Depends(get_db)):
    return service.apply_to_scopes(
        db,
        project_id,
        body.binding_ids,
        body.target_scopes,
        mode=body.mode,
        actor="user",
    )


@router.post("/projects/{project_id}/references/resolve")
def resolve_references(project_id: str, body: ResolveRequest, db: Session = Depends(get_db)):
    items = service.list_for_scope(
        db,
        project_id,
        body.scope_type,
        body.scope_id,
        include_inherited=body.include_inherited,
    )
    return {"items": items, "count": len(items)}


@router.get("/projects/{project_id}/references/readiness")
def reference_readiness(
    project_id: str,
    scope_type: str,
    scope_id: str,
    workflow_key: str,
    db: Session = Depends(get_db),
):
    return service.readiness(db, project_id, scope_type, scope_id, workflow_key)


@router.post("/projects/{project_id}/references/preflight")
def reference_preflight(project_id: str, body: PreflightRequest, db: Session = Depends(get_db)):
    return service.preflight(
        db,
        project_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        workflow_key=body.workflow_key,
        override_binding_ids=body.override_binding_ids,
    )


@router.get("/projects/{project_id}/references/assets/{asset_id}/usage")
def asset_reference_usage(project_id: str, asset_id: str, db: Session = Depends(get_db)):
    return service.asset_usage(db, project_id, asset_id)
