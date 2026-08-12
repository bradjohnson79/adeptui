"""Scene / Bible / Spatial Map → Voice Environment recommendation."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Scene
from .contracts import VoiceEnvironmentRecommendation
from .presets import DEVICE_PRESETS, DIRECTION_PRESETS, DISTANCE_PRESETS, SPACE_PRESETS, TONE_PRESETS, WALLA_PRESETS


def recommend_environment(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    scene_id: Optional[str] = None,
    location_id: Optional[str] = None,
) -> VoiceEnvironmentRecommendation:
    scene = db.get(Scene, scene_id) if scene_id else None
    if scene_id and not scene:
        from .errors import VoiceEnvironmentError

        raise VoiceEnvironmentError(
            "VOICE_ENVIRONMENT_SCENE_NOT_FOUND",
            "That scene could not be found in this project.",
            status_code=404,
        )

    environment_prompt = ""
    spatial_map_id = None
    resolved_location = location_id
    if scene is not None:
        environment_prompt = str(getattr(scene, "prompt", None) or getattr(scene, "title", None) or "")
        # Best-effort Spatial Map reference bundle.
        try:
            from ..spatial_map import models as sm_models

            MapRow = getattr(sm_models, "SpatialMapRow", None) or getattr(sm_models, "SpatialMap", None)
            if MapRow is not None:
                q = db.query(MapRow).filter(getattr(MapRow, "project_id", None) == project_id)
                # Prefer maps assigned to this scene when column exists.
                if hasattr(MapRow, "scene_id"):
                    rows = q.filter(MapRow.scene_id == scene_id).all() or q.limit(1).all()
                else:
                    rows = q.limit(1).all()
                if rows:
                    spatial_map_id = getattr(rows[0], "id", None)
                    environment_prompt = (
                        str(getattr(rows[0], "master_environment_prompt", None) or environment_prompt)
                    )
                    resolved_location = resolved_location or getattr(rows[0], "location_id", None)
        except Exception:
            pass

    prompt_l = (environment_prompt or "").lower()
    space = "small_room"
    if any(k in prompt_l for k in ("corridor", "hallway", "metallic", "ship")):
        space = "spaceship_corridor"
    elif any(k in prompt_l for k in ("cathedral", "church")):
        space = "cathedral"
    elif any(k in prompt_l for k in ("stadium", "arena")):
        space = "stadium"
    elif any(k in prompt_l for k in ("warehouse", "hangar")):
        space = "warehouse"
    elif any(k in prompt_l for k in ("forest", "woods")):
        space = "forest"
    elif any(k in prompt_l for k in ("street", "city")):
        space = "street"
    elif any(k in prompt_l for k in ("hall", "chamber")):
        space = "large_hall"

    device = "direct"
    if any(k in prompt_l for k in ("intercom", "comms", "radio")):
        device = "intercom"
    elif "phone" in prompt_l:
        device = "mobile_phone"

    walla = "none"
    if any(k in prompt_l for k in ("crowd", "audience", "stadium")):
        walla = "stadium"
    elif any(k in prompt_l for k in ("command", "ops", "bridge")):
        walla = "command_center"
    elif any(k in prompt_l for k in ("restaurant", "cafe")):
        walla = "restaurant"

    distance = "medium_close_up"
    direction = "slightly_right"
    tone = "natural"

    space_label = SPACE_PRESETS[space]["label"]
    reason = (
        "Recommended from live scene and spatial context. "
        f"Space reads as {space_label.lower()}."
    )
    if environment_prompt:
        reason += f" Evidence: {environment_prompt[:220]}"

    draft: dict[str, Any] = {
        "projectId": project_id,
        "characterId": character_id,
        "sceneId": scene_id,
        "locationId": resolved_location,
        "name": f"{space_label} — Medium Close-Up",
        "spacePreset": space,
        "distancePreset": distance,
        "directionPreset": direction,
        "tonePreset": tone,
        "devicePreset": device,
        "wallaPreset": walla,
        "wallaLevel": "subtle" if walla != "none" else None,
        "wallaDistance": "mid",
        "wallaBehavior": "steady",
        "source": "codirector",
    }

    return VoiceEnvironmentRecommendation(
        profileDraft=draft,
        spaceLabel=space_label,
        distanceLabel=DISTANCE_PRESETS[distance]["label"],
        directionLabel=DIRECTION_PRESETS[direction]["label"],
        toneLabel=TONE_PRESETS[tone]["label"],
        deviceLabel=DEVICE_PRESETS[device]["label"],
        wallaLabel=WALLA_PRESETS[walla]["label"],
        reason=reason,
        evidence={
            "sceneId": scene_id,
            "locationId": resolved_location,
            "spatialMapId": spatial_map_id,
            "environmentPrompt": environment_prompt or None,
        },
    )
