"""Contact-first Timeline SFX timing. Cadence is the last fallback, never silent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

from .media_packet import ContactEvent

TimingSource = Literal["visible_contact", "motion_derived", "cadence_inference", "manual"]
DEFAULT_WALK_CADENCE_SEC = 0.55


@dataclass(frozen=True)
class TimedHit:
    character_name: str
    character_id: str | None
    start_sec: float
    length_sec: float
    volume: float
    label: str
    timing_source: TimingSource
    foot: str = "unknown"
    surface: str | None = None
    confidence: float | None = None


def plan_contact_hits(
    contacts: Iterable[ContactEvent | dict[str, Any]],
    *,
    clip_length_sec: float = 0.35,
    volume: float = 0.32,
) -> list[TimedHit]:
    """Place one SFX hit per detected contact. Confidence is preserved, not invented."""

    hits: list[TimedHit] = []
    length = min(max(float(clip_length_sec or 0.35), 0.12), 0.8)
    for raw in contacts:
        item = raw if isinstance(raw, ContactEvent) else ContactEvent.model_validate(raw)
        start = item.startTime
        if start is None:
            continue
        name = (item.characterLabel or "Footsteps").strip() or "Footsteps"
        source = item.timingSource or "visible_contact"
        hits.append(
            TimedHit(
                character_name=name,
                character_id=item.characterId,
                start_sec=round(float(start), 3),
                length_sec=round(length, 3),
                volume=volume,
                label=f"{name} footsteps" if name != "Footsteps" else "Footsteps",
                timing_source=source if source in ("visible_contact", "motion_derived", "cadence_inference", "manual") else "visible_contact",
                foot=item.foot or "unknown",
                surface=item.surface,
                confidence=item.confidence,
            )
        )
    hits.sort(key=lambda hit: hit.start_sec)
    return hits


def disclose_timing(source: TimingSource) -> str:
    if source == "visible_contact":
        return "Timed to visible foot contacts in the clip."
    if source == "motion_derived":
        return "Timed from motion, not a visible contact frame."
    if source == "manual":
        return "Timed from a manual mark."
    return f"Inferred walking pace ({DEFAULT_WALK_CADENCE_SEC:.2f}s). Not frame-perfect contact."
