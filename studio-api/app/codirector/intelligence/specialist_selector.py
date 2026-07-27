"""Bounded specialist selection for Co-Director M2.4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .schemas import IntentClassification
from .specialist_registry import SpecialistRegistry

MAX_SPECIALISTS = 8

_INTENT_SPECIALISTS: dict[str, tuple[str, ...]] = {
    "revise_dialogue": ("screenwriter", "story-editor", "performance-director", "sound-designer"),
    "plan_scene": (
        "story-analyst",
        "director",
        "screenwriter",
        "producer",
        "cinematographer",
        "sound-designer",
        "music-supervisor",
        "editor",
    ),
    "design_location": (
        "production-designer",
        "art-director",
        "cinematographer",
        "lighting-supervisor",
        "technical-director",
    ),
    "create_storyboard": (
        "director",
        "cinematographer",
        "art-director",
        "script-supervisor",
        "continuity-analyst",
        "sound-designer",
        "editor",
        "vision-reviewer",
    ),
    "prepare_video_generation": (
        "director",
        "cinematographer",
        "sound-designer",
        "music-supervisor",
        "continuity-analyst",
        "editor",
        "prompt-architect",
        "vision-reviewer",
    ),
    "review_asset": (
        "art-director",
        "continuity-analyst",
        "asset-manager",
        "qa-reviewer",
        "vision-reviewer",
        "technical-director",
    ),
    "prepare_image_generation": (
        "director",
        "art-director",
        "lighting-supervisor",
        "prompt-architect",
        "asset-manager",
        "vision-reviewer",
    ),
    "answer_question": ("producer", "pipeline-manager"),
    "unknown": ("director", "producer", "story-analyst"),
}

# First-class audio/editorial / M2.11 production intelligence intents
_INTENT_SPECIALISTS.update(
    {
        "plan_audio": ("sound-designer", "music-supervisor", "editor", "director"),
        "assemble_sequence": (
            "editor",
            "sound-designer",
            "music-supervisor",
            "continuity-analyst",
            "director",
        ),
        "production_intelligence": (
            "story-analyst",
            "bible-manager",
            "continuity-analyst",
            "director",
            "cinematographer",
            "sound-designer",
            "music-supervisor",
            "editor",
        ),
    }
)

_CONTINUITY_INTENTS = frozenset(
    {
        "revise_dialogue",
        "plan_scene",
        "create_storyboard",
        "prepare_video_generation",
        "assemble_sequence",
        "production_intelligence",
    }
)


@dataclass
class SpecialistSelection:
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    reasons: list[str] = field(default_factory=list)

    @property
    def all_selected(self) -> tuple[str, ...]:
        return self.required + self.optional


class SpecialistSelector:
    def __init__(self, registry: SpecialistRegistry | None = None, *, max_specialists: int = MAX_SPECIALISTS) -> None:
        self.registry = registry or SpecialistRegistry()
        self.max_specialists = max(1, max_specialists)

    def select(
        self,
        intent: IntentClassification,
        *,
        include_continuity: bool | None = None,
    ) -> SpecialistSelection:
        base = _INTENT_SPECIALISTS.get(intent.primaryIntent, _INTENT_SPECIALISTS["unknown"])
        selected: list[str] = []
        skipped: list[str] = []
        reasons: list[str] = [f"intent={intent.primaryIntent}"]

        for specialist_id in base:
            if specialist_id not in self.registry.ids():
                skipped.append(specialist_id)
                continue
            if len(selected) >= self.max_specialists:
                skipped.append(specialist_id)
                continue
            selected.append(specialist_id)

        if include_continuity is None:
            include_continuity = intent.primaryIntent in _CONTINUITY_INTENTS
        if include_continuity and "continuity-analyst" in self.registry.ids():
            if "continuity-analyst" not in selected and len(selected) < self.max_specialists:
                selected.append("continuity-analyst")
                reasons.append("continuity context relevant")
            elif "continuity-analyst" not in selected:
                skipped.append("continuity-analyst")

        bounded = selected[: self.max_specialists]
        overflow = selected[self.max_specialists :]
        skipped.extend(overflow)

        required_count = min(3, len(bounded)) if intent.complexity != "simple" else min(1, len(bounded))
        required = tuple(bounded[:required_count])
        optional = tuple(bounded[required_count:])
        return SpecialistSelection(required=required, optional=optional, skipped=tuple(dict.fromkeys(skipped)), reasons=reasons)

    def validate_selection(self, specialist_ids: Iterable[str]) -> list[str]:
        return self.registry.validate_ids(specialist_ids)

_INTENT_SPECIALISTS.update(
    {
        "virtual_production": (
            "virtual-production-coordinator",
            "production-designer",
            "cinematographer",
            "lighting-supervisor",
            "continuity-analyst",
            "technical-director",
        ),
        "environment_studio": (
            "virtual-production-coordinator",
            "production-designer",
            "art-director",
            "cinematographer",
            "lighting-supervisor",
        ),
    }
)

_INTENT_SPECIALISTS.update(
    {
        "storyteller_discovery": (
            "storyteller",
            "sound-producer",
            "director",
            "cinematographer",
            "continuity-analyst",
        ),
        "sound_production": (
            "sound-producer",
            "music-supervisor",
            "sound-designer",
            "storyteller",
            "editor",
        ),
        "unified_experience": (
            "storyteller",
            "sound-producer",
            "cinematographer",
            "editor",
            "virtual-production-coordinator",
            "continuity-analyst",
            "director",
        ),
    }
)
_CONTINUITY_INTENTS = frozenset(set(_CONTINUITY_INTENTS) | {"storyteller_discovery", "unified_experience", "sound_production"})
