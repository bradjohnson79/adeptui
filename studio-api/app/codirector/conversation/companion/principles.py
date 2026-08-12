"""Story principle helpers with provenance."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .schemas import PrincipleImportance, PrincipleStatus, StoryPrinciple, StoryStrengthProfile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_emerging_principles(user_message: str, project_id: str, source_id: str) -> list[StoryPrinciple]:
    """Lightweight extraction of candidate principles from substantial lore turns."""

    text = (user_message or "").strip()
    if len(text) < 80:
        return []
    out: list[StoryPrinciple] = []
    # Tone / identity cues
    if re.search(r"\b(mythic|tactile|tide|harbor|no cyberpunk|grounded)\b", text, re.I):
        out.append(
            StoryPrinciple(
                project_id=project_id,
                statement="Tone stays tactile, mythic, and grounded rather than cyberpunk/glossy.",
                category="tone",
                status=PrincipleStatus.EMERGING,
                importance=PrincipleImportance.MAJOR,
                source_ids=[source_id],
                confidence=0.65,
                created_at=_now(),
                updated_at=_now(),
            )
        )
    if re.search(r"\b(lantern|harbor child|central encounter|emotional engine)\b", text, re.I):
        out.append(
            StoryPrinciple(
                project_id=project_id,
                statement="An early intimate encounter (e.g. harbor-child / lantern-call) carries the emotional engine.",
                category="emotional_core",
                status=PrincipleStatus.EMERGING,
                importance=PrincipleImportance.FOUNDATIONAL,
                source_ids=[source_id],
                confidence=0.6,
                created_at=_now(),
                updated_at=_now(),
            )
        )
    if re.search(r"\b(continuity matters|hand-built|salt air)\b", text, re.I):
        out.append(
            StoryPrinciple(
                project_id=project_id,
                statement="Continuity of tactile world details (salt air, hand-built craft) is a promise.",
                category="world_laws",
                status=PrincipleStatus.EMERGING,
                importance=PrincipleImportance.SUPPORTING,
                source_ids=[source_id],
                confidence=0.55,
                created_at=_now(),
                updated_at=_now(),
            )
        )
    return out[:4]


def merge_principles(existing: list[StoryPrinciple], incoming: list[StoryPrinciple]) -> list[StoryPrinciple]:
    by_stmt = {p.statement.lower(): p for p in existing}
    for item in incoming:
        key = item.statement.lower()
        if key in by_stmt:
            prev = by_stmt[key]
            for sid in item.source_ids:
                if sid not in prev.source_ids:
                    prev.source_ids.append(sid)
            prev.confidence = min(0.95, max(prev.confidence, item.confidence))
            prev.updated_at = _now()
        else:
            by_stmt[key] = item
    return list(by_stmt.values())[:40]


def profile_from_principles(project_id: str, principles: list[StoryPrinciple]) -> StoryStrengthProfile:
    profile = StoryStrengthProfile(project_id=project_id)
    for p in principles:
        if p.status in {PrincipleStatus.SUPERSEDED, PrincipleStatus.REJECTED}:
            continue
        bucket = {
            "emotional_core": profile.emotional_core,
            "theme": profile.thematic_pillars,
            "character": profile.character_promises,
            "relationship": profile.relationship_promises,
            "world_laws": profile.world_laws,
            "tone": profile.tone_commitments,
            "mystery": profile.mystery_boundaries,
            "audience": profile.audience_promises,
            "visual": profile.visual_identity,
            "non_negotiable": profile.creator_non_negotiables,
        }.get(p.category)
        if bucket is not None and p.id not in bucket:
            bucket.append(p.id)
        elif p.category == "emotional_core" and p.id not in profile.emotional_core:
            profile.emotional_core.append(p.id)
    return profile
