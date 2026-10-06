"""Canonical PoseCraft scene operations used by API and Co-Director.

These are the only mutation verbs. They never touch Babylon or Fire3D internals.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

from .schemas import (
    CameraState,
    FigureInstance,
    JointRotation,
    PoseCraftObject,
    PoseCraftScene,
    PoseCraftShot,
)
from .vec3 import as_vec3

FocusKind = Literal["stage", "figure", "object", "head", "face", "torso"]


def _find_figure(scene: PoseCraftScene, figure_id: str) -> FigureInstance | None:
    for figure in scene.figures:
        if figure.id == figure_id or figure.name.lower() == figure_id.lower():
            return figure
    return None


def _find_object(scene: PoseCraftScene, object_id: str) -> PoseCraftObject | None:
    for obj in scene.objects:
        if obj.id == object_id or obj.name.lower() == object_id.lower():
            return obj
    return None


def place_figure(scene: PoseCraftScene, figure_id: str, x: float, z: float, y: float = 0.0, rotation_y: float | None = None) -> bool:
    figure = _find_figure(scene, figure_id)
    if figure is None:
        return False
    figure.position = {"x": float(x), "y": float(y), "z": float(z)}
    if rotation_y is not None:
        figure.rotationY = float(rotation_y)
        figure.rotation = {**as_vec3(figure.rotation), "y": float(rotation_y)}
    return True


def move_object(scene: PoseCraftScene, object_id: str, *, x: float | None = None, y: float | None = None, z: float | None = None, rotation: dict[str, float] | None = None, scale: dict[str, float] | None = None) -> bool:
    obj = _find_object(scene, object_id)
    if obj is None:
        return False
    pos = as_vec3(obj.position)
    if x is not None:
        pos["x"] = float(x)
    if y is not None:
        pos["y"] = float(y)
    if z is not None:
        pos["z"] = float(z)
    obj.position = pos
    if rotation:
        obj.rotation = as_vec3(rotation)
    if scale:
        obj.scale = as_vec3(scale, default_y=1.0)
    return True


def sit_on_object(scene: PoseCraftScene, figure_id: str, object_id: str) -> dict[str, Any]:
    """Place pelvis relative to the object, apply a sitting starting pose.

    Honest: initial placement, not a physically perfect IK solve.
    """
    figure = _find_figure(scene, figure_id)
    obj = _find_object(scene, object_id)
    if figure is None or obj is None:
        return {"applied": False, "error": "figure or object not found"}
    seat = as_vec3(obj.position)
    height = float((obj.size or {}).get("y") or 0.45)
    figure.position = {"x": seat["x"], "y": max(height * 0.55, 0.38), "z": seat["z"]}
    yaw = float((obj.rotation or {}).get("y") or 0.0)
    figure.rotationY = yaw
    figure.rotation = {"x": 0.0, "y": yaw, "z": 0.0}
    figure.poseId = "rest-seated"
    figure.poseLabel = "Sitting"
    pose = dict(figure.pose or {})
    pose["pelvis"] = JointRotation(x=8.0, y=0.0, z=0.0)
    pose["leftHip"] = JointRotation(x=72.0, y=0.0, z=8.0)
    pose["rightHip"] = JointRotation(x=72.0, y=0.0, z=-8.0)
    pose["leftKnee"] = JointRotation(x=-82.0, y=0.0, z=0.0)
    pose["rightKnee"] = JointRotation(x=-82.0, y=0.0, z=0.0)
    pose["spine"] = JointRotation(x=6.0, y=0.0, z=0.0)
    figure.pose = pose
    return {"applied": True, "honestLabel": "Initial sit placement — refine by hand if needed."}


def look_at(scene: PoseCraftScene, figure_id: str, *, target_figure_id: str | None = None, target_object_id: str | None = None) -> dict[str, Any]:
    figure = _find_figure(scene, figure_id)
    if figure is None:
        return {"applied": False, "error": "figure not found"}
    target_pos = None
    target_id = None
    if target_figure_id:
        other = _find_figure(scene, target_figure_id)
        if other:
            target_pos = as_vec3(other.position, default_y=1.5)
            target_id = other.id
    if target_pos is None and target_object_id:
        obj = _find_object(scene, target_object_id)
        if obj:
            target_pos = as_vec3(obj.position, default_y=0.8)
            target_id = obj.id
    if target_pos is None:
        return {"applied": False, "error": "look target not found"}
    origin = as_vec3(figure.position)
    dx = target_pos["x"] - origin["x"]
    dz = target_pos["z"] - origin["z"]
    yaw = math.degrees(math.atan2(dx, dz)) if (dx or dz) else figure.rotationY
    figure.rotationY = yaw
    figure.rotation = {"x": 0.0, "y": yaw, "z": 0.0}
    figure.eyelineTargetId = target_id
    pose = dict(figure.pose or {})
    pose["head"] = JointRotation(x=0.0, y=8.0 if dx >= 0 else -8.0, z=0.0)
    figure.pose = pose
    return {"applied": True, "targetId": target_id}


def focus_subject(scene: PoseCraftScene, *, kind: FocusKind, subject_id: str | None = None) -> CameraState:
    camera = scene.camera
    target = {"x": 0.0, "y": 1.2, "z": 0.0}
    radius = 8.0
    if kind == "stage":
        if scene.figures:
            xs = [as_vec3(f.position)["x"] for f in scene.figures]
            zs = [as_vec3(f.position)["z"] for f in scene.figures]
            target = {"x": sum(xs) / len(xs), "y": 1.2, "z": sum(zs) / len(zs)}
        radius = 10.0
    elif kind in {"figure", "torso", "head", "face"} and subject_id:
        figure = _find_figure(scene, subject_id)
        if figure:
            pos = as_vec3(figure.position)
            heights = {"figure": 0.95, "torso": 1.05, "head": 1.62, "face": 1.68}
            target = {"x": pos["x"], "y": heights.get(kind, 1.2), "z": pos["z"]}
            radius = {"figure": 3.2, "torso": 1.8, "head": 0.55, "face": 0.42}.get(kind, 3.2)
    elif kind == "object" and subject_id:
        obj = _find_object(scene, subject_id)
        if obj:
            pos = as_vec3(obj.position)
            target = {"x": pos["x"], "y": pos["y"] + 0.4, "z": pos["z"]}
            radius = 2.4
    camera.target = target
    camera.radius = radius
    camera.minZ = 0.05
    camera.focusId = subject_id
    camera.focusKind = kind
    scene.camera = camera
    return camera


def replace_human_with_figure(scene: PoseCraftScene, object_id: str, figure: FigureInstance) -> dict[str, Any]:
    """Place a PoseCraft figure at a detected-human object. The static person stays an object."""
    obj = _find_object(scene, object_id)
    if obj is None:
        return {"applied": False, "error": "object not found"}
    if not obj.detectedHuman:
        return {"applied": False, "error": "object is not a detected person"}
    pos = as_vec3(obj.position)
    yaw = float((obj.rotation or {}).get("y") or 0.0)
    figure.position = {"x": pos["x"], "y": 0.0, "z": pos["z"]}
    figure.rotationY = yaw
    figure.rotation = {"x": 0.0, "y": yaw, "z": 0.0}
    scene.figures.append(figure)
    scene.selectedFigureId = figure.id
    obj.visible = False
    obj.name = f"{obj.name} (replaced)"
    return {"applied": True, "figureId": figure.id, "objectId": obj.id, "keptStaticPerson": False}


def save_shot(scene: PoseCraftScene, name: str, *, freeze_transforms: bool = True) -> PoseCraftShot:
    shot = PoseCraftShot(
        shotId=str(uuid.uuid4()),
        name=name[:120] or "Shot",
        camera=scene.camera.model_copy(deep=True),
        cameraId=scene.selectedCameraId,
        figureTransforms={
            f.id: {"position": as_vec3(f.position), "rotationY": f.rotationY, "pose": f.pose}
            for f in scene.figures
        }
        if freeze_transforms
        else {},
        objectTransforms={
            o.id: {"position": as_vec3(o.position), "rotation": as_vec3(o.rotation), "scale": as_vec3(o.scale, default_y=1.0)}
            for o in scene.objects
        }
        if freeze_transforms
        else {},
    )
    scene.shots.append(shot)
    scene.selectedShotId = shot.shotId
    return shot
