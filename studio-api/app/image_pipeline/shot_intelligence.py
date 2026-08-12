"""Deterministic shot interpretation for the image pipeline foundation."""

from __future__ import annotations

import re
from typing import Any

from .contracts import ImageShotIntent

_COUNT_PATTERNS = (
    (r"\bthree[- ]character\b|\b3[- ]character\b|\bthree people\b|\bthree characters\b", 3),
    (r"\btwo[- ]shot\b|\b2[- ]shot\b|\btwo characters\b|\btwo people\b", 2),
    (r"\bgroup\b|\bcrowd\b|\bensemble\b", 4),
)


def _contains(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _subject_count(text: str) -> int:
    for pattern, count in _COUNT_PATTERNS:
        if re.search(pattern, text):
            return count
    return 1


def interpret_shot(prompt: str, project_context: dict[str, Any] | None = None) -> ImageShotIntent:
    text = " ".join((prompt or "").strip().lower().split())
    project_context = project_context or {}

    shot_size = "medium"
    if _contains(text, "close-up", "close up", "portrait", "tight frame"):
        shot_size = "close_up"
    elif _contains(text, "wide shot", "wide frame", "wide reveal", "full scene", "establishing", "long shot"):
        shot_size = "wide"
    elif _contains(text, "insert", "detail shot"):
        shot_size = "insert"

    shot_type = shot_size
    if _contains(text, "over the shoulder", "over-the-shoulder"):
        shot_type = "over_shoulder"
    elif _contains(text, "pov", "point of view"):
        shot_type = "pov"

    subject_count = _subject_count(text)
    motion_level = "still"
    if _contains(text, "running", "chasing", "fight", "explosion", "jump", "sprinting"):
        motion_level = "dynamic"
    elif _contains(text, "walking", "turning", "reaching", "leaning", "moving"):
        motion_level = "active"

    environment_type = None
    if _contains(text, "street", "alley", "city", "rooftop", "forest", "warehouse", "room", "kitchen"):
        environment_type = "grounded_location"
    elif _contains(text, "void", "dream", "cosmic", "abstract"):
        environment_type = "stylized"

    staging_signals: list[str] = []
    if subject_count >= 3:
        staging_signals.append("multi-character-blocking")
    if _contains(text, "foreground", "background", "depth", "layered"):
        staging_signals.append("depth-composition")
    if _contains(text, "doorway", "window", "hallway", "stairs", "balcony"):
        staging_signals.append("architectural-anchor")
    if motion_level == "dynamic":
        staging_signals.append("action-pose")

    wants_reveal = _contains(text, "reveal", "suddenly seen", "uncover")
    wants_suspense = _contains(text, "suspense", "tense", "ominous", "edge of frame", "dread")
    wants_comedy = _contains(text, "comedy", "funny", "awkward", "absurd")
    wants_intimacy = _contains(text, "intimate", "tender", "romantic", "whisper", "vulnerable")
    wants_action = _contains(text, "action", "fight", "chase", "explosion", "battle")
    wants_horror = _contains(text, "horror", "monster", "blood", "terrifying", "creepy", "haunted", "ghostly")
    wants_establishing = _contains(text, "establishing", "set the scene", "wide overview")

    complexity = "simple"
    if len(staging_signals) >= 2 or subject_count >= 3 or motion_level == "dynamic":
        complexity = "complex"
    elif subject_count == 2 or motion_level == "active":
        complexity = "moderate"

    clarification = None
    if len(text) < 20:
        clarification = "What should the audience notice first in this image?"
    elif shot_size == "medium" and not any(
        [wants_reveal, wants_suspense, wants_comedy, wants_intimacy, wants_action, wants_horror, wants_establishing]
    ):
        clarification = "Should this feel more like a wide scene setter, an intimate moment, or a dramatic reveal?"

    subject_labels = []
    if isinstance(project_context.get("characterNames"), list):
        for name in project_context["characterNames"][:subject_count]:
            if isinstance(name, str) and name.strip():
                subject_labels.append(name.strip())

    return ImageShotIntent(
        prompt=prompt,
        shotType=shot_type,
        shotSize=shot_size,
        subjectCount=subject_count,
        subjectLabels=subject_labels,
        primaryAction="action" if wants_action else ("reveal" if wants_reveal else None),
        environmentType=environment_type,
        complexity=complexity,
        motionLevel=motion_level,
        wantsReveal=wants_reveal,
        wantsSuspense=wants_suspense,
        wantsComedy=wants_comedy,
        wantsIntimacy=wants_intimacy,
        wantsAction=wants_action,
        wantsHorror=wants_horror,
        wantsEstablishing=wants_establishing,
        stagingSignals=staging_signals,
        clarificationQuestion=clarification,
    )

