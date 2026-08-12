"""Creative return-point capture."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .schemas import CreativeReturnPoint


def maybe_capture_return_point(user_message: str, project_id: str, source_id: str) -> CreativeReturnPoint | None:
    text = user_message or ""
    if not re.search(r"\b(alive|working|lands|charged|confrontation|encounter)\b", text, re.I):
        return None
    if len(text) < 60:
        return None
    m = re.search(r"(.{20,160})", text)
    desc = (m.group(1).strip() if m else text[:160]).strip()
    return CreativeReturnPoint(
        project_id=project_id,
        description=desc,
        why_it_worked="Creator described energy, purpose, or a charged encounter in this material.",
        source_ids=[source_id],
        confidence=0.55,
        creator_confirmed=False,
        status="active",
        related_principle_ids=[],
    )


def merge_return_points(existing: list[CreativeReturnPoint], incoming: CreativeReturnPoint | None) -> list[CreativeReturnPoint]:
    if not incoming:
        return existing
    for item in existing:
        if item.description[:80].lower() == incoming.description[:80].lower():
            return existing
    return [incoming, *existing][:12]
