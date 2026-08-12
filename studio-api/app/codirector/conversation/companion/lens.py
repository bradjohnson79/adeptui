"""Project Creative Lens — gradual, evidence-based artistic interpretation."""

from __future__ import annotations

import re

from .schemas import ProjectCreativeLens


def update_creative_lens(lens: ProjectCreativeLens, user_message: str, project_id: str, source_id: str) -> ProjectCreativeLens:
    updated = lens.model_copy(deep=True)
    updated.project_id = project_id
    text = user_message or ""
    if re.search(r"\bmythic\b", text, re.I) and "mythic" not in updated.emotional_tones:
        updated.emotional_tones.append("mythic")
    if re.search(r"\b(mystery|withhold|ambigu)\b", text, re.I):
        updated.ambiguity_preference = "prefer_ambiguity"
        if "mystery" not in updated.dominant_genres:
            updated.dominant_genres.append("mystery")
    if re.search(r"\b(comedy|funny|gag)\b", text, re.I) and "comedy" not in updated.dominant_genres:
        updated.dominant_genres.append("comedy")
    if re.search(r"\b(tactile|grounded|harbor|tide)\b", text, re.I) and "tactile intimacy" not in updated.artistic_priorities:
        updated.artistic_priorities.append("tactile intimacy")
    if re.search(r"\b(pacing|slow|tight)\b", text, re.I):
        updated.pacing_preference = "conscious_pacing"
    if source_id and source_id not in updated.source_ids:
        updated.source_ids.append(source_id)
    updated.source_ids = updated.source_ids[-12:]
    updated.status = "emerging" if not updated.creator_confirmed else updated.status
    return updated
