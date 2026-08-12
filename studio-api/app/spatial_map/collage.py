from __future__ import annotations

from typing import Any

from .errors import SpatialMapErrorCode, raise_http_error
from .schemas import (
    REQUIRED_360_DIRECTIONS,
    Spatial360Collage,
    Spatial360View,
    SpatialCaptureMode,
    SpatialDirection,
)

YAW_BY_DIRECTION: dict[str, float] = {
    "front": 0.0,
    "front_right": 45.0,
    "right": 90.0,
    "rear_right": 135.0,
    "rear": 180.0,
    "rear_left": 225.0,
    "left": 270.0,
    "front_left": 315.0,
    "ceiling": 0.0,
    "floor": 0.0,
    "hero": 0.0,
}


def _required_view(direction: str) -> Spatial360View:
    return Spatial360View(direction=direction, yawDegrees=YAW_BY_DIRECTION[direction])


def _token_overlap(left: str, right: str) -> int:
    left_tokens = {tok.strip(" ,.;:").lower() for tok in left.split() if tok.strip(" ,.;:")}
    right_tokens = {tok.strip(" ,.;:").lower() for tok in right.split() if tok.strip(" ,.;:")}
    return len(left_tokens & right_tokens)


def _ensure_supported_direction(direction: str) -> None:
    if direction not in YAW_BY_DIRECTION:
        raise raise_http_error(SpatialMapErrorCode.COLLAGE_DIRECTION_INVALID, direction=direction)


def create_collage(
    *,
    master_environment_prompt: str,
    capture_mode: SpatialCaptureMode = "environment_only",
    camera_height_meters: float = 1.6,
    lens_mm: float = 24.0,
    hero_direction: SpatialDirection | None = None,
) -> Spatial360Collage:
    views = [_required_view(direction) for direction in REQUIRED_360_DIRECTIONS]
    collage = Spatial360Collage(
        masterEnvironmentPrompt=(master_environment_prompt or "").strip(),
        captureMode=capture_mode,
        cameraHeightMeters=camera_height_meters,
        lensMm=lens_mm,
        heroDirection=hero_direction,
        views=views,
    )
    collage.continuityWarnings = validate_adjacent_continuity(collage)
    collage.minimumDirectionsMet = _minimum_directions_met(collage)
    return collage


def upsert_view(
    collage: Spatial360Collage,
    *,
    direction: str,
    asset_id: str | None = None,
    prompt: str = "",
    status: str = "planned",
) -> Spatial360Collage:
    _ensure_supported_direction(direction)
    views = [view for view in collage.views if view.direction != direction]
    views.append(
        Spatial360View(
            direction=direction,
            yawDegrees=YAW_BY_DIRECTION[direction],
            assetId=asset_id,
            prompt=prompt,
            status=status,  # type: ignore[arg-type]
        )
    )
    ordered = sorted(views, key=lambda view: list(YAW_BY_DIRECTION).index(view.direction))
    collage.views = ordered
    collage.continuityWarnings = validate_adjacent_continuity(collage)
    collage.minimumDirectionsMet = _minimum_directions_met(collage)
    return collage


def _minimum_directions_met(collage: Spatial360Collage) -> bool:
    present = {view.direction for view in collage.views}
    return all(direction in present for direction in REQUIRED_360_DIRECTIONS)


def validate_adjacent_continuity(collage: Spatial360Collage) -> list[str]:
    warnings: list[str] = []
    if not _minimum_directions_met(collage):
        warnings.append("360 collage is missing one or more required directions.")
    ordered_required = [next((view for view in collage.views if view.direction == direction), None) for direction in REQUIRED_360_DIRECTIONS]
    for index, current in enumerate(ordered_required):
        if current is None:
            continue
        nxt = ordered_required[(index + 1) % len(ordered_required)]
        if nxt is None:
            continue
        if abs((nxt.yawDegrees - current.yawDegrees) % 360.0 - 45.0) > 1e-6:
            warnings.append(f"{current.direction} does not rotate cleanly into {nxt.direction}.")
        if current.prompt and nxt.prompt and _token_overlap(current.prompt, nxt.prompt) < 2:
            warnings.append(f"{current.direction} and {nxt.direction} prompts may describe different worlds.")
        if current.assetId and not nxt.assetId:
            warnings.append(f"{nxt.direction} is missing an adjacent capture beside {current.direction}.")
    return sorted(set(warnings))


def generate_360_plan(
    *,
    master_environment_prompt: str,
    include_characters: bool = False,
    camera_height_meters: float = 1.6,
    lens_mm: float = 24.0,
) -> dict[str, Any]:
    prompts = build_directional_prompts(
        master_environment_prompt=master_environment_prompt,
        include_characters=include_characters,
        camera_height_meters=camera_height_meters,
        lens_mm=lens_mm,
    )
    shots = [
        {
            "direction": direction,
            "yawDegrees": YAW_BY_DIRECTION[direction],
            "prompt": prompts[direction],
        }
        for direction in REQUIRED_360_DIRECTIONS
    ]
    return {
        "masterEnvironmentPrompt": (master_environment_prompt or "").strip(),
        "captureMode": "include_characters" if include_characters else "environment_only",
        "cameraHeightMeters": camera_height_meters,
        "lensMm": lens_mm,
        "shots": shots,
    }


def build_directional_prompts(
    *,
    master_environment_prompt: str,
    include_characters: bool = False,
    camera_height_meters: float = 1.6,
    lens_mm: float = 24.0,
) -> dict[str, str]:
    base = (master_environment_prompt or "").strip()
    character_clause = (
        "Include the existing character placements consistently."
        if include_characters
        else "Environment only. Do not introduce characters."
    )
    prompts: dict[str, str] = {}
    for direction in REQUIRED_360_DIRECTIONS:
        prompts[direction] = (
            f"{base} Same environment, same lighting, same set dressing. "
            f"Rotate the camera to {direction.replace('_', ' ')} ({int(YAW_BY_DIRECTION[direction])} degrees yaw). "
            f"Keep the camera height locked at {camera_height_meters:.2f}m and the lens locked at {lens_mm:.0f}mm. "
            f"{character_clause} Do not redesign or remix the world."
        ).strip()
    return prompts
