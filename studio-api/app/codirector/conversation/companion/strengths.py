"""Evidence-based creator/project strength records — no vague flattery."""

from __future__ import annotations

import re

from .schemas import CreatorStrength, StoryPrinciple

_BANNED = re.compile(
    r"\b(brilliant|genius|gifted|everything .+ excellent|amazing artist|incredible talent)\b",
    re.I,
)


def propose_strength_from_principles(
    project_id: str,
    principles: list[StoryPrinciple],
    *,
    source_id: str,
) -> CreatorStrength | None:
    confirmedish = [
        p
        for p in principles
        if p.status.value in {"CONFIRMED", "APPROVED", "EMERGING"}
        and p.importance.value in {"FOUNDATIONAL", "MAJOR"}
    ]
    if len(confirmedish) < 1:
        return None
    # Prefer tone + emotional core pairing as a specific, useful strength.
    tone = next((p for p in confirmedish if p.category == "tone"), None)
    core = next((p for p in confirmedish if p.category == "emotional_core"), None)
    if tone and core:
        statement = (
            "The project consistently grounds larger mythic stakes in intimate, tactile emotional encounters "
            "rather than abstract spectacle."
        )
        sources = list({*tone.source_ids, *core.source_ids, source_id})
    elif core:
        statement = (
            "The story’s early emotional engine is carried by a specific intimate encounter, "
            "not by generic plot machinery."
        )
        sources = list({*core.source_ids, source_id})
    elif tone:
        statement = f"Tone discipline is a demonstrated strength: {tone.statement}"
        sources = list({*tone.source_ids, source_id})
    else:
        return None

    if _BANNED.search(statement):
        return None
    return CreatorStrength(
        statement=statement,
        evidence_source_ids=sources[:8],
        confidence=0.65,
        project_scope=project_id,
        confirmed_by_user=False,
        status="proposed",
    )


def merge_strengths(existing: list[CreatorStrength], incoming: CreatorStrength | None) -> list[CreatorStrength]:
    if not incoming:
        return existing
    for item in existing:
        if item.statement.lower() == incoming.statement.lower():
            for sid in incoming.evidence_source_ids:
                if sid not in item.evidence_source_ids:
                    item.evidence_source_ids.append(sid)
            item.confidence = min(0.95, max(item.confidence, incoming.confidence))
            return existing
    return [*existing, incoming][:20]
