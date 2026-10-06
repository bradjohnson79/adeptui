"""Compile distinct generation layers from Movement Segment state.

Generators receive unchanged facts, starting state, ending state, action,
and the Timed Prompt separately. Never collapse to a single walk sentence.
"""

from __future__ import annotations

import re
from typing import Any

from .movement import (
    active_segment,
    compact_segment_json,
    compute_transition,
    find_segment,
    find_segment_by_number,
    hydrate_movement_segments,
    movement_alias,
    previous_segment,
)
from .schemas import SpatialMapDocument


def parse_movement_alias(text: str | None) -> int | None:
    match = re.search(r"(?:~)?\bM\s*([1-5])\b", str(text or ""), re.I)
    return int(match.group(1)) if match else None


def resolve_segment_for_ref(document: SpatialMapDocument, ref: dict[str, Any] | None, text: str = "") -> Any:
    hydrate_movement_segments(document)
    if isinstance(ref, dict) and ref.get("id"):
        return find_segment(document, str(ref["id"]))
    number = None
    if isinstance(ref, dict) and ref.get("segmentNumber"):
        number = int(ref["segmentNumber"])
    if number is None:
        number = parse_movement_alias(text)
    if number is not None:
        return find_segment_by_number(document, number)
    return active_segment(document)


def compile_generation_layers(
    document: SpatialMapDocument,
    segment: Any,
    *,
    timed_prompt: str = "",
) -> dict[str, Any]:
    hydrate_movement_segments(document)
    prior = previous_segment(document, segment)
    transition = compute_transition(prior, segment) if prior is not None else None
    packed = compact_segment_json(segment)
    dialogue = " / ".join(
        f"{d.get('speaker')}: {d.get('text')}" if d.get("speaker") else str(d.get("text") or "")
        for d in (packed.get("dialogue") or [])
        if d.get("text")
    )
    layers = {
        "unchanged": (transition or {}).get("unchanged") or ["environment", "cameras", "ERS"],
        "startingState": (transition or {}).get("startingState") or packed,
        "endingState": packed,
        "action": packed.get("userDirection") or packed.get("productionPrompt") or "",
        "dialogue": dialogue,
        "timedPrompt": timed_prompt,
        "movementAlias": movement_alias(int(getattr(segment, "segmentNumber", 1) or 1)),
        "movementSegmentId": getattr(segment, "id", ""),
        "movementSegmentRevision": int(getattr(segment, "revision", 1) or 1),
        "transition": transition,
    }
    return layers


def layers_as_provider_text(layers: dict[str, Any]) -> str:
    """Structured prose for adapters. Does not emit a lone walk sentence."""
    parts = [
        "UNCHANGED FACTS: " + ", ".join(str(x) for x in (layers.get("unchanged") or [])),
        f"STARTING STATE ({(layers.get('transition') or {}).get('fromAlias') or 'M1'}): beat "
        + str((layers.get("startingState") or {}).get("beatName") or ""),
        f"ENDING STATE ({layers.get('movementAlias')}): beat "
        + str((layers.get("endingState") or {}).get("beatName") or ""),
    ]
    if layers.get("action"):
        parts.append("ACTION / DIRECTION: " + str(layers["action"]))
    if layers.get("dialogue"):
        parts.append("DIALOGUE: " + str(layers["dialogue"]))
    if layers.get("timedPrompt"):
        parts.append("TIMED PROMPT: " + str(layers["timedPrompt"]))
    return "\n".join(part for part in parts if part.strip())
