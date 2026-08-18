from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .scene_creator_mini import (
    MiniRegenerateBody,
    MiniSendBody,
    MiniTakeCreateBody,
)
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
    SpatialPropAttachBody,
    SpatialPropPlacementBody,
    SpatialPropPlacementUpdateBody,
    SpatialPropRelationshipUpdateBody,
    Spatial360ViewUpsertBody,
    SpatialVariantCreateBody,
)
from .service import (
    build_reference_bundle,
    commit_document,
    consistency_check,
    create_camera,
    create_capture_plan,
    create_collage,
    create_document,
    create_path,
    create_variant,
    get_document,
    list_documents,
    attach_prop,
    place_character,
    place_prop,
    remove_camera,
    remove_character,
    remove_prop,
    assign_to_scene,
    detach_prop,
    update_camera,
    update_character,
    update_collage_view,
    update_document,
    update_prop,
    update_prop_relationship,
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


@router.post("/projects/{project_id}/maps/{document_id}/save")
def api_commit_map(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Explicit Save Spatial Map commit. Stamps savedAt + savedVersion.

    The frontend gates 'Use in Scene Creator' on savedVersion == version, so
    this is the authoritative commit boundary; it is never called implicitly.
    """
    return {"document": commit_document(db, project_id, document_id).model_dump()}


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
    detachAttachedProps: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "document": remove_character(
            db,
            project_id,
            document_id,
            placement_id,
            detach_attached_props=detachAttachedProps,
        ).model_dump()
    }


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


@router.post("/projects/{project_id}/maps/{document_id}/props/{placement_id}/attach")
def api_attach_prop(
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropAttachBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": attach_prop(db, project_id, document_id, placement_id, body).model_dump()}


@router.post("/projects/{project_id}/maps/{document_id}/props/{placement_id}/detach")
def api_detach_prop(
    project_id: str,
    document_id: str,
    placement_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"document": detach_prop(db, project_id, document_id, placement_id).model_dump()}


@router.patch("/projects/{project_id}/maps/{document_id}/props/{placement_id}/relationship")
def api_update_prop_relationship(
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropRelationshipUpdateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "document": update_prop_relationship(db, project_id, document_id, placement_id, body).model_dump()
    }


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


@router.get("/projects/{project_id}/maps/{document_id}/mini-take/preview")
def api_mini_take_preview(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .scene_creator_mini import active_cameras_for_document, latest_mini_take, mini_output_count

    document = get_document(db, project_id, document_id)
    compiled = active_cameras_for_document(document)
    saved = bool(document.savedVersion) and document.savedVersion == document.version
    count = int(compiled.get("count") or 0)
    latest = latest_mini_take(project_id, document_id)
    return {
        "saved": saved,
        "isDirty": not saved,
        "cameraCount": count,
        "outputCount": mini_output_count(count),
        "labels": list(compiled.get("labels") or []),
        "cameras": list(compiled.get("cameras") or []),
        "latestTakeId": (latest or {}).get("id"),
    }


@router.post("/projects/{project_id}/maps/{document_id}/mini-take")
def api_create_mini_take(
    project_id: str,
    document_id: str,
    body: MiniTakeCreateBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .scene_creator_mini import create_mini_take

    parsed = body or MiniTakeCreateBody()
    return {"take": create_mini_take(db, project_id, document_id, parsed)}


@router.get("/projects/{project_id}/maps/{document_id}/mini-take/{take_id}")
def api_get_mini_take(
    project_id: str,
    document_id: str,
    take_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .scene_creator_mini import get_mini_take

    return {"take": get_mini_take(db, project_id, take_id)}


@router.post("/projects/{project_id}/maps/{document_id}/mini-take/{take_id}/regenerate")
def api_regenerate_mini_take(
    project_id: str,
    document_id: str,
    take_id: str,
    body: MiniRegenerateBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .scene_creator_mini import regenerate_mini

    return {"take": regenerate_mini(db, project_id, document_id, take_id, body or MiniRegenerateBody())}


@router.post("/projects/{project_id}/maps/{document_id}/mini-take/{take_id}/send-to-library")
def api_send_mini_to_library(
    project_id: str,
    document_id: str,
    take_id: str,
    body: MiniSendBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .scene_creator_mini import send_selected_to_library

    return {"take": send_selected_to_library(db, project_id, take_id, body or MiniSendBody())}


class CameraReferenceGenerateBody(BaseModel):
    generator: Literal["qwen2512", "gpt-image-2"] = "qwen2512"


@router.get("/projects/{project_id}/maps/{document_id}/camera-references")
def api_list_camera_references(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .camera_reference import list_refs
    from .service import get_document

    document = get_document(db, project_id, document_id)
    return list_refs(db, project_id, document)


@router.post("/projects/{project_id}/maps/{document_id}/camera-references/{camera_id}")
def api_generate_camera_reference(
    project_id: str,
    document_id: str,
    camera_id: str,
    body: CameraReferenceGenerateBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .camera_reference import enqueue_camera_ref
    from .service import get_document

    document = get_document(db, project_id, document_id)
    camera = next(
        (c for c in getattr(document, "cameras", None) or [] if str(getattr(c, "id", "") or "") == camera_id),
        None,
    )
    if camera is None:
        raise HTTPException(404, "Camera not found in this Spatial Map.")
    generator = (body.generator if body is not None else "qwen2512") or "qwen2512"
    record = enqueue_camera_ref(db, project_id, document, camera, generator)
    return {"reference": record}
