"""Scene Creator cinematographer — structured cameras, commands, persistence.

Spatial Map ``SpatialCamera`` remains the baseline authority. This module stores
Scene Creator *adjusted* C1–C4 state and never writes back to the map.
"""

from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..spatial_map.grid import (
    CARDINAL_LABELS,
    adjacent_cell,
    cell_center_normalized,
    density_for_scale,
    orientation_to_yaw,
)

# Never write Scene Creator camera experiments back to Spatial Map.
# Future hook: Save Camera Position Back to Spatial Map (not shipped).
SAVE_CAMERA_BACK_TO_SPATIAL_MAP = False

logger = logging.getLogger(__name__)

CINEMATOGRAPHER_CATEGORY = "scene_cinematographer"

PreviewStatus = Literal["none", "stale", "generating", "ready", "failed"]
TargetEntityType = Literal["character", "prop"]
AnglePreset = Literal["low", "eye_level", "high"]

FOV_PRESETS = ("narrow", "medium", "wide")
FOV_LENS_MM = {"narrow": 85.0, "medium": 35.0, "wide": 24.0}

# Look-axis cell deltas. Row increases south; N looks toward decreasing row.
LOOK_DELTA: dict[str, tuple[int, int]] = {
    "N": (0, -1),
    "NE": (1, -1),
    "E": (1, 0),
    "SE": (1, 1),
    "S": (0, 1),
    "SW": (-1, 1),
    "W": (-1, 0),
    "NW": (-1, -1),
}

SHOT_TYPE_LABELS: dict[str, str] = {
    "extreme_close_up": "EXTREME CLOSE-UP",
    "close_up": "CLOSE-UP",
    "medium_close_up": "MEDIUM CLOSE-UP",
    "medium": "MEDIUM SHOT",
    "cowboy": "COWBOY SHOT",
    "full": "FULL SHOT",
    "wide": "WIDE SHOT",
    "extreme_wide": "EXTREME WIDE SHOT",
}

ANGLE_LABELS = {"high": "HIGH ANGLE", "eye_level": "EYE LEVEL", "low": "LOW ANGLE"}

HASH_FIELDS = (
    "cameraId",
    "cameraSlot",
    "gridColumn",
    "gridRow",
    "normalizedX",
    "normalizedY",
    "yawDegrees",
    "pitchDegrees",
    "rollDegrees",
    "heightMeters",
    "fovPreset",
    "lensMm",
    "opticalZoomStep",
    "forwardBack",
    "leftRight",
    "vertical",
    "anglePreset",
    "shotType",
    "targetEntityId",
    "targetEntityType",
    "orientation",
    "inclusionPropId",
)


class CinematographerError(ValueError):
    pass


class CameraCommandSpec(BaseModel):
    id: str
    category: str
    label: str
    needs_subject: bool = False
    physical: bool = False
    optical: bool = False


CAMERA_OPERATIONS: list[CameraCommandSpec] = [
    CameraCommandSpec(id="step_forward", category="movement", label="Step Forward", physical=True),
    CameraCommandSpec(id="step_back", category="movement", label="Step Back", physical=True),
    CameraCommandSpec(id="step_left", category="movement", label="Step Left", physical=True),
    CameraCommandSpec(id="step_right", category="movement", label="Step Right", physical=True),
    CameraCommandSpec(id="step_up", category="movement", label="Step Up", physical=True),
    CameraCommandSpec(id="step_down", category="movement", label="Step Down", physical=True),
    CameraCommandSpec(id="extreme_close_up", category="framing", label="Extreme Close-Up", needs_subject=True),
    CameraCommandSpec(id="close_up", category="framing", label="Close-Up", needs_subject=True),
    CameraCommandSpec(id="medium_close_up", category="framing", label="Medium Close-Up", needs_subject=True),
    CameraCommandSpec(id="medium", category="framing", label="Medium Shot", needs_subject=True),
    CameraCommandSpec(id="cowboy", category="framing", label="Cowboy Shot", needs_subject=True),
    CameraCommandSpec(id="full", category="framing", label="Full Shot", needs_subject=True),
    CameraCommandSpec(id="wide", category="framing", label="Wide Shot", needs_subject=True),
    CameraCommandSpec(id="extreme_wide", category="framing", label="Extreme Wide Shot", needs_subject=True),
    CameraCommandSpec(id="dolly_in", category="dolly", label="Dolly In", physical=True),
    CameraCommandSpec(id="dolly_out", category="dolly", label="Dolly Out", physical=True),
    CameraCommandSpec(id="high_angle", category="angle", label="High Angle", needs_subject=True),
    CameraCommandSpec(id="eye_level", category="angle", label="Eye Level", needs_subject=True),
    CameraCommandSpec(id="low_angle", category="angle", label="Low Angle", needs_subject=True),
    CameraCommandSpec(id="orbit_left", category="orbit", label="Orbit Left", physical=True),
    CameraCommandSpec(id="orbit_right", category="orbit", label="Orbit Right", physical=True),
    CameraCommandSpec(id="zoom_in", category="optical", label="Zoom In", optical=True),
    CameraCommandSpec(id="zoom_out", category="optical", label="Zoom Out", optical=True),
    CameraCommandSpec(id="orient_3d_enable", category="orientation3d", label="Enable 3D Aim"),
    CameraCommandSpec(id="orient_3d_disable", category="orientation3d", label="Disable 3D Aim"),
    CameraCommandSpec(id="orient_yaw", category="orientation3d", label="Aim Yaw"),
    CameraCommandSpec(id="orient_pitch", category="orientation3d", label="Aim Pitch"),
    CameraCommandSpec(id="orient_roll", category="orientation3d", label="Aim Roll"),
    CameraCommandSpec(id="orient_zoom", category="orientation3d", label="Optical Zoom", optical=True),
    CameraCommandSpec(id="orient_target_lock", category="orientation3d", label="Target Lock"),
    CameraCommandSpec(id="orient_axis_lock", category="orientation3d", label="Axis Lock"),
    CameraCommandSpec(id="orient_snap", category="orientation3d", label="Snap Aim"),
    CameraCommandSpec(id="orient_reset", category="orientation3d", label="Reset Aim"),
]

OPS_BY_ID = {op.id: op for op in CAMERA_OPERATIONS}


class PhysicalStepOffset(BaseModel):
    forwardBack: int = 0
    leftRight: int = 0
    vertical: int = 0


class AxisLocks(BaseModel):
    yaw: bool = False
    pitch: bool = False
    roll: bool = False
    zoom: bool = False


class Orientation3DState(BaseModel):
    enabled: bool = False
    targetLock: bool = False
    axisLocks: AxisLocks = Field(default_factory=AxisLocks)
    source: Literal["discrete", "gizmo"] = "discrete"
    zoom: float = 1.0


class CameraPose(BaseModel):
    """Hashable structured composition. Preview asset ids are not part of this."""

    cameraId: str = ""
    cameraSlot: int = 0
    label: str = "Camera"
    enabled: bool = True
    gridColumn: int = 0
    gridRow: int = 0
    normalizedX: float = 0.0
    normalizedY: float = 0.0
    x: float = 0.0
    y: float = 1.6
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    heightMeters: float = 1.6
    orientation: str = "N"
    fovPreset: str = "medium"
    lensMm: float = 35.0
    opticalZoomStep: int = 0
    physicalStepOffset: PhysicalStepOffset = Field(default_factory=PhysicalStepOffset)
    anglePreset: AnglePreset = "eye_level"
    shotType: str = "medium"
    targetEntityId: str = ""
    targetEntityType: Optional[TargetEntityType] = None
    inclusionPropId: str = ""
    orientation3d: Orientation3DState = Field(default_factory=Orientation3DState)


class CameraLineage(BaseModel):
    cameraId: str = ""
    cameraStateVersion: int = 1
    cameraStateHash: str = ""
    previewJobId: str = ""
    previewAssetId: str = ""
    previewStateVersion: int = 0
    previewStateHash: str = ""
    locked: bool = False
    lockedStateVersion: int = 0
    lockedStateHash: str = ""
    lockedSnapshot: dict[str, Any] = Field(default_factory=dict)
    finalJobId: str = ""
    finalAssetId: str = ""
    finalStateVersion: int = 0
    previewStatus: PreviewStatus = "none"
    previewError: str = ""


class SceneCameraRecord(BaseModel):
    cameraId: str
    cameraSlot: int = 0
    label: str = "Camera 1"
    enabled: bool = True
    baseline: CameraPose = Field(default_factory=CameraPose)
    current: CameraPose = Field(default_factory=CameraPose)
    history: list[dict[str, Any]] = Field(default_factory=list)
    cameraStateVersion: int = 1
    cameraStateHash: str = ""
    structuredCommand: dict[str, Any] = Field(default_factory=dict)
    displayInstruction: str = ""
    userCameraPromptDelta: str = ""
    lineage: CameraLineage = Field(default_factory=CameraLineage)


class SceneCinematographerPack(BaseModel):
    scene_id: str
    project_id: str = ""
    density: int = 10
    grid_scale: int = 0
    selected_camera_id: str = ""
    cameras: list[SceneCameraRecord] = Field(default_factory=list)
    updated_at: str = ""


def camera_state_hash(pose: CameraPose) -> str:
    payload = {
        "cameraId": pose.cameraId,
        "cameraSlot": pose.cameraSlot,
        "gridColumn": pose.gridColumn,
        "gridRow": pose.gridRow,
        "normalizedX": round(float(pose.normalizedX or 0), 6),
        "normalizedY": round(float(pose.normalizedY or 0), 6),
        "yawDegrees": round(float(pose.yawDegrees or 0), 3),
        "pitchDegrees": round(float(pose.pitchDegrees or 0), 3),
        "rollDegrees": round(float(pose.rollDegrees or 0), 3),
        "heightMeters": round(float(pose.heightMeters or 0), 4),
        "fovPreset": pose.fovPreset,
        "lensMm": round(float(pose.lensMm or 0), 2),
        "opticalZoomStep": int(pose.opticalZoomStep or 0),
        "forwardBack": pose.physicalStepOffset.forwardBack,
        "leftRight": pose.physicalStepOffset.leftRight,
        "vertical": pose.physicalStepOffset.vertical,
        "anglePreset": pose.anglePreset,
        "shotType": pose.shotType,
        "targetEntityId": pose.targetEntityId or "",
        "targetEntityType": pose.targetEntityType or "",
        "orientation": (pose.orientation or "N").upper(),
        "inclusionPropId": pose.inclusionPropId or "",
    }
    o3 = pose.orientation3d
    if o3.enabled:
        payload["orientation3dEnabled"] = True
        payload["orientation3dTargetLock"] = bool(o3.targetLock)
        payload["orientation3dLockYaw"] = bool(o3.axisLocks.yaw)
        payload["orientation3dLockPitch"] = bool(o3.axisLocks.pitch)
        payload["orientation3dLockRoll"] = bool(o3.axisLocks.roll)
        payload["orientation3dLockZoom"] = bool(o3.axisLocks.zoom)
        payload["orientation3dZoom"] = round(float(o3.zoom or 1.0), 3)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def operations_catalog() -> list[dict[str, Any]]:
    return [op.model_dump() for op in CAMERA_OPERATIONS]


def _op(operation_id: str) -> CameraCommandSpec:
    spec = OPS_BY_ID.get(operation_id)
    if spec is None:
        raise CinematographerError("That camera move is not available.")
    return spec


def validate_command(
    operation_id: str,
    *,
    character_id: str = "",
    prop_id: str = "",
) -> CameraCommandSpec:
    spec = _op(operation_id)
    if spec.needs_subject and not (character_id or "").strip() and not (prop_id or "").strip():
        raise CinematographerError("Choose a character or a prop for this shot.")
    return spec


def _right_delta(orientation: str) -> tuple[int, int]:
    labels = list(CARDINAL_LABELS)
    idx = labels.index(orientation) if orientation in labels else 0
    right = labels[(idx + 2) % 8]
    return LOOK_DELTA[right]


def _apply_cell(pose: CameraPose, column: int, row: int, density: int) -> None:
    nx, ny = cell_center_normalized(column, row, density)
    pose.gridColumn = column
    pose.gridRow = row
    pose.normalizedX = nx
    pose.normalizedY = ny


def _step_cells(pose: CameraPose, d_col: int, d_row: int, density: int, steps: int) -> None:
    col, row = int(pose.gridColumn), int(pose.gridRow)
    last = None
    for _ in range(max(1, steps)):
        nxt = adjacent_cell(col, row, d_col, d_row, density)
        if nxt is None:
            raise CinematographerError("Can't step further in that direction.")
        last = nxt
        col, row = nxt
    if last is None:
        raise CinematographerError("Can't step further in that direction.")
    _apply_cell(pose, last[0], last[1], density)


def _rotate_orientation(pose: CameraPose, steps: int) -> None:
    labels = list(CARDINAL_LABELS)
    current = (pose.orientation or "N").upper()
    if current not in labels:
        current = "N"
    idx = (labels.index(current) + steps) % 8
    pose.orientation = labels[idx]
    pose.yawDegrees = orientation_to_yaw(pose.orientation)


def _nudge_fov(pose: CameraPose, delta_index: int) -> None:
    """delta_index -1 = narrower (zoom in). Never moves the camera cell."""
    base = list(FOV_PRESETS)
    idx = base.index(pose.fovPreset) if pose.fovPreset in base else 1
    idx = max(0, min(2, idx + int(delta_index)))
    pose.fovPreset = base[idx]
    pose.lensMm = FOV_LENS_MM[pose.fovPreset]


YAW_SNAP_DEGREES: dict[str, float] = {
    "front": 0.0,
    "three_quarter_left": 45.0,
    "profile_left": 90.0,
    "rear_three_quarter_left": 135.0,
    "rear": 180.0,
    "rear_three_quarter_right": -135.0,
    "profile_right": -90.0,
    "three_quarter_right": -45.0,
}

PITCH_SNAP_DEGREES: dict[str, float] = {
    "eye_level": 0.0,
    "slight_high": -12.0,
    "high": -28.0,
    "birds_eye": -55.0,
    "slight_low": 12.0,
    "low": 22.0,
    "worms_eye": 45.0,
}

PITCH_MIN, PITCH_MAX = -60.0, 60.0
ROLL_MIN, ROLL_MAX = -25.0, 25.0
ZOOM_MIN, ZOOM_MAX = 0.5, 3.0
LENS_MIN_MM, LENS_MAX_MM = 18.0, 200.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def wrap_yaw_degrees(degrees: float) -> float:
    """Wrap yaw to (-180, 180]."""
    x = float(degrees) % 360.0
    if x > 180.0:
        x -= 360.0
    elif x <= -180.0:
        x += 360.0
    if x == -180.0:
        x = 180.0
    return x


def clamp_pitch_degrees(degrees: float) -> float:
    return _clamp(degrees, PITCH_MIN, PITCH_MAX)


def clamp_roll_degrees(degrees: float) -> float:
    return _clamp(degrees, ROLL_MIN, ROLL_MAX)


def clamp_optical_zoom(zoom: float) -> float:
    return _clamp(zoom, ZOOM_MIN, ZOOM_MAX)


def _nearest_fov_preset(lens_mm: float) -> str:
    return min(FOV_LENS_MM, key=lambda name: abs(FOV_LENS_MM[name] - float(lens_mm)))


def _parse_snap_id(snap_id: str) -> tuple[float | None, float | None]:
    raw = (snap_id or "").strip().lower().replace("-", "_")
    if not raw:
        return None, None
    if raw in YAW_SNAP_DEGREES and raw not in PITCH_SNAP_DEGREES:
        return YAW_SNAP_DEGREES[raw], None
    if raw in PITCH_SNAP_DEGREES and raw not in YAW_SNAP_DEGREES:
        return None, PITCH_SNAP_DEGREES[raw]
    yaw_val: float | None = None
    remainder = raw
    for key in sorted(YAW_SNAP_DEGREES, key=len, reverse=True):
        token = f"_{key}_"
        if raw == key:
            yaw_val = YAW_SNAP_DEGREES[key]
            remainder = ""
            break
        if raw.startswith(f"{key}_"):
            yaw_val = YAW_SNAP_DEGREES[key]
            remainder = raw[len(key) + 1 :]
            break
        if raw.endswith(f"_{key}"):
            yaw_val = YAW_SNAP_DEGREES[key]
            remainder = raw[: -(len(key) + 1)]
            break
        if token in f"_{raw}_":
            yaw_val = YAW_SNAP_DEGREES[key]
            remainder = raw.replace(key, "", 1).strip("_")
            break
    pitch_val: float | None = None
    pitch_src = remainder or raw
    for key in sorted(PITCH_SNAP_DEGREES, key=len, reverse=True):
        if pitch_src == key or raw == key or raw.startswith(f"{key}_") or raw.endswith(f"_{key}"):
            pitch_val = PITCH_SNAP_DEGREES[key]
            break
    return yaw_val, pitch_val


def _apply_optical_zoom(pose: CameraPose, zoom: float, *, baseline_lens_mm: float) -> None:
    zoom = clamp_optical_zoom(zoom)
    pose.orientation3d.zoom = zoom
    base_lens = float(baseline_lens_mm or 0) or 35.0
    pose.lensMm = _clamp(base_lens * zoom, LENS_MIN_MM, LENS_MAX_MM)
    pose.fovPreset = _nearest_fov_preset(pose.lensMm)


def _restore_orientation_from_baseline(record: SceneCameraRecord) -> None:
    """Reset aim/optics only. Keep shot type, target, cell, and physical offset."""
    base = record.baseline
    cur = record.current
    cur.yawDegrees = base.yawDegrees
    cur.pitchDegrees = base.pitchDegrees
    cur.rollDegrees = base.rollDegrees
    cur.lensMm = base.lensMm
    cur.fovPreset = base.fovPreset
    cur.opticalZoomStep = base.opticalZoomStep
    cur.orientation = base.orientation
    cur.orientation3d = base.orientation3d.model_copy(deep=True)


def _apply_orientation3d_operation(
    pose: CameraPose,
    operation_id: str,
    patch: dict[str, Any],
    *,
    baseline_lens_mm: float,
) -> None:
    o3 = pose.orientation3d
    locks = o3.axisLocks
    preserved_target = pose.targetEntityId
    preserved_type = pose.targetEntityType

    if operation_id == "orient_3d_enable":
        o3.enabled = True
        o3.source = "gizmo"
        o3.targetLock = bool(pose.targetEntityId)
        if "targetLock" in patch:
            o3.targetLock = bool(patch["targetLock"])
        return
    if operation_id == "orient_3d_disable":
        o3.enabled = False
        o3.source = "discrete"
        return
    if operation_id == "orient_reset":
        o3.source = "gizmo" if o3.enabled else "discrete"
        return
    if operation_id == "orient_target_lock":
        if "targetLock" in patch:
            o3.targetLock = bool(patch["targetLock"])
        else:
            o3.targetLock = True
        o3.source = "gizmo"
        return
    if operation_id == "orient_axis_lock":
        axis = patch.get("axisLocks")
        if isinstance(axis, dict):
            if "yaw" in axis:
                o3.axisLocks.yaw = bool(axis["yaw"])
            if "pitch" in axis:
                o3.axisLocks.pitch = bool(axis["pitch"])
            if "roll" in axis:
                o3.axisLocks.roll = bool(axis["roll"])
            if "zoom" in axis:
                o3.axisLocks.zoom = bool(axis["zoom"])
        o3.source = "gizmo"
        return

    o3.source = "gizmo"
    if operation_id in {"orient_yaw", "orient_pitch", "orient_roll", "orient_zoom", "orient_snap"}:
        o3.enabled = True

    if operation_id == "orient_yaw" and not locks.yaw and "yawDegrees" in patch:
        pose.yawDegrees = wrap_yaw_degrees(float(patch["yawDegrees"]))
    elif operation_id == "orient_pitch" and not locks.pitch and "pitchDegrees" in patch:
        pose.pitchDegrees = clamp_pitch_degrees(float(patch["pitchDegrees"]))
    elif operation_id == "orient_roll" and not locks.roll and "rollDegrees" in patch:
        pose.rollDegrees = clamp_roll_degrees(float(patch["rollDegrees"]))
    elif operation_id == "orient_zoom" and not locks.zoom and "zoom" in patch:
        _apply_optical_zoom(pose, float(patch["zoom"]), baseline_lens_mm=baseline_lens_mm)
    elif operation_id == "orient_snap":
        yaw_val, pitch_val = _parse_snap_id(str(patch.get("snapId") or ""))
        if yaw_val is not None and not locks.yaw:
            pose.yawDegrees = wrap_yaw_degrees(yaw_val)
        if pitch_val is not None and not locks.pitch:
            pose.pitchDegrees = clamp_pitch_degrees(pitch_val)

    if o3.targetLock:
        pose.targetEntityId = preserved_target
        pose.targetEntityType = preserved_type


def apply_operation(
    pose: CameraPose,
    operation_id: str,
    *,
    density: int,
    character_id: str = "",
    prop_id: str = "",
    character_name: str = "",
    prop_name: str = "",
    character_slot: int | None = None,
    prop_slot: int | None = None,
    held_by_character_id: str = "",
    orientation_patch: dict[str, Any] | None = None,
    baseline_lens_mm: float = 35.0,
) -> dict[str, Any]:
    spec = validate_command(operation_id, character_id=character_id, prop_id=prop_id)
    orientation = (pose.orientation or "N").upper()
    if orientation not in LOOK_DELTA:
        orientation = "N"
        pose.orientation = "N"
    look = LOOK_DELTA[orientation]
    right = _right_delta(orientation)
    orienting = spec.category == "orientation3d"
    keep_target = orienting and pose.orientation3d.targetLock and pose.targetEntityId

    if character_id:
        pose.targetEntityId = character_id
        pose.targetEntityType = "character"
    elif prop_id and (spec.needs_subject or spec.id == "orient_target_lock"):
        pose.targetEntityId = prop_id
        pose.targetEntityType = "prop"
    elif keep_target:
        pass
    if prop_id and character_id:
        pose.inclusionPropId = prop_id
        if held_by_character_id and held_by_character_id == character_id:
            pose.inclusionPropId = prop_id
    elif prop_id and spec.needs_subject and not character_id:
        pose.inclusionPropId = ""

    if spec.id == "step_forward":
        _step_cells(pose, look[0], look[1], density, 1)
        pose.physicalStepOffset.forwardBack += 1
    elif spec.id == "step_back":
        _step_cells(pose, -look[0], -look[1], density, 1)
        pose.physicalStepOffset.forwardBack -= 1
    elif spec.id == "step_right":
        _step_cells(pose, right[0], right[1], density, 1)
        pose.physicalStepOffset.leftRight += 1
    elif spec.id == "step_left":
        _step_cells(pose, -right[0], -right[1], density, 1)
        pose.physicalStepOffset.leftRight -= 1
    elif spec.id == "step_up":
        pose.heightMeters = round(pose.heightMeters + 0.4, 4)
        pose.y = pose.heightMeters
        pose.physicalStepOffset.vertical += 1
    elif spec.id == "step_down":
        pose.heightMeters = max(0.3, round(pose.heightMeters - 0.4, 4))
        pose.y = pose.heightMeters
        pose.physicalStepOffset.vertical -= 1
    elif spec.id == "dolly_in":
        _step_cells(pose, look[0], look[1], density, 2)
        pose.physicalStepOffset.forwardBack += 2
    elif spec.id == "dolly_out":
        _step_cells(pose, -look[0], -look[1], density, 2)
        pose.physicalStepOffset.forwardBack -= 2
    elif spec.id == "orbit_left":
        _rotate_orientation(pose, -1)
    elif spec.id == "orbit_right":
        _rotate_orientation(pose, 1)
    elif spec.id == "zoom_in":
        pose.opticalZoomStep += 1
        _nudge_fov(pose, -1)
    elif spec.id == "zoom_out":
        pose.opticalZoomStep -= 1
        _nudge_fov(pose, 1)
    elif spec.id in SHOT_TYPE_LABELS:
        pose.shotType = spec.id
    elif spec.id == "high_angle":
        pose.anglePreset = "high"
        pose.pitchDegrees = -28.0
        pose.heightMeters = max(pose.heightMeters, 2.2)
        pose.y = pose.heightMeters
    elif spec.id == "eye_level":
        pose.anglePreset = "eye_level"
        pose.pitchDegrees = 0.0
    elif spec.id == "low_angle":
        pose.anglePreset = "low"
        pose.pitchDegrees = 22.0
        pose.heightMeters = max(0.4, min(pose.heightMeters, 1.0))
        pose.y = pose.heightMeters
    elif spec.category == "orientation3d":
        _apply_orientation3d_operation(
            pose,
            spec.id,
            orientation_patch or {},
            baseline_lens_mm=baseline_lens_mm,
        )

    instruction = build_display_instruction(
        pose,
        spec,
        character_id=character_id,
        prop_id=prop_id,
        character_name=character_name,
        prop_name=prop_name,
        character_slot=character_slot,
        prop_slot=prop_slot,
    )
    structured = {
        "cameraId": pose.cameraId,
        "cameraSlot": pose.cameraSlot,
        "operation": spec.id,
        "category": spec.category,
        "shotType": pose.shotType,
        "anglePreset": pose.anglePreset,
        "targetEntityId": pose.targetEntityId,
        "targetEntityType": pose.targetEntityType,
        "inclusionPropId": pose.inclusionPropId,
        "opticalZoomStep": pose.opticalZoomStep,
        "physicalStepOffset": pose.physicalStepOffset.model_dump(),
    }
    return {"instruction": instruction, "structured": structured}


def build_display_instruction(
    pose: CameraPose,
    spec: CameraCommandSpec,
    *,
    character_id: str = "",
    prop_id: str = "",
    character_name: str = "",
    prop_name: str = "",
    character_slot: int | None = None,
    prop_slot: int | None = None,
) -> str:
    cam = f"CAMERA {pose.cameraSlot + 1}"
    char_label = ""
    if character_id:
        n = character_slot if character_slot else 1
        char_label = f"CHARACTER {n}"
        if character_name:
            char_label = f"{char_label}, {character_name}"
    prop_label = ""
    if prop_id:
        n = prop_slot if prop_slot else 1
        prop_label = f"PROP {n}"
        if prop_name:
            prop_label = f"{prop_label}, {prop_name}"

    if spec.category == "movement":
        words = {
            "step_forward": "ONE STEP FORWARD",
            "step_back": "ONE STEP BACK",
            "step_left": "ONE STEP LEFT",
            "step_right": "ONE STEP RIGHT",
            "step_up": "ONE STEP UP",
            "step_down": "ONE STEP DOWN",
        }
        return f"{cam} move {words[spec.id]}."
    if spec.category == "dolly":
        verb = "DOLLY IN toward" if spec.id == "dolly_in" else "DOLLY OUT from"
        target = char_label or prop_label or "the subject"
        return f"{cam} {verb} {target}."
    if spec.category == "orbit":
        side = "LEFT" if spec.id == "orbit_left" else "RIGHT"
        return f"{cam} ORBIT {side}."
    if spec.category == "optical":
        return f"{cam} ZOOM {'IN' if spec.id == 'zoom_in' else 'OUT'}."
    if spec.category == "orientation3d":
        words = {
            "orient_3d_enable": "enable 3D camera aim",
            "orient_3d_disable": "return to standard camera aim",
            "orient_yaw": "adjust yaw",
            "orient_pitch": "adjust pitch",
            "orient_roll": "adjust roll",
            "orient_zoom": "adjust optical zoom",
            "orient_target_lock": "set target lock",
            "orient_axis_lock": "set axis lock",
            "orient_snap": "snap camera aim",
            "orient_reset": "reset 3D camera aim",
        }
        return f"{cam} {words.get(spec.id, spec.label.lower())}."
    if spec.category == "angle":
        angle = ANGLE_LABELS[spec.id.replace("_angle", "") if spec.id != "eye_level" else "eye_level"]
        if spec.id == "high_angle":
            angle = "HIGH ANGLE"
        elif spec.id == "low_angle":
            angle = "LOW ANGLE"
        else:
            angle = "EYE LEVEL"
        if char_label and prop_label:
            return f"{cam} take {angle} on {char_label} with {prop_label} included in composition."
        target = char_label or prop_label or "the subject"
        return f"{cam} take {angle} on {target}."
    shot = SHOT_TYPE_LABELS.get(spec.id, spec.label.upper())
    if char_label and prop_label:
        return f"{cam} take {shot} on {char_label} with {prop_label} included in composition."
    if char_label:
        return f"{cam} take {shot} on {char_label}."
    if prop_label:
        return f"{cam} take {shot} on {prop_label}."
    return f"{cam} take {shot}."


def _snapshot_current(record: SceneCameraRecord) -> dict[str, Any]:
    return {
        "pose": record.current.model_dump(),
        "cameraStateVersion": record.cameraStateVersion,
        "cameraStateHash": record.cameraStateHash,
        "structuredCommand": deepcopy(record.structuredCommand),
        "displayInstruction": record.displayInstruction,
        "userCameraPromptDelta": record.userCameraPromptDelta,
        "lineage": record.lineage.model_dump(),
    }


def _restore_snapshot(record: SceneCameraRecord, snap: dict[str, Any]) -> None:
    record.current = CameraPose.model_validate(snap.get("pose") or {})
    record.cameraStateVersion = int(snap.get("cameraStateVersion") or 1)
    record.cameraStateHash = str(snap.get("cameraStateHash") or camera_state_hash(record.current))
    record.structuredCommand = dict(snap.get("structuredCommand") or {})
    record.displayInstruction = str(snap.get("displayInstruction") or "")
    record.userCameraPromptDelta = str(snap.get("userCameraPromptDelta") or "")
    lin = snap.get("lineage")
    if isinstance(lin, dict):
        record.lineage = CameraLineage.model_validate(lin)


def bump_after_mutation(record: SceneCameraRecord) -> None:
    record.cameraStateVersion = int(record.cameraStateVersion or 1) + 1
    record.cameraStateHash = camera_state_hash(record.current)
    record.lineage.cameraId = record.cameraId
    record.lineage.cameraStateVersion = record.cameraStateVersion
    record.lineage.cameraStateHash = record.cameraStateHash
    if record.lineage.previewStateVersion != record.cameraStateVersion:
        if record.lineage.previewStatus in {"ready", "generating"}:
            record.lineage.previewStatus = "stale"
        elif record.lineage.previewStatus == "none":
            pass
        else:
            record.lineage.previewStatus = "stale"
    if record.lineage.locked:
        if (
            record.lineage.lockedStateVersion != record.cameraStateVersion
            or record.lineage.lockedStateHash != record.cameraStateHash
        ):
            record.lineage.locked = False


def lock_is_valid(record: SceneCameraRecord) -> bool:
    lin = record.lineage
    if not lin.locked:
        return False
    if lin.lockedStateVersion != record.cameraStateVersion:
        return False
    if lin.lockedStateHash != record.cameraStateHash:
        return False
    return True


def preview_matches_current(record: SceneCameraRecord) -> bool:
    lin = record.lineage
    if lin.previewStatus not in {"ready", "generating"}:
        # generating still matches if version matches
        if lin.previewStatus != "generating":
            return False
    return (
        lin.previewStateVersion == record.cameraStateVersion
        and (not lin.previewStateHash or lin.previewStateHash == record.cameraStateHash)
    )


def can_lock(record: SceneCameraRecord) -> bool:
    lin = record.lineage
    return (
        lin.previewStatus == "ready"
        and lin.previewStateVersion == record.cameraStateVersion
        and (not lin.previewStateHash or lin.previewStateHash == record.cameraStateHash)
    )


def pose_from_spatial(cam: Any, *, slot: int, density: int) -> CameraPose:
    orientation = str(getattr(cam, "orientation", None) or "N").upper() or "N"
    col = int(getattr(cam, "gridColumn", 0) or 0)
    row = int(getattr(cam, "gridRow", 0) or 0)
    nx = getattr(cam, "normalizedX", None)
    ny = getattr(cam, "normalizedY", None)
    if nx is None or ny is None:
        nx, ny = cell_center_normalized(col, row, density)
    targets = list(getattr(cam, "targetCharacterIds", None) or [])
    pose = CameraPose(
        cameraId=str(getattr(cam, "id", "") or ""),
        cameraSlot=slot,
        label=str(getattr(cam, "label", None) or f"Camera {slot + 1}"),
        enabled=bool(getattr(cam, "visible", True)),
        gridColumn=col,
        gridRow=row,
        normalizedX=float(nx),
        normalizedY=float(ny),
        x=float(getattr(cam, "x", 0) or 0),
        y=float(getattr(cam, "y", 1.6) or 1.6),
        z=float(getattr(cam, "z", 0) or 0),
        yawDegrees=float(getattr(cam, "yawDegrees", None) or orientation_to_yaw(orientation)),
        pitchDegrees=float(getattr(cam, "pitchDegrees", 0) or 0),
        rollDegrees=float(getattr(cam, "rollDegrees", 0) or 0),
        heightMeters=float(getattr(cam, "heightMeters", None) or getattr(cam, "y", 1.6) or 1.6),
        orientation=orientation,
        fovPreset=str(getattr(cam, "fovPreset", None) or "medium"),
        lensMm=float(getattr(cam, "lensMm", None) or FOV_LENS_MM.get(str(getattr(cam, "fovPreset", None) or "medium"), 35)),
        shotType=str(getattr(cam, "shotType", None) or "medium"),
        targetEntityId=str(targets[0]) if targets else "",
        targetEntityType="character" if targets else None,
    )
    return pose


def bind_pack_from_spatial(
    pack: SceneCinematographerPack | None,
    *,
    project_id: str,
    scene_id: str,
    spatial_cameras: list[Any],
    density: int,
    grid_scale: int,
) -> SceneCinematographerPack:
    pack = pack or SceneCinematographerPack(scene_id=scene_id, project_id=project_id)
    pack.project_id = project_id
    pack.scene_id = scene_id
    pack.density = density
    pack.grid_scale = grid_scale
    existing = {c.cameraId: c for c in pack.cameras}
    next_cameras: list[SceneCameraRecord] = []
    for index, cam in enumerate(spatial_cameras or []):
        slot = getattr(cam, "cameraSlot", None)
        if slot is None or int(slot) < 0:
            slot = index
        slot = int(slot)
        cam_id = str(getattr(cam, "id", "") or "")
        if not cam_id:
            continue
        baseline = pose_from_spatial(cam, slot=slot, density=density)
        rec = existing.get(cam_id)
        if rec is None:
            rec = SceneCameraRecord(
                cameraId=cam_id,
                cameraSlot=slot,
                label=baseline.label or f"Camera {slot + 1}",
                enabled=baseline.enabled,
                baseline=baseline,
                current=baseline.model_copy(deep=True),
            )
            rec.cameraStateHash = camera_state_hash(rec.current)
            rec.cameraStateVersion = 1
            rec.lineage = CameraLineage(
                cameraId=cam_id,
                cameraStateVersion=1,
                cameraStateHash=rec.cameraStateHash,
            )
        else:
            rec.baseline = baseline
            rec.enabled = baseline.enabled
            rec.cameraSlot = slot
            rec.label = baseline.label or rec.label
            if rec.cameraStateVersion <= 1 and not rec.history and not rec.lineage.locked:
                rec.current = baseline.model_copy(deep=True)
                rec.cameraStateHash = camera_state_hash(rec.current)
                rec.lineage.cameraStateHash = rec.cameraStateHash
        next_cameras.append(rec)
    pack.cameras = next_cameras
    if pack.selected_camera_id not in {c.cameraId for c in pack.cameras}:
        pack.selected_camera_id = pack.cameras[0].cameraId if pack.cameras else ""
    return pack


def get_camera(pack: SceneCinematographerPack, camera_id: str) -> SceneCameraRecord:
    rec = next((c for c in pack.cameras if c.cameraId == camera_id), None)
    if rec is None:
        raise CinematographerError("That camera is not available.")
    if not rec.enabled:
        raise CinematographerError("That camera is turned off on the Spatial Map.")
    return rec


def apply_command_to_pack(
    pack: SceneCinematographerPack,
    *,
    camera_id: str,
    operation_id: str,
    character_id: str = "",
    prop_id: str = "",
    character_name: str = "",
    prop_name: str = "",
    character_slot: int | None = None,
    prop_slot: int | None = None,
    held_by_character_id: str = "",
    orientation_patch: dict[str, Any] | None = None,
) -> SceneCinematographerPack:
    rec = get_camera(pack, camera_id)
    rec.history.append(_snapshot_current(rec))
    if len(rec.history) > 40:
        rec.history = rec.history[-40:]
    if operation_id == "orient_reset":
        _restore_orientation_from_baseline(rec)
    result = apply_operation(
        rec.current,
        operation_id,
        density=pack.density,
        character_id=character_id,
        prop_id=prop_id,
        character_name=character_name,
        prop_name=prop_name,
        character_slot=character_slot,
        prop_slot=prop_slot,
        held_by_character_id=held_by_character_id,
        orientation_patch=orientation_patch,
        baseline_lens_mm=float(rec.baseline.lensMm or 35.0),
    )
    rec.structuredCommand = result["structured"]
    spec = OPS_BY_ID.get(operation_id)
    # Orientation is a precision layer. Keep the dropdown semantic command
    # visible instead of replacing it with "adjust yaw".
    if spec is not None and spec.category == "orientation3d" and rec.displayInstruction:
        pass
    else:
        rec.displayInstruction = result["instruction"]
    bump_after_mutation(rec)
    pack.selected_camera_id = camera_id
    return pack


def undo_camera(pack: SceneCinematographerPack, camera_id: str) -> SceneCinematographerPack:
    rec = get_camera(pack, camera_id)
    if not rec.history:
        raise CinematographerError("Nothing to undo on this camera.")
    snap = rec.history.pop()
    _restore_snapshot(rec, snap)
    pack.selected_camera_id = camera_id
    return pack


def reset_camera(pack: SceneCinematographerPack, camera_id: str) -> SceneCinematographerPack:
    rec = get_camera(pack, camera_id)
    rec.history.append(_snapshot_current(rec))
    rec.current = rec.baseline.model_copy(deep=True)
    rec.structuredCommand = {}
    rec.displayInstruction = ""
    rec.userCameraPromptDelta = ""
    rec.lineage.previewStatus = "stale" if rec.lineage.previewJobId or rec.lineage.previewAssetId else "none"
    rec.lineage.locked = False
    rec.lineage.lockedStateVersion = 0
    rec.lineage.lockedStateHash = ""
    rec.lineage.lockedSnapshot = {}
    bump_after_mutation(rec)
    pack.selected_camera_id = camera_id
    return pack


def lock_camera(pack: SceneCinematographerPack, camera_id: str) -> SceneCinematographerPack:
    rec = get_camera(pack, camera_id)
    if not can_lock(rec):
        raise CinematographerError("Generate a preview of this camera setup before locking it.")
    rec.lineage.locked = True
    rec.lineage.lockedStateVersion = rec.cameraStateVersion
    rec.lineage.lockedStateHash = rec.cameraStateHash
    rec.lineage.lockedSnapshot = rec.current.model_dump()
    rec.lineage.cameraId = rec.cameraId
    pack.selected_camera_id = camera_id
    return pack


def compile_camera_context(
    rec: SceneCameraRecord,
    *,
    character_name: str = "",
    prop_name: str = "",
    held_association: str = "",
) -> dict[str, Any]:
    pose = rec.current
    cell = f"C{pose.gridColumn + 1}R{pose.gridRow + 1}"
    lines = [
        f"Camera C{pose.cameraSlot + 1}:",
        f"- Position: {cell}",
        f"- Orientation: {pose.orientation}",
        f"- Shot: {SHOT_TYPE_LABELS.get(pose.shotType, pose.shotType)}",
        f"- Angle: {pose.anglePreset.replace('_', ' ')}",
        f"- Physical offset: {pose.physicalStepOffset.forwardBack} step forward/back, "
        f"{pose.physicalStepOffset.leftRight} left/right, {pose.physicalStepOffset.vertical} vertical",
        f"- Optical zoom: {pose.opticalZoomStep:+d}",
        f"- FOV: {pose.fovPreset} ({pose.lensMm:.0f}mm equivalent)",
    ]
    if pose.targetEntityId:
        kind = pose.targetEntityType or "target"
        name = character_name or prop_name or pose.targetEntityId
        lines.append(f"- Target: {kind} {name}")
    if pose.inclusionPropId:
        extra = f" with {prop_name}" if prop_name else ""
        lines.append(f"- Prop in composition: {pose.inclusionPropId}{extra}")
    if held_association:
        lines.append(f"- Association: {held_association}")
    if pose.orientation3d.enabled:
        lines.extend(_orientation3d_prose_lines(pose))
    if rec.displayInstruction:
        lines.append(rec.displayInstruction)
    if rec.userCameraPromptDelta.strip():
        lines.append(rec.userCameraPromptDelta.strip())
    compiled = {
        "cameraId": rec.cameraId,
        "cameraSlot": rec.cameraSlot,
        "cameraStateVersion": rec.cameraStateVersion,
        "cameraStateHash": rec.cameraStateHash,
        "locked": lock_is_valid(rec),
        "pose": rec.current.model_dump(),
        "instruction": rec.displayInstruction,
        "userCameraPromptDelta": rec.userCameraPromptDelta,
        "lines": lines,
        "prose": " ".join(lines),
    }
    if pose.orientation3d.enabled:
        compiled["orientation3d"] = pose.orientation3d.model_dump()
    return compiled


def _fmt_signed_degrees(value: float) -> str:
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 0.05:
        return f"{int(round(rounded)):+d}°"
    return f"{rounded:+.1f}°"


def _yaw_cinematic_language(yaw: float) -> str:
    wrapped = wrap_yaw_degrees(yaw)
    abs_y = abs(wrapped)
    if abs_y <= 22.5:
        return "front"
    if abs_y <= 67.5:
        return "three-quarter left" if wrapped > 0 else "three-quarter right"
    if abs_y <= 112.5:
        return "profile left" if wrapped > 0 else "profile right"
    if abs_y <= 157.5:
        return "rear three-quarter left" if wrapped > 0 else "rear three-quarter right"
    return "rear"


def _pitch_cinematic_language(pitch: float) -> str:
    if pitch <= -8:
        return "elevated looking down"
    if pitch >= 8:
        return "low angle"
    return "eye level"


def _orientation3d_prose_lines(pose: CameraPose) -> list[str]:
    o3 = pose.orientation3d
    lock_label = "on" if o3.targetLock else "off"
    aim = (
        f"- 3D camera aim: yaw {_fmt_signed_degrees(pose.yawDegrees)}, "
        f"pitch {_fmt_signed_degrees(pose.pitchDegrees)}, "
        f"roll {_fmt_signed_degrees(pose.rollDegrees)}, "
        f"optical zoom {o3.zoom:.2f}x, target lock {lock_label}."
    )
    bits = [_yaw_cinematic_language(pose.yawDegrees), _pitch_cinematic_language(pose.pitchDegrees)]
    if abs(pose.rollDegrees) >= 3:
        tilt = "clockwise" if pose.rollDegrees > 0 else "counterclockwise"
        bits.append(f"subtle Dutch tilt {tilt}")
    if o3.zoom > 1.0:
        bits.append("tighter optical framing")
    elif o3.zoom < 1.0:
        bits.append("wider optical framing")
    framing = f"- Framing: {', '.join(bits)}."
    return [aim, framing]


def save_pack(db: Session, project_id: str, pack: SceneCinematographerPack) -> None:
    from datetime import datetime, timezone

    from ..spatial_map.ers_persistence import _upsert_trait

    pack.updated_at = datetime.now(timezone.utc).isoformat()
    pack.project_id = project_id
    _upsert_trait(
        db,
        project_id=project_id,
        category=CINEMATOGRAPHER_CATEGORY,
        key=pack.scene_id,
        value=pack.model_dump_json(),
        provenance="scene_creator",
    )


def load_pack(db: Session, project_id: str, scene_id: str) -> SceneCinematographerPack | None:
    from ..spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=CINEMATOGRAPHER_CATEGORY, key=scene_id)
    if not raw:
        return None
    try:
        return SceneCinematographerPack.model_validate_json(raw)
    except Exception as exc:
        logger.error("Failed to load cinematographer pack %s: %s", scene_id, exc)
        return None


def list_packs(db: Session, project_id: str) -> list[SceneCinematographerPack]:
    from ..spatial_map.ers_persistence import _list_trait_values

    out: list[SceneCinematographerPack] = []
    for raw in _list_trait_values(db, project_id=project_id, category=CINEMATOGRAPHER_CATEGORY):
        try:
            out.append(SceneCinematographerPack.model_validate_json(raw))
        except Exception:
            continue
    return out


def list_spatial_cameras(db: Session, project_id: str) -> tuple[list[Any], int, int]:
    from ..spatial_map.service import list_documents

    maps = list_documents(db, project_id)
    if not maps:
        return [], 10, 0
    doc = maps[0]
    scale = int(getattr(doc, "gridScale", 0) or 0)
    density = density_for_scale(scale)
    cams = list(doc.cameras or [])
    return cams, density, scale


def association_for(
    db: Session,
    project_id: str,
    *,
    character_id: str,
    prop_id: str,
) -> str:
    if not character_id or not prop_id:
        return ""
    try:
        from ..spatial_map.service import list_documents

        maps = list_documents(db, project_id)
    except Exception:
        return ""
    if not maps:
        return ""
    for prop in maps[0].props or []:
        pid = str(getattr(prop, "propId", "") or "")
        if pid != prop_id:
            continue
        if str(getattr(prop, "placementMode", "") or "") != "attached":
            continue
        attached = str(getattr(prop, "attachedCharacterId", "") or "")
        rel = str(getattr(prop, "relationship", "") or "")
        if attached == character_id:
            point = str(getattr(prop, "attachmentPoint", "") or "")
            rel_label = rel.replace("_", " ") or "associated with"
            extra = f" ({point.replace('_', ' ')})" if point else ""
            return f"Prop is {rel_label} the character{extra}."
    return ""


def api_preview_capability(*, api_enabled: bool, api_model: str = "") -> dict[str, Any]:
    """Honest API preview cost/quality. Never invent cheap when priced as full."""
    if not api_enabled:
        return {
            "status": "none",
            "label": "",
            "supportsDraftPreview": False,
            "supportsLowResolution": False,
            "supportsCostEstimate": False,
        }
    model = (api_model or "").strip()
    if not model:
        return {
            "status": "unsupported",
            "label": "Preview Unsupported",
            "supportsDraftPreview": False,
            "supportsLowResolution": False,
            "supportsCostEstimate": False,
        }
    # Known hosted still-image providers bill per image, not by draft resolution.
    return {
        "status": "standard_cost",
        "label": "Standard-Cost Preview Only",
        "supportsDraftPreview": False,
        "supportsLowResolution": True,
        "supportsCostEstimate": False,
        "model": model,
    }


def local_preview_capability() -> dict[str, Any]:
    return {
        "status": "economy",
        "label": "Economy Preview Available",
        "supportsDraftPreview": True,
        "supportsLowResolution": True,
        "supportsCostEstimate": False,
    }


def empty_pack(project_id: str, scene_id: str) -> SceneCinematographerPack:
    return SceneCinematographerPack(scene_id=scene_id, project_id=project_id)
