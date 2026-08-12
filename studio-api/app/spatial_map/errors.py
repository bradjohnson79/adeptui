"""Typed M4.11 Spatial Map error contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException


class SpatialMapErrorCode(str, Enum):
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    SPATIAL_MAP_NOT_FOUND = "SPATIAL_MAP_NOT_FOUND"
    SCENE_NOT_FOUND = "SCENE_NOT_FOUND"
    PLACEMENT_NOT_FOUND = "PLACEMENT_NOT_FOUND"
    CHARACTER_LIMIT_REACHED = "CHARACTER_LIMIT_REACHED"
    PROP_LIMIT_REACHED = "PROP_LIMIT_REACHED"
    CAMERA_LIMIT_REACHED = "CAMERA_LIMIT_REACHED"
    COORDINATE_SYSTEM_UNSUPPORTED = "COORDINATE_SYSTEM_UNSUPPORTED"
    COLLAGE_MINIMUM_DIRECTIONS_REQUIRED = "COLLAGE_MINIMUM_DIRECTIONS_REQUIRED"
    COLLAGE_DIRECTION_INVALID = "COLLAGE_DIRECTION_INVALID"
    PATH_SUBJECT_NOT_FOUND = "PATH_SUBJECT_NOT_FOUND"
    ASSIGNMENT_INVALID = "ASSIGNMENT_INVALID"
    REFERENCE_BUNDLE_TARGET_INVALID = "REFERENCE_BUNDLE_TARGET_INVALID"


ERROR_DETAILS: dict[SpatialMapErrorCode, dict[str, Any]] = {
    SpatialMapErrorCode.PROJECT_NOT_FOUND: {
        "status": 404,
        "explanation": "The requested project does not exist.",
        "recovery": "Confirm the projectId and retry.",
    },
    SpatialMapErrorCode.SPATIAL_MAP_NOT_FOUND: {
        "status": 404,
        "explanation": "The requested Spatial Map document could not be found.",
        "recovery": "Refresh the map list and retry with a valid document id.",
    },
    SpatialMapErrorCode.SCENE_NOT_FOUND: {
        "status": 404,
        "explanation": "The requested scene does not exist in this project.",
        "recovery": "Choose a valid scene from the open project and retry.",
    },
    SpatialMapErrorCode.PLACEMENT_NOT_FOUND: {
        "status": 404,
        "explanation": "That character, prop, or camera is no longer on this map.",
        "recovery": "Refresh the map and try again.",
    },
    SpatialMapErrorCode.CHARACTER_LIMIT_REACHED: {
        "status": 409,
        "explanation": "A Spatial Map can only hold four characters.",
        "recovery": "Remove a character placement or create a new map variant.",
    },
    SpatialMapErrorCode.PROP_LIMIT_REACHED: {
        "status": 409,
        "explanation": "A Spatial Map can only hold four props.",
        "recovery": "Remove a prop placement or create a new map variant.",
    },
    SpatialMapErrorCode.CAMERA_LIMIT_REACHED: {
        "status": 409,
        "explanation": "A Spatial Map can only hold eight cameras.",
        "recovery": "Remove a camera or reuse an existing camera angle.",
    },
    SpatialMapErrorCode.COORDINATE_SYSTEM_UNSUPPORTED: {
        "status": 400,
        "explanation": "Spatial Map documents must use the adept-world-v1 coordinate system.",
        "recovery": "Retry with coordinateSystem='adept-world-v1'.",
    },
    SpatialMapErrorCode.COLLAGE_MINIMUM_DIRECTIONS_REQUIRED: {
        "status": 400,
        "explanation": "A 360 collage needs at least the eight primary directions.",
        "recovery": "Provide front, front_right, right, rear_right, rear, rear_left, left, and front_left.",
    },
    SpatialMapErrorCode.COLLAGE_DIRECTION_INVALID: {
        "status": 400,
        "explanation": "The requested collage direction is not supported.",
        "recovery": "Use one of the supported directions for Spatial 360 capture.",
    },
    SpatialMapErrorCode.PATH_SUBJECT_NOT_FOUND: {
        "status": 404,
        "explanation": "The movement path points to a character, prop, or camera that is not on this map.",
        "recovery": "Create the placement first, then attach the movement path.",
    },
    SpatialMapErrorCode.ASSIGNMENT_INVALID: {
        "status": 400,
        "explanation": "The requested scene assignment is invalid for this map.",
        "recovery": "Confirm the scene belongs to the same project and retry.",
    },
    SpatialMapErrorCode.REFERENCE_BUNDLE_TARGET_INVALID: {
        "status": 400,
        "explanation": "Spatial reference bundles only support image or video targets.",
        "recovery": "Retry with target='image' or target='video'.",
    },
}


def error_payload(code: SpatialMapErrorCode | str, message: str | None = None, **extra: Any) -> dict[str, Any]:
    enum_code = SpatialMapErrorCode(code)
    detail = ERROR_DETAILS[enum_code]
    payload = {
        "code": enum_code.value,
        "message": message or detail["explanation"],
        "explanation": detail["explanation"],
        "recovery": detail["recovery"],
    }
    payload.update(extra)
    return payload


def raise_http_error(
    code: SpatialMapErrorCode | str,
    message: str | None = None,
    *,
    status_code: int | None = None,
    **extra: Any,
) -> HTTPException:
    enum_code = SpatialMapErrorCode(code)
    status = int(status_code or ERROR_DETAILS[enum_code]["status"])
    return HTTPException(status_code=status, detail=error_payload(enum_code, message, **extra))
