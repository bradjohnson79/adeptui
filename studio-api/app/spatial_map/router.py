from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .schemas import (
    SpatialAssignSceneBody,
    SpatialCameraCreateBody,
    SpatialCameraUpdateBody,
    SpatialCapturePlanBody,
    SpatialCharacterPlacementBody,
    SpatialCharacterPlacementUpdateBody,
    SpatialCollageCreateBody,
    SpatialMapCreateBody,
    SpatialMapUpdateBody,
    SpatialMovementPathCreateBody,
    SpatialPropPlacementBody,
    SpatialPropPlacementUpdateBody,
    Spatial360ViewUpsertBody,
    SpatialVariantCreateBody,
)
from .service import (
    build_reference_bundle,
    consistency_check,
    create_camera,
    create_capture_plan,
    create_collage,
    create_document,
    create_path,
    create_variant,
    get_document,
    list_documents,
    place_character,
    place_prop,
    remove_camera,
    remove_character,
    remove_prop,
    assign_to_scene,
    update_camera,
    update_character,
    update_collage_view,
    update_document,
    update_prop,
)

router = APIRouter(prefix="/spatial-map", tags=["spatial-map-m411"])


@router.get("/projects/{project_id}/maps")
def api_list_maps(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"documents": [item.model_dump() for item in list_documents(db, project_id)]}


@router.post("/projects/{project_id}/maps")
def api_create_map(project_id: str, body: SpatialMapCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"document": create_document(db, project_id, body).model_dump()}


@router.get("/projects/{project_id}/maps/{document_id}")
def api_get_map(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"document": get_document(db, project_id, document_id).model_dump()}


@router.patch("/projects/{project_id}/maps/{document_id}")
def api_update_map(
    project_id: str,
    document_id: str,
    body: SpatialMapUpdateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": update_document(db, project_id, document_id, body).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/characters")
def api_place_character(
    project_id: str,
    document_id: str,
    body: SpatialCharacterPlacementBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": place_character(db, project_id, document_id, body).model_dump()}


@router.patch("/projects/{project_id}/maps/{document_id}/characters/{placement_id}")
def api_update_character(
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialCharacterPlacementUpdateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": update_character(db, project_id, document_id, placement_id, body).model_dump()}


@router.delete("/projects/{project_id}/maps/{document_id}/characters/{placement_id}")
def api_remove_character(
    project_id: str,
    document_id: str,
    placement_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": remove_character(db, project_id, document_id, placement_id).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/props")
def api_place_prop(
    project_id: str,
    document_id: str,
    body: SpatialPropPlacementBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": place_prop(db, project_id, document_id, body).model_dump()}


@router.patch("/projects/{project_id}/maps/{document_id}/props/{placement_id}")
def api_update_prop(
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropPlacementUpdateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": update_prop(db, project_id, document_id, placement_id, body).model_dump()}


@router.delete("/projects/{project_id}/maps/{document_id}/props/{placement_id}")
def api_remove_prop(
    project_id: str,
    document_id: str,
    placement_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": remove_prop(db, project_id, document_id, placement_id).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/cameras")
def api_create_camera(
    project_id: str,
    document_id: str,
    body: SpatialCameraCreateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": create_camera(db, project_id, document_id, body).model_dump()}


@router.patch("/projects/{project_id}/maps/{document_id}/cameras/{camera_id}")
def api_update_camera(
    project_id: str,
    document_id: str,
    camera_id: str,
    body: SpatialCameraUpdateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": update_camera(db, project_id, document_id, camera_id, body).model_dump()}


@router.delete("/projects/{project_id}/maps/{document_id}/cameras/{camera_id}")
def api_remove_camera(
    project_id: str,
    document_id: str,
    camera_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": remove_camera(db, project_id, document_id, camera_id).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/paths")
def api_create_path(
    project_id: str,
    document_id: str,
    body: SpatialMovementPathCreateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": create_path(db, project_id, document_id, body).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/assign-scene")
def api_assign_scene(
    project_id: str,
    document_id: str,
    body: SpatialAssignSceneBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": assign_to_scene(db, project_id, document_id, body).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/variants")
def api_create_variant(
    project_id: str,
    document_id: str,
    body: SpatialVariantCreateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": create_variant(db, project_id, document_id, body).model_dump()}


@router.get("/projects/{project_id}/maps/{document_id}/reference-bundle")
def api_reference_bundle(
    project_id: str,
    document_id: str,
    target: str = "image",
    cameraId: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "bundle": build_reference_bundle(
            db,
            project_id,
            document_id,
            target=target,
            camera_id=cameraId,
        ).model_dump()
    }


@router.post("/projects/{project_id}/maps/{document_id}/collage")
def api_create_collage(
    project_id: str,
    document_id: str,
    body: SpatialCollageCreateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": create_collage(db, project_id, document_id, body).model_dump()}


@router.put("/projects/{project_id}/maps/{document_id}/collage/views/{direction}")
def api_upsert_collage_view(
    project_id: str,
    document_id: str,
    direction: str,
    body: Spatial360ViewUpsertBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "document": update_collage_view(
            db,
            project_id,
            document_id,
            direction=direction,
            asset_id=body.assetId,
            prompt=body.prompt,
            status=body.status,
        ).model_dump()
    }


@router.post("/projects/{project_id}/maps/{document_id}/capture-plan")
def api_capture_plan(
    project_id: str,
    document_id: str,
    body: SpatialCapturePlanBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"plan": create_capture_plan(db, project_id, document_id, body).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/consistency-check")
def api_consistency_check(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return consistency_check(db, project_id, document_id).model_dump()
