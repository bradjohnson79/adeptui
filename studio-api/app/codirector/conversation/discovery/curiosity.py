"""Curiosity threads — deferred follow-through without interrupting narration."""

from __future__ import annotations

import re

from .schemas import CreativeIntrigueAssessment, CuriosityThread


def capture_curiosity_threads(
    *,
    project_id: str,
    user_message: str,
    intrigue: CreativeIntrigueAssessment,
    source_id: str,
) -> list[CuriosityThread]:
    threads: list[CuriosityThread] = []
    for q in intrigue.unanswered_creative_questions[:3]:
        threads.append(
            CuriosityThread(
                project_id=project_id,
                subject=q[:160],
                why_it_matters="May carry emotional or thematic weight for the project.",
                source_ids=[source_id],
                priority=60,
                status="DEFERRED",
            )
        )
    # Unusual two-versions / memory hooks
    m = re.search(r"(.{0,40}(?:two versions|remembers|secret|unusual).{0,60})", user_message or "", re.I)
    if m:
        threads.append(
            CuriosityThread(
                project_id=project_id,
                subject=m.group(1).strip(),
                why_it_matters="Unusual detail that may become the emotional center.",
                source_ids=[source_id],
                priority=80,
                status="OPEN",
            )
        )
    return threads[:5]


def merge_curiosity(existing: list[CuriosityThread], incoming: list[CuriosityThread]) -> list[CuriosityThread]:
    seen = {t.subject.lower() for t in existing}
    out = list(existing)
    for t in incoming:
        if t.subject.lower() in seen:
            continue
        seen.add(t.subject.lower())
        out.append(t)
    return out[:40]
