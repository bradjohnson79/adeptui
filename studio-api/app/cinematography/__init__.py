from .catalog import (
    CAMERA_FOCUS_ENVIRONMENT_ID,
    CAMERA_LENS_IDS,
    CAMERA_LENS_LABELS,
    CAMERA_SHOT_IDS,
    CAMERA_SHOT_LABELS,
    LENS_LABELS,
    LENS_VALUES,
    LIGHTING_MOOD_LABELS,
    LIGHTING_MOODS,
    LIGHTING_PRESET_IDS,
    LIGHTING_PRESET_LABELS,
    SHOT_SIZE_IDS,
    SHOT_SIZE_LABELS,
    SHOT_SIZES,
    camera_focus_label,
    camera_lens_label,
    camera_shot_label,
    format_camera_clip_label,
    hydrate_camera_lens,
    hydrate_camera_shot,
    hydrate_lighting_preset,
    lighting_preset_label,
    normalize_catalog_id,
)
from .compile import camera_nl_instruction, compile_canonical_camera

compile_camera_instruction_text = camera_nl_instruction


def camera_has_semantics(camera):
    return bool(camera)


__all__ = [
    "CAMERA_FOCUS_ENVIRONMENT_ID",
    "CAMERA_LENS_IDS",
    "CAMERA_LENS_LABELS",
    "CAMERA_SHOT_IDS",
    "CAMERA_SHOT_LABELS",
    "LENS_LABELS",
    "LENS_VALUES",
    "LIGHTING_MOOD_LABELS",
    "LIGHTING_MOODS",
    "LIGHTING_PRESET_IDS",
    "LIGHTING_PRESET_LABELS",
    "SHOT_SIZE_IDS",
    "SHOT_SIZE_LABELS",
    "SHOT_SIZES",
    "camera_focus_label",
    "camera_has_semantics",
    "camera_lens_label",
    "camera_nl_instruction",
    "camera_shot_label",
    "compile_camera_instruction_text",
    "compile_canonical_camera",
    "format_camera_clip_label",
    "hydrate_camera_lens",
    "hydrate_camera_shot",
    "hydrate_lighting_preset",
    "lighting_preset_label",
    "normalize_catalog_id",
]
