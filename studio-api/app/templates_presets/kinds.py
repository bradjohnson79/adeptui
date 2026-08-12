"""Enums and constants for the M3.1a Templates & Presets layer."""

from __future__ import annotations

from typing import Literal

SCHEMA_VERSION = 1
CREATIVE_ITEM_PACKAGE = "adept.creative_item.v1"
PROJECT_TYPE_PACKAGE = "adept.project_type.v1"

CreativeKind = Literal[
    "generation_template",
    "camera_preset",
    "lighting_preset",
    "color_preset",
    "look_preset",
    "audio_preset",
    "character_preset",
    "scene_preset",
]

Scope = Literal["system", "user", "project", "scene", "shot"]
Lifecycle = Literal[
    "draft",
    "in_review",
    "approved",
    "locked",
    "superseded",
    "deprecated",
    "archived",
]
Origin = Literal["builtin", "local", "imported", "shared"]
Visibility = Literal["private", "project", "user", "shared"]
BindingMode = Literal["inherit", "override", "disabled"]
ScopeLevel = Literal["project", "scene", "shot"]
ProductionUnitKind = Literal["season", "episode", "trailer", "sequence", "beat"]

CREATIVE_KINDS: tuple[str, ...] = (
    "generation_template",
    "camera_preset",
    "lighting_preset",
    "color_preset",
    "look_preset",
    "audio_preset",
    "character_preset",
    "scene_preset",
)

BINDING_SLOTS: tuple[str, ...] = (
    "default_generation_template",
    "default_camera",
    "default_lighting",
    "default_color",
    "default_look",
    "grammar_pack",
    "default_audio",
    "delivery",
)

LIBRARY_KEY_BY_KIND: dict[str, str] = {
    "generation_template": "templates_presets.generation_templates",
    "camera_preset": "templates_presets.camera_presets",
    "lighting_preset": "templates_presets.lighting_presets",
    "color_preset": "templates_presets.color_presets",
    "look_preset": "templates_presets.look_presets",
    "audio_preset": "templates_presets.generation_templates.audio",
}

# First-level project type selector (UX).
PRIMARY_PROJECT_TYPE_SLUGS: tuple[str, ...] = (
    "feature_film",
    "short_film",
    "series",
    "documentary",
    "animation",
    "talking_avatar",
    "commercial",
    "music_video",
    "social_media",
    "youtube_creator",
    "educational_explainer",
    "storyboard_previs",
    "game_cinematic",
    "video_cinematic_trailer",
    "custom",
)

LEGACY_PRODUCTION_TYPE_MAP: dict[str, str] = {
    "Short Film": "short_film",
    "Feature Film": "feature_film",
    "Series Episode": "television_episodic",
    "Commercial": "commercial",
    "Music Video": "music_video",
    "Social Video": "social_media",
    "Animation": "animation",
    "Custom": "custom",
}

RESOLUTION_BASE_LONG: dict[str, int] = {
    "720p": 1280,
    "1080p": 1920,
    "1440p": 2560,
    "4K": 3840,
}
