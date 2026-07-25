"""Bounded specialist selection for Co-Director M2.4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .schemas import IntentClassification
from .specialist_registry import SpecialistRegistry

MAX_SPECIALISTS = 8

_INTENT_SPECIALISTS: dict[str, tuple[str, ...]] = {
    "revise_dialogue": ("screenwriter", "story-editor", "performance-director"),
    "plan_scene": ("director", "screenwriter", "producer", "cinematographer", "script-supervisor"),
    "design_location": ("production-designer", "art-director", "cinematographer", "technical-director"),
    "create_storyboard": (
        "director",
        "cinematographer",
        "art-director",
        "script-supervisor",
        "continuity-analyst",
        "prompt-architect",
        "technical-director",
        "vision-reviewer",
    ),
    "prepare_video_generation": (
        "director",
        "cinematographer",
        "choreographer",
        "continuity-analyst",
        "editor",
        "prompt-architect",
        "technical-director",
        "vision-reviewer",
    ),
    "review_asset": ("art-director", "continuity-analyst", "vision-reviewer", "technical-director"),
    "prepare_image_generation": (
        "director",
        "art-director",
        "prompt-architect",
        "technical-director",
        "vision-reviewer",
    ),
    "answer_question": ("producer",),
    "unknown": ("director", "producer"),
}

_CONTINUITY_INTENTS = frozenset({"revise_dialogue", "plan_scene", "create_storyboard", "prepare_video_generation"})


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
