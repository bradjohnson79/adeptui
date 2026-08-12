"""Heuristic routing for Phase 2 foundation specialists."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .roster import SPECIALIST_IDS

_DEFAULT_SPECIALISTS: tuple[str, ...] = (
    "story_architect",
    "cinematography_director",
)

_INTENT_MAP: tuple[tuple[set[str], tuple[str, ...]], ...] = (
    ({"write_story", "revise_story", "develop_concept", "write_scene"}, ("story_architect", "editor")),
    ({"create_character", "revise_character"}, ("character_architect", "performance_director")),
    ({"design_location", "plan_scene"}, ("world_builder", "production_designer")),
    ({"create_shot_list", "create_storyboard", "prepare_image_generation"}, ("cinematography_director", "lighting_director")),
    ({"prepare_video_generation", "assemble_sequence"}, ("editor", "cinematography_director")),
    ({"revise_dialogue", "plan_audio"}, ("performance_director", "sound_director")),
    ({"review_continuity", "review_asset"}, ("continuity_supervisor", "editor")),
)

_KEYWORD_MAP: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("staging", "shot", "camera", "storyboard", "frame", "lens", "coverage", "blocking"), ("cinematography_director", "performance_director")),
    (("character", "hero", "villain", "arc", "motivation"), ("character_architect", "performance_director")),
    (("world", "location", "setting", "culture", "history"), ("world_builder", "production_designer")),
    (("light", "lighting", "mood", "shadow", "contrast"), ("lighting_director", "cinematic_psychology")),
    (("edit", "cut", "pace", "sequence", "montage"), ("editor",)),
    (("sound", "music", "voice", "audio", "ambience"), ("sound_director", "performance_director")),
    (("performance", "dialogue", "actor", "delivery", "emotion"), ("performance_director", "cinematic_psychology")),
    (("continuity", "match", "consistency", "callback"), ("continuity_supervisor",)),
)

_PROFILE_MAP: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("animation", "anime"), ("performance_director", "production_designer")),
    (("documentary", "doc"), ("editor", "sound_director")),
    (("commercial", "brand"), ("production_designer", "editor")),
    (("horror", "thriller"), ("lighting_director", "cinematic_psychology")),
    (("podcast", "audio"), ("sound_director", "performance_director")),
)


def _normalized_intent(intent: Any) -> str:
    if intent is None:
        return ""
    if isinstance(intent, str):
        return intent.strip().lower()
    primary = getattr(intent, "primaryIntent", None)
    if isinstance(primary, str):
        return primary.strip().lower()
    if isinstance(intent, dict):
        value = intent.get("primaryIntent") or intent.get("intent")
        if isinstance(value, str):
            return value.strip().lower()
    return ""


def _flatten_strings(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            out.append(value.strip().lower())
    return out


def _append_unique(target: list[str], candidates: Iterable[str]) -> None:
    for candidate in candidates:
        if candidate == "creative_director":
            continue
        if candidate in SPECIALIST_IDS and candidate not in target:
            target.append(candidate)


def select_specialists(user_message: str, intent: Any, domain_profile_ids: list[str] | None) -> list[str]:
    """Return a stable, creator-facing specialist bundle without the creative director."""

    message = (user_message or "").lower()
    selected: list[str] = []
    normalized_intent = _normalized_intent(intent)
    profiles = _flatten_strings(domain_profile_ids or [])

    for intents, specialists in _INTENT_MAP:
        if normalized_intent in intents:
            _append_unique(selected, specialists)

    for keywords, specialists in _KEYWORD_MAP:
        if any(keyword in message for keyword in keywords):
            _append_unique(selected, specialists)

    for profile_keywords, specialists in _PROFILE_MAP:
        if any(keyword in profile for profile in profiles for keyword in profile_keywords):
            _append_unique(selected, specialists)

    continuity_requested = any(token in message for token in ("review", "risk", "problem", "issue", "continuity"))
    if any(token in message for token in ("review", "risk", "problem", "issue", "continuity")):
        _append_unique(selected, ("continuity_supervisor",))
    if any(token in message for token in ("emotion", "tone", "tension", "subtext")):
        _append_unique(selected, ("cinematic_psychology",))

    if not selected:
        _append_unique(selected, _DEFAULT_SPECIALISTS)

    if "continuity_supervisor" not in selected and normalized_intent in {"revise_story", "review_continuity"}:
        _append_unique(selected, ("continuity_supervisor",))

    if continuity_requested and "continuity_supervisor" in selected:
        selected = ["continuity_supervisor", *[item for item in selected if item != "continuity_supervisor"]]

    # Staging / shot language should lead with cinematography, not worldbuilding.
    if any(token in message for token in ("staging", "shot", "camera", "coverage", "blocking")):
        if "cinematography_director" not in selected:
            _append_unique(selected, ("cinematography_director",))
        selected = [
            "cinematography_director",
            *[item for item in selected if item != "cinematography_director"],
        ]

    return selected[:4]


__all__ = ["select_specialists"]
