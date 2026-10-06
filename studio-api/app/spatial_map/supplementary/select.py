"""Choose the two supplementary cameras that maximize information gain."""

from __future__ import annotations

from typing import Any

from .contracts import CAMERA_ROLES, CameraRole


def _env_kind(scene_description: str, environment_type: str = "") -> str:
    blob = f"{environment_type} {scene_description}".lower()
    if any(tok in blob for tok in ("corridor", "hallway", "passage", "elevator")):
        return "corridor"
    if any(tok in blob for tok in ("facade", "exterior", "outside", "street")):
        return "exterior"
    if any(tok in blob for tok in ("room", "chamber", "interior", "office", "kitchen")):
        return "room"
    return "uncertain"


def select_camera_role(
    *,
    scene_description: str = "",
    environment_type: str = "",
    slot: str = "A",
    accepted_role_a: CameraRole | None = None,
    remaining_unknown: list[str] | None = None,
) -> dict[str, Any]:
    """Pick one camera. View B targets residual uncertainty after Master + A."""
    kind = _env_kind(scene_description, environment_type)
    unknown = [str(x).lower() for x in (remaining_unknown or [])]
    if slot == "B":
        used = accepted_role_a
        if kind == "corridor":
            role: CameraRole = "LEFT_SIDE" if used == "REVERSE" else "REVERSE"
            if any("door" in u or "chamber" in u or "side" in u for u in unknown):
                role = "LEFT_SIDE" if used != "LEFT_SIDE" else "RIGHT_SIDE"
            if any("behind" in u or "reverse" in u or "far end" in u for u in unknown):
                role = "REVERSE" if used != "REVERSE" else "CORRIDOR_FACING"
        elif kind == "room":
            role = "ROOM_FACING" if used == "OPPOSITE_CORNER" else "OPPOSITE_CORNER"
            if any("rear" in u or "behind" in u for u in unknown):
                role = "REAR" if used != "REAR" else "OPPOSITE_CORNER"
        elif kind == "exterior":
            role = "LEFT_SIDE" if used == "REAR" else "REAR"
        else:
            role = "RIGHT_SIDE" if used == "REVERSE" else "REVERSE"
        if used and role == used:
            role = next((item for item in CAMERA_ROLES if item != used), "REAR")
        reason = (
            "View B targets remaining uncertainty after the observed master and accepted View A. "
            "It is not a second pretty angle of the same already-visible volume."
        )
        return {"cameraRole": role, "environmentKind": kind, "slot": "B", "reason": reason}

    if kind == "corridor":
        role = "REVERSE"
        reason = "A reverse look from the far end exposes the corridor the master hides behind the camera."
    elif kind == "room":
        role = "OPPOSITE_CORNER"
        reason = "The opposite corner reveals walls and openings poorly visible from a front-corner master."
    elif kind == "exterior":
        role = "REAR"
        reason = "A rear/side angle exposes the hidden facade the master does not show."
    else:
        role = "REVERSE"
        reason = "A reverse camera is the highest-gain first view when the layout is still uncertain."
    return {"cameraRole": role, "environmentKind": kind, "slot": "A", "reason": reason}


def prompt_for_role(
    role: CameraRole,
    *,
    scene_description: str = "",
) -> str:
    place = (scene_description or "this environment").strip()
    transforms: dict[CameraRole, str] = {
        "REVERSE": (
            "from a camera positioned on the opposite side of the space, looking back toward "
            "the original camera position"
        ),
        "LEFT_SIDE": "from a camera on the left side, looking across the space toward the right-hand architecture",
        "RIGHT_SIDE": "from a camera on the right side, looking across the space toward the left-hand architecture",
        "REAR": "from a camera behind the original viewpoint, showing the rear of this location",
        "OPPOSITE_CORNER": "from the opposite corner of the room, looking back through the space",
        "ELEVATED": "from a slightly elevated camera that reveals floor layout and openings without becoming a map",
        "ROOM_FACING": "from inside the room, facing the opening or wall that was poorly visible in the master",
        "CORRIDOR_FACING": "looking toward an important doorway or chamber along the corridor, not a restyle of the master",
    }
    transform = transforms[role]
    return (
        f"Show this exact same environment ({place}) {transform}. "
        "Preserve the same architecture, doors, windows, elevators, room openings, wall materials, "
        "floors, major props or landmarks, lighting identity, and structural relationships. "
        "This is the same physical location from another viewpoint, not a redesign. "
        "Do not beautify. Do not add rooms, doors, or major structures that are not implied by the source. "
        "The new camera must expose spatial information that was obscured or ambiguous in the original view."
    )
