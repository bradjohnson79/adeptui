"""Creative opening detection — strongest place to deepen next."""

from __future__ import annotations

import hashlib
import re

from .contracts import CreativeOpening


def detect_creative_openings(
    *,
    user_message: str,
    open_questions: list[str] | None = None,
    has_episode_gap: bool = False,
    format_label: str = "UNKNOWN",
) -> list[CreativeOpening]:
    text = user_message or ""
    lower = text.lower()
    openings: list[CreativeOpening] = []

    def add(opening_type: str, foundation: list[str], missing: str, why: str, question: str | None, priority: float):
        digest = hashlib.sha1(f"{opening_type}:{missing}".encode("utf-8")).hexdigest()[:10]
        openings.append(
            CreativeOpening(
                id=f"co-{digest}",
                openingType=opening_type,
                knownFoundation=foundation,
                missingDimension=missing,
                whyItMatters=why,
                suggestedQuestion=question,
                suggestedAction=None,
                priority=priority,
            )
        )

    if re.search(r"\b(character|protagonist|lead)\b", lower) and not re.search(
        r"\b(want|motive|because|afraid|need)\b", lower
    ):
        add(
            "character_motivation",
            ["Character role mentioned"],
            "motivation",
            "Motivation turns a role into a living person the audience can follow.",
            "What does this character want most — and what are they afraid to lose?",
            0.85,
        )
    if re.search(r"\b(relationship|together|partners?)\b", lower) and not re.search(
        r"\b(history|met|years|childhood)\b", lower
    ):
        add(
            "relationship_history",
            ["Relationship referenced"],
            "shared history",
            "History gives the relationship weight before the plot asks it to break or hold.",
            "What shared history makes this relationship feel inevitable?",
            0.8,
        )
    if re.search(r"\b(location|place|set|room|city)\b", lower) and not re.search(
        r"\b(light|sound|smell|looks|atmosphere)\b", lower
    ):
        add(
            "location_identity",
            ["Location named"],
            "visual and sound identity",
            "Visual and sound identity make the place usable for image, video, and continuity.",
            "How should this place look and sound when we first arrive?",
            0.75,
        )
    if has_episode_gap and format_label == "EPISODIC_SERIES":
        add(
            "next_installment",
            ["Prior installment established"],
            "next installment purpose",
            "Knowing what the next installment must accomplish keeps development one step ahead.",
            None,
            0.9,
        )
    for q in open_questions or []:
        digest = hashlib.sha1(q.encode("utf-8")).hexdigest()[:10]
        openings.append(
            CreativeOpening(
                id=f"co-q-{digest}",
                openingType="open_question",
                knownFoundation=[],
                missingDimension=q,
                whyItMatters="This unanswered dimension could deepen the current material.",
                suggestedQuestion=q,
                priority=0.7,
            )
        )

    openings.sort(key=lambda o: o.priority, reverse=True)
    return openings[:5]


def strongest_opening(openings: list[CreativeOpening]) -> CreativeOpening | None:
    return openings[0] if openings else None
