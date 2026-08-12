"""Classify whether a problem is story-foundational or surrounding execution."""

from __future__ import annotations

import re

from .schemas import StoryProblemSource

_PATTERNS: list[tuple[re.Pattern[str], StoryProblemSource]] = [
    (re.compile(r"\b(slow(?:ly)?|pacing|dragging|mov(?:es|ing) too slow(?:ly)?)\b", re.I), StoryProblemSource.PACING),
    (re.compile(r"\b(staging|presentation|how (?:it|the scene) (?:reads|plays|lands))\b", re.I), StoryProblemSource.PRESENTATION),
    (re.compile(r"\b(visual|shot|camera|framing|looks)\b", re.I), StoryProblemSource.VISUAL_EXECUTION),
    (re.compile(r"\b(dialogue|line reads?|on[- ]the[- ]nose)\b", re.I), StoryProblemSource.DIALOGUE),
    (re.compile(r"\b(performance|acting|delivery)\b", re.I), StoryProblemSource.PERFORMANCE),
    (re.compile(r"\b(edit(?:ing)?|cut|montage)\b", re.I), StoryProblemSource.EDITING),
    (re.compile(r"\b(sound|score|music|mix)\b", re.I), StoryProblemSource.SOUND),
    (re.compile(r"\b(timeout|vram|cuda|render|model|gpu|comfy|technical)\b", re.I), StoryProblemSource.TECHNICAL_LIMITATION),
    (re.compile(r"\b(scope|budget|schedule|too expensive|production)\b", re.I), StoryProblemSource.PRODUCTION_SCOPE),
    (re.compile(r"\b(structure|act break|sequence order)\b", re.I), StoryProblemSource.STRUCTURE),
    (re.compile(r"\b(character(?:ization)?|motivation|arc)\b", re.I), StoryProblemSource.CHARACTERIZATION),
    (re.compile(r"\b(emotion(?:al)?|feeling|resonance)\b", re.I), StoryProblemSource.EMOTIONAL_DELIVERY),
    (re.compile(r"\b(exposition|information|clarity|confus)\b", re.I), StoryProblemSource.INFORMATION_DELIVERY),
    (re.compile(r"\b(remove the (?:central|core|main)|rewrite the (?:foundation|premise)|story (?:itself )?is (?:wrong|broken))\b", re.I), StoryProblemSource.FOUNDATIONAL_STORY),
    (re.compile(r"\b(not sure|uncertain|wonder whether)\b", re.I), StoryProblemSource.USER_UNCERTAINTY),
]


def classify_problem_source(user_message: str) -> StoryProblemSource:
    text = user_message or ""
    for pattern, source in _PATTERNS:
        if pattern.search(text):
            return source
    return StoryProblemSource.UNKNOWN


def foundational_rewrite_likely_premature(source: StoryProblemSource) -> bool:
    """True when surrounding layers should be tried before foundational rewrite."""

    return source in {
        StoryProblemSource.PACING,
        StoryProblemSource.PRESENTATION,
        StoryProblemSource.VISUAL_EXECUTION,
        StoryProblemSource.DIALOGUE,
        StoryProblemSource.PERFORMANCE,
        StoryProblemSource.EDITING,
        StoryProblemSource.SOUND,
        StoryProblemSource.TECHNICAL_LIMITATION,
        StoryProblemSource.PRODUCTION_SCOPE,
        StoryProblemSource.INFORMATION_DELIVERY,
        StoryProblemSource.EMOTIONAL_DELIVERY,
    }
