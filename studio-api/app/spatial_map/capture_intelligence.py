"""Co-Director 360° Scene Capture Intelligence.

One master environment prompt. The camera rotates. The world does not rewrite itself.
"""

from __future__ import annotations

import math
from typing import Iterable

from .collage import YAW_BY_DIRECTION, generate_360_plan
from .schemas import (
    REQUIRED_360_DIRECTIONS,
    SpatialCapturePlan,
    SpatialCapturePlanBody,
    SpatialCaptureShot,
    SpatialCharacterPlacement,
    SpatialMapDocument,
    SpatialPropPlacement,
)


def _angle_delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _bearing_degrees(*, from_x: float, from_z: float, to_x: float, to_z: float) -> float:
    # Yaw 0 = +Z (front), increasing clockwise toward +X (right).
    dx = to_x - from_x
    dz = to_z - from_z
    return (math.degrees(math.atan2(dx, dz)) + 360.0) % 360.0


def _visibility_for_yaw(
    *,
    yaw_degrees: float,
    camera_x: float,
    camera_z: float,
    object_x: float,
    object_z: float,
    label: str,
) -> str | None:
    bearing = _bearing_degrees(from_x=camera_x, from_z=camera_z, to_x=object_x, to_z=object_z)
    delta = _angle_delta(bearing, yaw_degrees)
    if delta <= 35:
        return f"{label} visible ahead"
    if delta <= 70:
        side = "right" if ((bearing - yaw_degrees + 360.0) % 360.0) < 180.0 else "left"
        return f"{label} partially visible at {side} edge"
    if delta <= 110:
        return f"{label} occluded / leaving frame"
    return None


def _spatial_visibility_clause(
    document: SpatialMapDocument,
    *,
    yaw_degrees: float,
    include_characters: bool,
) -> str:
    camera = next((c for c in document.cameras if c.hero), None) or (
        document.cameras[0] if document.cameras else None
    )
    cam_x = camera.x if camera else 0.0
    cam_z = camera.z if camera else 0.0

    notes: list[str] = []
    props: Iterable[SpatialPropPlacement] = document.props
    for prop in props:
        note = _visibility_for_yaw(
            yaw_degrees=yaw_degrees,
            camera_x=cam_x,
            camera_z=cam_z,
            object_x=prop.x,
            object_z=prop.z,
            label=prop.label or "Prop",
        )
        if note:
            notes.append(note)

    if include_characters:
        characters: Iterable[SpatialCharacterPlacement] = document.characters
        for character in characters:
            note = _visibility_for_yaw(
                yaw_degrees=yaw_degrees,
                camera_x=cam_x,
                camera_z=cam_z,
                object_x=character.x,
                object_z=character.z,
                label=character.label or "Character",
            )
            if note:
                notes.append(note)
    else:
        notes.append("No characters in frame.")

    for anchor in document.anchors:
        note = _visibility_for_yaw(
            yaw_degrees=yaw_degrees,
            camera_x=cam_x,
            camera_z=cam_z,
            object_x=anchor.x,
            object_z=anchor.z,
            label=anchor.label or "Anchor",
        )
        if note:
            notes.append(note)

    if not notes:
        return "Reveal the environment in this direction with no forced set dressing changes."
    return "Spatial awareness: " + "; ".join(notes) + "."


def build_directional_prompts_for_document(
    document: SpatialMapDocument,
    *,
    master_environment_prompt: str,
    include_characters: bool,
    camera_height_meters: float,
    lens_mm: float,
) -> dict[str, str]:
    base = (master_environment_prompt or "").strip()
    character_clause = (
        "Include placed characters from the Spatial Map consistently."
        if include_characters
        else "Environment only. Do not introduce characters."
    )
    prompts: dict[str, str] = {}
    for direction in REQUIRED_360_DIRECTIONS:
        yaw = YAW_BY_DIRECTION[direction]
        spatial_clause = _spatial_visibility_clause(
            document,
            yaw_degrees=yaw,
            include_characters=include_characters,
        )
        prompts[direction] = (
            f"{base} Same environment, same lighting, same materials, same time of day. "
            f"Camera facing {direction.replace('_', ' ')} at {int(yaw)} degrees yaw. "
            f"Keep camera height locked at {camera_height_meters:.2f}m and lens locked at {lens_mm:.0f}mm. "
            f"{character_clause} {spatial_clause} "
            f"Do not redesign the world. Only the camera orientation changes."
        ).strip()
    return prompts


def build_scene_capture_plan(document: SpatialMapDocument, body: SpatialCapturePlanBody) -> SpatialCapturePlan:
    master_prompt = (body.masterEnvironmentPrompt or document.masterEnvironmentPrompt or "").strip()
    if not master_prompt:
        master_prompt = (
            f"{document.title}. Consistent cinematic environment. Ultra consistent architecture. "
            "No redesign between views."
        ).strip()
    include_characters = bool(body.includeCharacters)
    payload = generate_360_plan(
        master_environment_prompt=master_prompt,
        include_characters=include_characters,
        camera_height_meters=body.cameraHeightMeters,
        lens_mm=body.lensMm,
    )
    directional_prompts = build_directional_prompts_for_document(
        document,
        master_environment_prompt=master_prompt,
        include_characters=include_characters,
        camera_height_meters=body.cameraHeightMeters,
        lens_mm=body.lensMm,
    )
    shots = [
        SpatialCaptureShot(
            direction=shot["direction"],
            yawDegrees=shot["yawDegrees"],
            prompt=directional_prompts[shot["direction"]],
        )
        for shot in payload["shots"]
    ]
    instructions = [
        "The environment is created once. The camera rotates around the same environment.",
        "Use one master environment prompt for the full 360 set.",
        "Rotate the camera only; do not invent eight different environments.",
        f"Lock camera height at {body.cameraHeightMeters:.2f}m through every rotation.",
        f"Lock lens at {body.lensMm:.0f}mm for the entire capture.",
        "Preserve exposure, key direction, fill, color temperature, and time of day.",
        "Use Spatial Map placements to decide what becomes visible, leaves frame, or is occluded.",
        "Coordinate system remains adept-world-v1 internally; creator-facing language stays human-friendly.",
        "Provider honesty: approximate translation unless a provider advertises native coordinates.",
    ]
    return SpatialCapturePlan(
        documentId=document.id,
        captureMode="include_characters" if include_characters else "environment_only",
        masterEnvironmentPrompt=master_prompt,
        cameraHeightMeters=body.cameraHeightMeters,
        lensMm=body.lensMm,
        providerHonesty=document.providerHonesty,
        shots=shots,
        instructions=instructions,
    )
