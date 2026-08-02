"""Creative M4.10 emotion presets for IndexTTS2-compatible vectors."""

from __future__ import annotations

from typing import Any

SUPPORTED_VECTORS = ("joy", "sadness", "anger", "fear", "surprise", "disgust", "contempt")
_ALIASES = {"hate": "contempt"}


def normalize_mix(mix: dict[str, float] | None) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for raw_key, raw_value in (mix or {}).items():
        key = _ALIASES.get(str(raw_key).strip().lower(), str(raw_key).strip().lower())
        if key not in SUPPORTED_VECTORS:
            continue
        try:
            value = max(0.0, float(raw_value))
        except Exception:
            continue
        if value > 0:
            cleaned[key] = cleaned.get(key, 0.0) + value
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {key: round(value / total, 4) for key, value in cleaned.items()}


def creative_summary(preset: dict[str, Any]) -> str:
    vector = preset.get("emotionVector") or {}
    top = sorted(vector.items(), key=lambda item: item[1], reverse=True)
    top_label = top[0][0] if top else "neutral"
    intensity = preset.get("intensity") or "moderate"
    delivery = preset.get("delivery") or "natural"
    pacing = preset.get("pacing") or "steady"
    return f"{preset.get('name')}: {top_label} led, {intensity} intensity, {delivery}, {pacing} pacing."


PRESETS: list[dict[str, Any]] = [
    {
        "id": "quiet-grief",
        "name": "Quiet Grief",
        "emotionVector": normalize_mix({"sadness": 0.82, "fear": 0.1, "surprise": 0.08}),
        "intensity": "low",
        "delivery": "hushed, restrained, intimate",
        "pacing": "slow with careful spacing",
        "breath": "soft catches between phrases",
        "notes": "Best for loss held close rather than cried aloud.",
    },
    {
        "id": "contained-anger",
        "name": "Contained Anger",
        "emotionVector": normalize_mix({"anger": 0.7, "contempt": 0.2, "fear": 0.1}),
        "intensity": "medium",
        "delivery": "tight, precise, clipped",
        "pacing": "measured with firm stops",
        "breath": "compressed breath, little air release",
        "notes": "Feels controlled and dangerous, not explosive.",
    },
    {
        "id": "warm-reassurance",
        "name": "Warm Reassurance",
        "emotionVector": normalize_mix({"joy": 0.62, "sadness": 0.14, "fear": 0.08, "surprise": 0.16}),
        "intensity": "low",
        "delivery": "gentle, supportive, present",
        "pacing": "steady and patient",
        "breath": "open breath with easy releases",
        "notes": "Comforts without sounding overly cheerful.",
    },
    {
        "id": "fear-beneath-calm",
        "name": "Fear Beneath Calm",
        "emotionVector": normalize_mix({"fear": 0.58, "sadness": 0.17, "surprise": 0.25}),
        "intensity": "medium",
        "delivery": "controlled surface with strain underneath",
        "pacing": "steady with slight hesitation",
        "breath": "held breath on key words",
        "notes": "Outward composure with inner instability.",
    },
    {
        "id": "embarrassed-sincerity",
        "name": "Embarrassed Sincerity",
        "emotionVector": normalize_mix({"joy": 0.18, "fear": 0.32, "sadness": 0.1, "surprise": 0.4}),
        "intensity": "medium",
        "delivery": "earnest, slightly flustered",
        "pacing": "uneven with self-corrections",
        "breath": "small nervous breaths",
        "notes": "Honest feeling breaking through social discomfort.",
    },
    {
        "id": "defensive-humor",
        "name": "Defensive Humor",
        "emotionVector": normalize_mix({"joy": 0.28, "fear": 0.26, "contempt": 0.16, "surprise": 0.3}),
        "intensity": "medium",
        "delivery": "quick wit used as cover",
        "pacing": "brisk with sharp punch words",
        "breath": "light, restless breath",
        "notes": "Sounds funny on the surface and guarded underneath.",
    },
    {
        "id": "soft-pleading",
        "name": "Soft Pleading",
        "emotionVector": normalize_mix({"sadness": 0.35, "fear": 0.45, "joy": 0.2}),
        "intensity": "medium",
        "delivery": "gentle, vulnerable, reaching",
        "pacing": "slower with upward ends",
        "breath": "audible breath before requests",
        "notes": "Appeals softly rather than desperately.",
    },
    {
        "id": "growing-panic",
        "name": "Growing Panic",
        "emotionVector": normalize_mix({"fear": 0.68, "surprise": 0.22, "sadness": 0.1}),
        "intensity": "high",
        "delivery": "composure slipping line by line",
        "pacing": "accelerating with shorter pauses",
        "breath": "breath gets tighter as the line continues",
        "notes": "Escalates inside the line instead of starting fully panicked.",
    },
    {
        "id": "cold-authority",
        "name": "Cold Authority",
        "emotionVector": normalize_mix({"contempt": 0.46, "anger": 0.34, "disgust": 0.2}),
        "intensity": "medium",
        "delivery": "flat, dominant, unamused",
        "pacing": "deliberate and controlled",
        "breath": "minimal breath noise",
        "notes": "Commands without raising volume.",
    },
    {
        "id": "tender-vulnerability",
        "name": "Tender Vulnerability",
        "emotionVector": normalize_mix({"sadness": 0.44, "joy": 0.31, "fear": 0.25}),
        "intensity": "low",
        "delivery": "open-hearted, careful, exposed",
        "pacing": "slow and attentive",
        "breath": "warm open breath",
        "notes": "For intimate honesty without melodrama.",
    },
    {
        "id": "joyful-relief",
        "name": "Joyful Relief",
        "emotionVector": normalize_mix({"joy": 0.66, "surprise": 0.22, "sadness": 0.12}),
        "intensity": "medium",
        "delivery": "released, bright, grateful",
        "pacing": "easing from quick to settled",
        "breath": "breath opens after a held start",
        "notes": "The danger passed and the body finally knows it.",
    },
    {
        "id": "exhausted-determination",
        "name": "Exhausted Determination",
        "emotionVector": normalize_mix({"sadness": 0.24, "anger": 0.29, "fear": 0.17, "joy": 0.3}),
        "intensity": "medium",
        "delivery": "tired but unwilling to stop",
        "pacing": "slowed by fatigue, still purposeful",
        "breath": "heavy recovery breath between thoughts",
        "notes": "Fatigue should be audible without losing resolve.",
    },
]

PRESET_INDEX = {preset["id"]: {**preset, "summary": creative_summary(preset)} for preset in PRESETS}


def list_presets() -> list[dict[str, Any]]:
    return [PRESET_INDEX[preset["id"]] for preset in PRESETS]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    return PRESET_INDEX.get(preset_id)
