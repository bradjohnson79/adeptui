"""Compile creator presets into a normalized DSP plan."""

from __future__ import annotations

from typing import Any

from .presets import (
    DEVICE_PRESETS,
    DIRECTION_PRESETS,
    DISTANCE_PRESETS,
    SPACE_PRESETS,
    TONE_PRESETS,
    WALLA_LEVEL_SCALE,
    WALLA_PRESETS,
)


def compile_dsp_plan(profile: dict[str, Any]) -> dict[str, Any]:
    space = SPACE_PRESETS.get(str(profile.get("spacePreset") or "small_room"), SPACE_PRESETS["small_room"])
    distance = DISTANCE_PRESETS.get(
        str(profile.get("distancePreset") or "medium_close_up"), DISTANCE_PRESETS["medium_close_up"]
    )
    direction = DIRECTION_PRESETS.get(str(profile.get("directionPreset") or "center"), DIRECTION_PRESETS["center"])
    tone = TONE_PRESETS.get(str(profile.get("tonePreset") or "natural"), TONE_PRESETS["natural"])
    device = DEVICE_PRESETS.get(str(profile.get("devicePreset") or "direct"), DEVICE_PRESETS["direct"])
    walla = WALLA_PRESETS.get(str(profile.get("wallaPreset") or "none"), WALLA_PRESETS["none"])
    level_key = str(profile.get("wallaLevel") or "moderate")
    walla_scale = WALLA_LEVEL_SCALE.get(level_key, 1.0)

    processing_latency_ms = float(distance.get("latency_ms", 0)) + float(device.get("latency_ms", 0))
    tail_ms = float(space.get("tail_ms", 0))

    return {
        "kind": "deterministic_acoustic",
        "space": {
            "preset": profile.get("spacePreset"),
            "reverb_ms": space["reverb_ms"],
            "wet": space["wet"],
            "tail_ms": space["tail_ms"],
            "customPrompt": profile.get("customSpacePrompt"),
        },
        "distance": {
            "preset": profile.get("distancePreset"),
            "gain_db": distance["gain_db"],
            "hf_cut_hz": distance["hf_cut_hz"],
            "latency_ms": distance.get("latency_ms", 0),
            "customPrompt": profile.get("customDistancePrompt"),
        },
        "direction": {
            "preset": profile.get("directionPreset"),
            "pan": direction.get("pan", 0.0),
            "rear_bias": direction.get("rear_bias", 0.0),
            "brightness": direction.get("brightness", 1.0),
            "moving": bool(direction.get("moving")),
            "customPrompt": profile.get("customDirectionPrompt"),
        },
        "tone": {
            "preset": profile.get("tonePreset"),
            "low_shelf_db": tone.get("low_shelf_db", 0.0),
            "high_shelf_db": tone.get("high_shelf_db", 0.0),
            "lp_hz": tone.get("lp_hz"),
            "customPrompt": profile.get("customTonePrompt"),
        },
        "device": {
            "preset": profile.get("devicePreset"),
            "band_low_hz": device["band_low_hz"],
            "band_high_hz": device["band_high_hz"],
            "drive": device["drive"],
            "latency_ms": device.get("latency_ms", 0),
            "customPrompt": profile.get("customDevicePrompt"),
        },
        "walla": {
            "preset": profile.get("wallaPreset"),
            "level": float(walla.get("level", 0.0)) * walla_scale,
            "distance": profile.get("wallaDistance") or "mid",
            "behavior": profile.get("wallaBehavior") or "steady",
            "customPrompt": profile.get("customWallaPrompt"),
        },
        "timingHints": {
            "processingLatencyMs": processing_latency_ms,
            "tailDurationMs": tail_ms,
            # speechStartOffsetMs always remains dry-aligned (0 unless dry has leading silence)
            "speechStartOffsetMs": 0.0,
        },
        "customPrompts": {
            "space": profile.get("customSpacePrompt"),
            "distance": profile.get("customDistancePrompt"),
            "direction": profile.get("customDirectionPrompt"),
            "tone": profile.get("customTonePrompt"),
            "device": profile.get("customDevicePrompt"),
            "walla": profile.get("customWallaPrompt"),
        },
    }
