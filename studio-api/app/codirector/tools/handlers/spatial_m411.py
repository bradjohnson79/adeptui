"""M4.11 Co-Director spatial.* tools for creator-friendly map intelligence."""

from __future__ import annotations

import json
import math
from typing import Any

from ....spatial_map import service as spatial_service
from ....spatial_map.collage import YAW_BY_DIRECTION
from ....spatial_map.reference_bundle import creative_position_labels
from ....spatial_map.schemas import (
    SpatialAssignSceneBody,
    SpatialBounds,
    SpatialCamera,
    SpatialCameraCreateBody,
    SpatialCapturePlanBody,
    SpatialCharacterPlacement,
    SpatialCharacterPlacementBody,
    SpatialCollageCreateBody,
    SpatialMapCreateBody,
    SpatialMapDocument,
    SpatialMapUpdateBody,
    SpatialMovementPathCreateBody,
    SpatialMovementWaypoint,
    SpatialPropPlacement,
    SpatialPropPlacementBody,
)
from ..definitions import ToolContext, ToolPreview


def _string(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def _required_string(args: dict[str, Any], key: str) -> str:
    value = _string(args, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _number(args: dict[str, Any], key: str, default: float | None = None) -> float | None:
    value = args.get(key)
    if value in (None, ""):
        return default
    return float(value)


def _csv_list(args: dict[str, Any], key: str) -> list[str]:
    raw = _string(args, key)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _json_array_arg(args: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = args.get(key)
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        if not all(isinstance(item, dict) for item in raw):
            raise ValueError(f"{key} must be a list of objects.")
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} must be valid JSON.") from exc
        if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
            raise ValueError(f"{key} must decode to a list of objects.")
        return parsed
    raise ValueError(f"{key} must be a JSON array or JSON string.")


def _document(ctx: ToolContext, args: dict[str, Any]) -> SpatialMapDocument:
    return spatial_service.get_document(ctx.db, ctx.project_id, _required_string(args, "documentId"))


def _persist_document(
    ctx: ToolContext,
    document_id: str,
    mutator,
) -> SpatialMapDocument:
    row = spatial_service._row_or_404(ctx.db, ctx.project_id, document_id)
    document = spatial_service._parse_document(row)
    mutator(document)
    return spatial_service._save_document(ctx.db, row, document)


def _bounds_from_args(args: dict[str, Any]) -> SpatialBounds:
    return SpatialBounds(
        coordinateSystem=_string(args, "coordinateSystem") or "adept-world-v1",
        minX=float(args.get("minX", -5.0)),
        maxX=float(args.get("maxX", 5.0)),
        minY=float(args.get("minY", 0.0)),
        maxY=float(args.get("maxY", 3.0)),
        minZ=float(args.get("minZ", -5.0)),
        maxZ=float(args.get("maxZ", 5.0)),
    )


def _camera_for_document(document: SpatialMapDocument, camera_id: str | None) -> SpatialCamera | None:
    if camera_id:
        return next((camera for camera in document.cameras if camera.id == camera_id), None)
    return next((camera for camera in document.cameras if camera.hero), None) or (
        document.cameras[0] if document.cameras else None
    )


def _all_subjects(
    document: SpatialMapDocument,
) -> list[tuple[str, SpatialCharacterPlacement | SpatialPropPlacement]]:
    return [("character", item) for item in document.characters] + [("prop", item) for item in document.props]


def _resolve_subject(
    document: SpatialMapDocument,
    *,
    target_type: str,
    target_id: str,
) -> tuple[str, SpatialCharacterPlacement | SpatialPropPlacement | SpatialCamera | None]:
    if target_type == "character":
        item = next(
            (
                character
                for character in document.characters
                if character.id == target_id or character.characterId == target_id
            ),
            None,
        )
        return ("character", item)
    if target_type == "prop":
        item = next(
            (prop for prop in document.props if prop.id == target_id or (prop.propId and prop.propId == target_id)),
            None,
        )
        return ("prop", item)
    if target_type == "camera":
        return ("camera", next((camera for camera in document.cameras if camera.id == target_id), None))
    item = next(
        (subject for _kind, subject in _all_subjects(document) if subject.id == target_id),
        None,
    )
    if item is None:
        item = next((camera for camera in document.cameras if camera.id == target_id), None)
        if item is not None:
            return ("camera", item)
    if isinstance(item, SpatialCharacterPlacement):
        return ("character", item)
    if isinstance(item, SpatialPropPlacement):
        return ("prop", item)
    return ("unknown", None)


def _label_for_subject(kind: str, subject: SpatialCharacterPlacement | SpatialPropPlacement | SpatialCamera) -> str:
    if kind == "camera":
        return subject.label or "Camera"
    return subject.label or ("Character" if kind == "character" else "Prop")


def _direction_for_yaw(yaw_degrees: float) -> str:
    required = [
        "front",
        "front_right",
        "right",
        "rear_right",
        "rear",
        "rear_left",
        "left",
        "front_left",
    ]
    best = required[0]
    best_delta = 360.0
    for direction in required:
        delta = abs(_angle_delta(yaw_degrees, float(YAW_BY_DIRECTION[direction])))
        if delta < best_delta:
            best = direction
            best_delta = delta
    return best


def _horizontal_fov(lens_mm: float) -> float:
    safe_lens = max(lens_mm, 1.0)
    return max(18.0, min(100.0, math.degrees(2.0 * math.atan(36.0 / (2.0 * safe_lens)))))


def _vertical_fov(lens_mm: float) -> float:
    safe_lens = max(lens_mm, 1.0)
    return max(12.0, min(80.0, math.degrees(2.0 * math.atan(24.0 / (2.0 * safe_lens)))))


def _angle_delta(actual: float, expected: float) -> float:
    return ((actual - expected + 180.0) % 360.0) - 180.0


def _outside_bounds(document: SpatialMapDocument, *, x: float, y: float, z: float) -> bool:
    bounds = document.bounds
    return not (bounds.minX <= x <= bounds.maxX and bounds.minY <= y <= bounds.maxY and bounds.minZ <= z <= bounds.maxZ)


def _visibility_details(
    document: SpatialMapDocument,
    camera: SpatialCamera | None,
    kind: str,
    subject: SpatialCharacterPlacement | SpatialPropPlacement | SpatialCamera | None,
) -> dict[str, Any]:
    if camera is None:
        return {"visibility": "unknown", "reason": "No camera is placed on this map yet."}
    if subject is None:
        return {"visibility": "unknown", "reason": "The requested subject is not on this map."}
    if kind == "camera":
        return {
            "visibility": "unknown",
            "reason": "Cameras are reference viewpoints, not visibility subjects.",
            "subjectId": subject.id,
            "subjectLabel": subject.label,
        }

    dx = float(subject.x - camera.x)
    dy = float(subject.y - camera.heightMeters)
    dz = float(subject.z - camera.z)
    horizontal_distance = math.hypot(dx, dz)
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance <= 0.001:
        return {"visibility": "unknown", "reason": "Subject overlaps the camera position."}

    bearing = math.degrees(math.atan2(dx, dz))
    elevation = math.degrees(math.atan2(dy, max(horizontal_distance, 0.001)))
    horizontal_offset = abs(_angle_delta(bearing, camera.yawDegrees))
    vertical_offset = abs(_angle_delta(elevation, camera.pitchDegrees))
    horizontal_fov = _horizontal_fov(camera.lensMm)
    vertical_fov = _vertical_fov(camera.lensMm)
    edge_band_h = horizontal_fov * 0.18
    edge_band_v = vertical_fov * 0.18
    outside = _outside_bounds(document, x=subject.x, y=subject.y, z=subject.z)

    blocker: dict[str, Any] | None = None
    for blocker_kind, candidate in _all_subjects(document):
        if candidate.id == subject.id:
            continue
        cdx = float(candidate.x - camera.x)
        cdy = float(candidate.y - camera.heightMeters)
        cdz = float(candidate.z - camera.z)
        candidate_horizontal = math.hypot(cdx, cdz)
        candidate_distance = math.sqrt(cdx * cdx + cdy * cdy + cdz * cdz)
        if candidate_distance >= distance - 0.25:
            continue
        candidate_bearing = math.degrees(math.atan2(cdx, cdz))
        candidate_elevation = math.degrees(math.atan2(cdy, max(candidate_horizontal, 0.001)))
        if (
            abs(_angle_delta(candidate_bearing, bearing)) <= 8.0
            and abs(_angle_delta(candidate_elevation, elevation)) <= 10.0
        ):
            blocker = {
                "id": candidate.id,
                "label": _label_for_subject(blocker_kind, candidate),
                "kind": blocker_kind,
                "distanceMeters": round(candidate_distance, 2),
            }
            break

    if outside:
        visibility = "outside"
        reason = "Subject is outside the current map bounds."
    elif horizontal_offset > horizontal_fov / 2.0 or vertical_offset > vertical_fov / 2.0:
        visibility = "outside"
        reason = "Subject falls outside the camera framing."
    elif blocker is not None and horizontal_offset <= horizontal_fov * 0.22:
        visibility = "occluded"
        reason = f"{blocker['label']} is blocking the line of sight."
    elif (
        blocker is not None
        or horizontal_offset >= (horizontal_fov / 2.0 - edge_band_h)
        or vertical_offset >= (vertical_fov / 2.0 - edge_band_v)
    ):
        visibility = "partially"
        reason = "Subject is near the edge of frame or only partly readable."
    else:
        visibility = "visible"
        reason = "Subject is clearly inside the current camera framing."

    return {
        "visibility": visibility,
        "reason": reason,
        "subjectId": subject.id,
        "subjectLabel": _label_for_subject(kind, subject),
        "distanceMeters": round(distance, 2),
        "horizontalOffsetDegrees": round(horizontal_offset, 2),
        "verticalOffsetDegrees": round(vertical_offset, 2),
        "bearingDegrees": round(bearing, 2),
        "elevationDegrees": round(elevation, 2),
        "blocker": blocker,
    }


def _position_summary(x: float, y: float, z: float) -> str:
    label = creative_position_labels(x=x, y=y, z=z)
    return f"{label['summary']}, {label['height']}"


def _map_summary(document: SpatialMapDocument) -> dict[str, Any]:
    summary = spatial_service.document_summary(document)
    summary["assignedSceneIds"] = list(document.assignedSceneIds)
    summary["has360Collage"] = bool(document.collage)
    summary["heroCameraId"] = next((camera.id for camera in document.cameras if camera.hero), None)
    return summary


def _generation_packet(
    ctx: ToolContext,
    args: dict[str, Any],
    *,
    target: str,
) -> dict[str, Any]:
    document_id = _required_string(args, "documentId")
    camera_id = _string(args, "cameraId") or None
    bundle = spatial_service.build_reference_bundle(
        ctx.db,
        ctx.project_id,
        document_id,
        target=target,
        camera_id=camera_id,
    )
    primary_camera = bundle.primaryCamera
    prompt_direction = _direction_for_yaw(primary_camera.yawDegrees) if primary_camera else "front"
    directional_prompt = bundle.directionalPrompts.get(prompt_direction) if bundle.directionalPrompts else ""
    prompt = directional_prompt or bundle.environmentPrompt
    guidance = []
    if primary_camera is not None:
        guidance.append(
            f"Use the {primary_camera.label} framing at {primary_camera.heightMeters:.2f}m with a {primary_camera.lensMm:.0f}mm lens."
        )
    if target == "video" and bundle.movementPaths:
        guidance.append("Preserve the staged movement paths instead of inventing new blocking.")
    guidance.append("Keep the same environment prompt and placed assets consistent with the approved map.")
    return {
        "ok": True,
        "documentId": document_id,
        "target": target,
        "cameraDirection": prompt_direction,
        "prompt": prompt,
        "primaryCamera": primary_camera.model_dump() if primary_camera else None,
        "guidance": guidance,
        "referenceBundle": bundle.model_dump(),
        "mock": False,
        "_evidence": {
            "source": "spatial_map.reference_bundle",
            "target": target,
        },
    }


def _waypoints(args: dict[str, Any]) -> list[SpatialMovementWaypoint]:
    payload = _json_array_arg(args, "waypointsJson")
    if not payload:
        raise ValueError("waypointsJson is required")
    return [SpatialMovementWaypoint.model_validate(item) for item in payload]


async def list_maps(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _string(args, "sceneId")
    documents = spatial_service.list_documents(ctx.db, ctx.project_id)
    if scene_id:
        documents = [item for item in documents if item.sceneId == scene_id or scene_id in item.assignedSceneIds]
    return {
        "ok": True,
        "count": len(documents),
        "documents": [item.model_dump() for item in documents],
        "summaries": [_map_summary(item) for item in documents],
        "mock": False,
        "_evidence": {"source": "spatial_map.service.list_documents"},
    }


async def get_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    return {
        "ok": True,
        "document": document.model_dump(),
        "summary": _map_summary(document),
        "mock": False,
        "_evidence": {"source": "spatial_map.service.get_document"},
    }


async def inspect_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    hero_camera = _camera_for_document(document, _string(args, "cameraId") or None)
    return {
        "ok": True,
        "documentId": document.id,
        "title": document.title,
        "sceneId": document.sceneId,
        "locationId": document.locationId,
        "summary": _map_summary(document),
        "heroCamera": hero_camera.model_dump() if hero_camera else None,
        "characters": [
            {
                **item.model_dump(),
                "positionSummary": _position_summary(item.x, item.y, item.z),
            }
            for item in document.characters
        ],
        "props": [
            {
                **item.model_dump(),
                "positionSummary": _position_summary(item.x, item.y, item.z),
            }
            for item in document.props
        ],
        "paths": [item.model_dump() for item in document.paths],
        "mock": False,
        "_evidence": {"source": "spatial_map.service.document_summary"},
    }


async def list_cameras(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    return {
        "ok": True,
        "documentId": document.id,
        "count": len(document.cameras),
        "cameras": [camera.model_dump() for camera in document.cameras],
        "heroCameraId": next((camera.id for camera in document.cameras if camera.hero), None),
        "mock": False,
        "_evidence": {"source": "spatial_map.service.get_document"},
    }


async def get_camera_view(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    camera = _camera_for_document(document, _string(args, "cameraId") or None)
    if camera is None:
        return {
            "ok": True,
            "documentId": document.id,
            "camera": None,
            "subjects": [],
            "warnings": ["No camera is placed on this map yet."],
            "mock": False,
            "_evidence": {"source": "spatial_map.service.get_document"},
        }
    subjects = []
    for kind, subject in _all_subjects(document):
        subjects.append(
            {
                "kind": kind,
                "subject": subject.model_dump(),
                "analysis": _visibility_details(document, camera, kind, subject),
            }
        )
    return {
        "ok": True,
        "documentId": document.id,
        "camera": camera.model_dump(),
        "cameraDirection": _direction_for_yaw(camera.yawDegrees),
        "subjects": subjects,
        "warnings": list(document.warnings),
        "mock": False,
        "_evidence": {"source": "spatial_map.visibility_approximation"},
    }


async def check_visibility(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    target_type = _string(args, "targetType") or "placement"
    target_id = _required_string(args, "targetId")
    kind, subject = _resolve_subject(document, target_type=target_type, target_id=target_id)
    camera = _camera_for_document(document, _string(args, "cameraId") or None)
    analysis = _visibility_details(document, camera, kind, subject)
    return {
        "ok": True,
        "documentId": document.id,
        "camera": camera.model_dump() if camera else None,
        "analysis": analysis,
        "mock": False,
        "_evidence": {"source": "spatial_map.visibility_approximation"},
    }


async def check_consistency(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = _document(ctx, args)
    warnings = list(document.warnings)
    if not document.assignedSceneIds and not document.sceneId:
        warnings.append("Map is not assigned to a scene yet.")
    hero_count = len([camera for camera in document.cameras if camera.hero])
    if hero_count > 1:
        warnings.append("More than one camera is marked as hero.")
    for camera in document.cameras:
        if _outside_bounds(document, x=camera.x, y=camera.heightMeters, z=camera.z):
            warnings.append(f"Camera '{camera.label}' sits outside the current map bounds.")
    for label, item in [("Character", char) for char in document.characters] + [("Prop", prop) for prop in document.props]:
        if _outside_bounds(document, x=item.x, y=item.y, z=item.z):
            warnings.append(f"{label} '{item.label}' sits outside the current map bounds.")
    warnings = sorted(set(warnings))
    return {
        "ok": True,
        "documentId": document.id,
        "status": "ready" if not warnings else "needs_attention",
        "consistencyScore": max(0.0, round(1.0 - min(len(warnings), 8) * 0.12, 2)),
        "warnings": warnings,
        "summary": _map_summary(document),
        "mock": False,
        "_evidence": {"source": "spatial_map.consistency_warnings"},
    }


async def build_reference_bundle(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bundle = spatial_service.build_reference_bundle(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        target=_string(args, "target") or "image",
        camera_id=_string(args, "cameraId") or None,
    )
    return {
        "ok": True,
        "bundle": bundle.model_dump(),
        "mock": False,
        "_evidence": {"source": "spatial_map.service.build_reference_bundle"},
    }


def preview_create_map(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    title = _string(args, "title") or "Spatial Map"
    scene_id = _string(args, "sceneId") or "not assigned yet"
    return ToolPreview(
        summary="Create a new Spatial Map for this project.",
        lines=[
            f"title: {title}",
            f"sceneId: {scene_id}",
            "Creates one shared staging map for environment, characters, props, and cameras.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.create_document(
        ctx.db,
        ctx.project_id,
        SpatialMapCreateBody(
            title=_string(args, "title") or "Spatial Map",
            sceneId=_string(args, "sceneId") or None,
            locationId=_string(args, "locationId") or None,
            notes=_string(args, "notes"),
            bounds=_bounds_from_args(args),
            backgroundAssetId=_string(args, "backgroundAssetId") or None,
            masterEnvironmentPrompt=_string(args, "masterEnvironmentPrompt"),
            providerHonesty=_string(args, "providerHonesty") or "approximate_translation",
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.create_document"},
    }


def preview_update_bounds(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    document_id = _required_string(args, "documentId")
    bounds = _bounds_from_args(args)
    return ToolPreview(
        summary="Update the playable bounds of this Spatial Map.",
        lines=[
            f"documentId: {document_id}",
            f"x: {bounds.minX:g} to {bounds.maxX:g}",
            f"y: {bounds.minY:g} to {bounds.maxY:g}",
            f"z: {bounds.minZ:g} to {bounds.maxZ:g}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_update_bounds(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.update_document(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialMapUpdateBody(bounds=_bounds_from_args(args)),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.update_document"},
    }


def preview_place_character(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Place a character on the Spatial Map.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"characterId: {_required_string(args, 'characterId')}",
            f"label: {_required_string(args, 'label')}",
            f"position: {_position_summary(float(args.get('x', 0.0)), float(args.get('y', 0.0)), float(args.get('z', 0.0)))}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_place_character(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.place_character(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialCharacterPlacementBody(
            characterId=_required_string(args, "characterId"),
            label=_required_string(args, "label"),
            assetId=_string(args, "assetId") or None,
            anchorId=_string(args, "anchorId") or None,
            notes=_string(args, "notes"),
            x=float(args.get("x", 0.0)),
            y=float(args.get("y", 0.0)),
            z=float(args.get("z", 0.0)),
            yawDegrees=float(args.get("yawDegrees", 0.0)),
            pitchDegrees=float(args.get("pitchDegrees", 0.0)),
            rollDegrees=float(args.get("rollDegrees", 0.0)),
            scale=float(args.get("scale", 1.0)),
            pose=_string(args, "pose"),
            expression=_string(args, "expression"),
            eyeLine=_string(args, "eyeLine"),
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.place_character"},
    }


def preview_place_prop(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Place a prop on the Spatial Map.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"label: {_required_string(args, 'label')}",
            f"position: {_position_summary(float(args.get('x', 0.0)), float(args.get('y', 0.0)), float(args.get('z', 0.0)))}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_place_prop(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.place_prop(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialPropPlacementBody(
            label=_required_string(args, "label"),
            propId=_string(args, "propId") or None,
            assetId=_string(args, "assetId") or None,
            anchorId=_string(args, "anchorId") or None,
            notes=_string(args, "notes"),
            category=_string(args, "category"),
            state=_string(args, "state"),
            x=float(args.get("x", 0.0)),
            y=float(args.get("y", 0.0)),
            z=float(args.get("z", 0.0)),
            yawDegrees=float(args.get("yawDegrees", 0.0)),
            pitchDegrees=float(args.get("pitchDegrees", 0.0)),
            rollDegrees=float(args.get("rollDegrees", 0.0)),
            scale=float(args.get("scale", 1.0)),
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.place_prop"},
    }


def preview_move_placement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Move an existing map placement or camera.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"targetType: {_required_string(args, 'targetType')}",
            f"targetId: {_required_string(args, 'targetId')}",
            "Updates position and rotation only for the selected subject.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_move_placement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document_id = _required_string(args, "documentId")
    target_type = _required_string(args, "targetType")
    target_id = _required_string(args, "targetId")

    def _mutate(document: SpatialMapDocument) -> None:
        kind, item = _resolve_subject(document, target_type=target_type, target_id=target_id)
        if item is None:
            raise ValueError("The requested placement was not found on this map.")
        if kind == "camera":
            camera = item
            for field in ("x", "y", "z", "yawDegrees", "pitchDegrees", "rollDegrees"):
                value = _number(args, field)
                if value is not None:
                    setattr(camera, field, value)
            if _number(args, "heightMeters") is not None:
                camera.heightMeters = float(_number(args, "heightMeters", camera.heightMeters))
        else:
            for field in ("x", "y", "z", "yawDegrees", "pitchDegrees", "rollDegrees", "scale"):
                value = _number(args, field)
                if value is not None:
                    setattr(item, field, value)
            anchor_id = _string(args, "anchorId")
            if anchor_id:
                item.anchorId = anchor_id
            notes = _string(args, "notes")
            if notes:
                item.notes = notes

    document = _persist_document(ctx, document_id, _mutate)
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.document_mutation.move_placement"},
    }


def preview_create_camera(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Create a new camera on the Spatial Map.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"label: {_string(args, 'label') or 'Camera'}",
            f"lens: {float(args.get('lensMm', 35.0)):.0f}mm",
            f"height: {float(args.get('heightMeters', 1.6)):.2f}m",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_camera(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.create_camera(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialCameraCreateBody(
            label=_string(args, "label") or "Camera",
            x=float(args.get("x", 0.0)),
            y=float(args.get("y", 1.6)),
            z=float(args.get("z", 0.0)),
            yawDegrees=float(args.get("yawDegrees", 0.0)),
            pitchDegrees=float(args.get("pitchDegrees", 0.0)),
            rollDegrees=float(args.get("rollDegrees", 0.0)),
            lensMm=float(args.get("lensMm", 35.0)),
            heightMeters=float(args.get("heightMeters", 1.6)),
            shotType=_string(args, "shotType") or "medium",
            targetCharacterIds=_csv_list(args, "targetCharacterIdsCsv"),
            hero=_bool(args, "hero", False),
            lockedFor360=_bool(args, "lockedFor360", False),
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.create_camera"},
    }


def preview_update_camera(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Update an existing Spatial Map camera.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"cameraId: {_required_string(args, 'cameraId')}",
            "Can retune framing, lens, height, targets, or hero status.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_update_camera(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document_id = _required_string(args, "documentId")
    camera_id = _required_string(args, "cameraId")

    def _mutate(document: SpatialMapDocument) -> None:
        camera = next((item for item in document.cameras if item.id == camera_id), None)
        if camera is None:
            raise ValueError("cameraId was not found on this map.")
        for field in (
            "label",
            "shotType",
        ):
            value = _string(args, field)
            if value:
                setattr(camera, field, value)
        for field in ("x", "y", "z", "yawDegrees", "pitchDegrees", "rollDegrees", "lensMm", "heightMeters"):
            value = _number(args, field)
            if value is not None:
                setattr(camera, field, value)
        if "hero" in args and args.get("hero") is not None:
            hero = _bool(args, "hero", camera.hero)
            if hero:
                for other in document.cameras:
                    other.hero = False
            camera.hero = hero
        if "lockedFor360" in args and args.get("lockedFor360") is not None:
            camera.lockedFor360 = _bool(args, "lockedFor360", camera.lockedFor360)
        if "targetCharacterIdsCsv" in args:
            camera.targetCharacterIds = _csv_list(args, "targetCharacterIdsCsv")

    document = _persist_document(ctx, document_id, _mutate)
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.document_mutation.update_camera"},
    }


def preview_create_path(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    waypoints = _waypoints(args)
    return ToolPreview(
        summary="Create a movement path for a staged subject.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"subjectType: {_required_string(args, 'subjectType')}",
            f"subjectId: {_required_string(args, 'subjectId')}",
            f"waypoints: {len(waypoints)}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_path(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.create_path(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialMovementPathCreateBody(
            label=_string(args, "label") or "Movement Path",
            subjectType=_required_string(args, "subjectType"),
            subjectId=_required_string(args, "subjectId"),
            waypoints=_waypoints(args),
            notes=_string(args, "notes"),
            loop=_bool(args, "loop", False),
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.create_path"},
    }


def preview_generate_360_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    document_id = _required_string(args, "documentId")
    include_characters = _bool(args, "includeCharacters", False)
    plan = spatial_service.create_capture_plan(
        ctx.db,
        ctx.project_id,
        document_id,
        SpatialCapturePlanBody(
            includeCharacters=include_characters,
            masterEnvironmentPrompt=_string(args, "masterEnvironmentPrompt") or None,
            cameraHeightMeters=float(args.get("cameraHeightMeters", 1.6)),
            lensMm=float(args.get("lensMm", 24.0)),
        ),
    )
    return ToolPreview(
        summary="Create a locked 360 capture plan from one master environment prompt.",
        lines=[
            f"documentId: {document_id}",
            f"captureMode: {plan.captureMode}",
            f"masterEnvironmentPrompt: {plan.masterEnvironmentPrompt or '(empty)'}",
            f"shots: {len(plan.shots)} directions at locked height {plan.cameraHeightMeters:.2f}m and lens {plan.lensMm:.0f}mm",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Add a master environment prompt before capturing if the prompt is still empty."]
        if not plan.masterEnvironmentPrompt
        else [],
    )


def apply_generate_360_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document_id = _required_string(args, "documentId")
    include_characters = _bool(args, "includeCharacters", False)
    camera_height = float(args.get("cameraHeightMeters", 1.6))
    lens_mm = float(args.get("lensMm", 24.0))
    prompt = _string(args, "masterEnvironmentPrompt")
    document = spatial_service.create_collage(
        ctx.db,
        ctx.project_id,
        document_id,
        SpatialCollageCreateBody(
            masterEnvironmentPrompt=prompt,
            captureMode="include_characters" if include_characters else "environment_only",
            cameraHeightMeters=camera_height,
            lensMm=lens_mm,
            heroDirection=_string(args, "heroDirection") or None,
        ),
    )
    plan = spatial_service.create_capture_plan(
        ctx.db,
        ctx.project_id,
        document_id,
        SpatialCapturePlanBody(
            includeCharacters=include_characters,
            masterEnvironmentPrompt=prompt or None,
            cameraHeightMeters=camera_height,
            lensMm=lens_mm,
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "plan": plan.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {
            "source": "spatial_map.capture_intelligence",
            "usesSharedMasterPrompt": True,
        },
    }


def preview_assign_to_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Assign this Spatial Map to a scene.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"sceneId: {_required_string(args, 'sceneId')}",
            f"locationId: {_string(args, 'locationId') or '(unchanged)'}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_assign_to_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.assign_to_scene(
        ctx.db,
        ctx.project_id,
        _required_string(args, "documentId"),
        SpatialAssignSceneBody(
            sceneId=_required_string(args, "sceneId"),
            locationId=_string(args, "locationId") or None,
        ),
    )
    return {
        "ok": True,
        "document": document.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.assign_to_scene"},
    }


def preview_prepare_image_generation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    packet = _generation_packet(ctx, args, target="image")
    return ToolPreview(
        summary="Prepare an image generation packet from the approved Spatial Map.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"cameraDirection: {packet['cameraDirection']}",
            "Builds a reference bundle and prompt packet only. It does not generate an image yet.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_prepare_image_generation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    packet = _generation_packet(ctx, args, target="image")
    return {**packet, "approvedPreparation": True, "persisted": False}


def preview_prepare_video_generation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    packet = _generation_packet(ctx, args, target="video")
    return ToolPreview(
        summary="Prepare a video generation packet from the approved Spatial Map.",
        lines=[
            f"documentId: {_required_string(args, 'documentId')}",
            f"cameraDirection: {packet['cameraDirection']}",
            "Builds a motion-aware reference bundle and prompt packet only. It does not generate a video yet.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_prepare_video_generation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    packet = _generation_packet(ctx, args, target="video")
    return {**packet, "approvedPreparation": True, "persisted": False}
