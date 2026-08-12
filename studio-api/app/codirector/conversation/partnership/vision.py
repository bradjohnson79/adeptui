"""Project big-vision profile — timed, never forced in fragile emergence."""

from __future__ import annotations

import re

from .destination import detect_destination_conflicts
from .schemas import PartnershipProjectBundle, ProjectDestination, ProjectVisionProfile


_DEST_PATTERNS: list[tuple[str, ProjectDestination]] = [
    (r"\byoutube\b", ProjectDestination.YOUTUBE),
    (r"\bfestival", ProjectDestination.FILM_FESTIVALS),
    (r"\bproof of concept\b|\bpoc\b", ProjectDestination.PROOF_OF_CONCEPT),
    (r"\bproducer pitch\b|\bpitch (?:to )?producers?\b", ProjectDestination.PRODUCER_PITCH),
    (r"\bnetwork\b", ProjectDestination.NETWORK_PITCH),
    (r"\bstreamer\b|\bnetflix\b|\bhulu\b", ProjectDestination.STREAMER_PITCH),
    (r"\binvestor", ProjectDestination.INVESTOR_PITCH),
    (r"\bcrowdfund", ProjectDestination.CROWDFUNDING),
    (r"\bpersonal (?:project|piece)\b|\bjust for me\b", ProjectDestination.PERSONAL),
    (r"\bportfolio\b", ProjectDestination.PORTFOLIO),
    (r"\btheatrical\b", ProjectDestination.THEATRICAL),
    (r"\bnot sure\b|\bundecided\b|\bkeep (?:several|options) open\b", ProjectDestination.UNDECIDED),
]


def update_vision_from_message(
    bundle: PartnershipProjectBundle,
    user_message: str,
    *,
    creative_stage: str,
) -> ProjectVisionProfile:
    vision = bundle.vision
    msg = user_message or ""
    lowered = msg.lower()
    positioned: list[tuple[int, ProjectDestination]] = []
    for pattern, dest in _DEST_PATTERNS:
        m = re.search(pattern, lowered)
        if m:
            positioned.append((m.start(), dest))
    positioned.sort(key=lambda item: item[0])
    found = [d for _, d in positioned]
    # de-dupe preserving order
    seen: set[ProjectDestination] = set()
    ordered: list[ProjectDestination] = []
    for d in found:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    found = ordered
    if found:
        primary = found[0]
        if primary != ProjectDestination.UNDECIDED or vision.primary_destination == ProjectDestination.UNDECIDED:
            vision.primary_destination = primary
        for d in found[1:]:
            if d not in vision.secondary_destinations and d != vision.primary_destination:
                vision.secondary_destinations.append(d)
        vision.creator_confirmed = primary != ProjectDestination.UNDECIDED and "not sure" not in lowered

    if re.search(r"\baudience\b", lowered):
        # Capture a short audience phrase
        m = re.search(r"audience(?: is| of| for)?\s+([^.]{8,80})", msg, re.I)
        if m:
            phrase = m.group(1).strip()
            if phrase not in vision.intended_audience:
                vision.intended_audience.append(phrase)

    if "personal" in lowered and vision.primary_destination == ProjectDestination.PERSONAL:
        vision.commercial_intent = "NONE"
        vision.project_scale = "PERSONAL"

    if re.search(r"\b(festival|theatrical|network|investor)\b", lowered):
        if vision.commercial_intent == "UNDECIDED":
            vision.commercial_intent = "OPTIONAL"

    vision.conflicts = detect_destination_conflicts(vision)
    # Don't force vision update during fragile single-sentence emergence unless user brought it up
    if creative_stage == "EMERGENCE" and len(msg.split()) < 25 and not found:
        return vision
    bundle.vision = vision
    return vision


def vision_guidance(vision: ProjectVisionProfile) -> str:
    dest = vision.primary_destination.value
    lines = [f"Project destination emphasis: {dest}."]
    if vision.primary_destination == ProjectDestination.PERSONAL:
        lines.append("Personal project: do not force marketing or commercialization.")
    if vision.conflicts:
        lines.append("Destination tradeoffs to surface (do not decide for the user): " + "; ".join(vision.conflicts[:3]))
    if vision.intended_audience:
        lines.append("Audience notes: " + "; ".join(vision.intended_audience[:3]))
    return "\n".join(lines)
