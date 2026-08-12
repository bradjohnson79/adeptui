"""Destination-aware development guidance and multi-destination conflict detection."""

from __future__ import annotations

from .schemas import ProjectDestination, ProjectVisionProfile


def detect_destination_conflicts(vision: ProjectVisionProfile) -> list[str]:
    dests = {vision.primary_destination, *vision.secondary_destinations}
    conflicts: list[str] = []
    if ProjectDestination.FILM_FESTIVALS in dests and (
        ProjectDestination.YOUTUBE in dests or ProjectDestination.SOCIAL_SHORT in dests
    ):
        conflicts.append(
            "Festival premiere rules may conflict with public YouTube/social release — sequence carefully."
        )
    if ProjectDestination.FILM_FESTIVALS in dests and ProjectDestination.INDEPENDENT_COMMERCIAL in dests:
        conflicts.append("Exclusivity windows for festivals can delay commercial online publication.")
    if ProjectDestination.PROOF_OF_CONCEPT in dests and ProjectDestination.YOUTUBE in dests:
        conflicts.append("POC length/scope may differ from episodic YouTube cadence — clarify which comes first.")
    if ProjectDestination.NETWORK_PITCH in dests and ProjectDestination.YOUTUBE in dests:
        conflicts.append("Network pitch expectations can conflict with self-release strategy.")
    if ProjectDestination.PRODUCER_PITCH in dests and ProjectDestination.PERSONAL in dests:
        conflicts.append("Personal creative goals vs producer pitch packaging — keep both paths open until chosen.")
    return conflicts


def destination_strategy_notes(vision: ProjectVisionProfile) -> list[str]:
    d = vision.primary_destination
    if d == ProjectDestination.YOUTUBE:
        return [
            "Episode hooks and retention moments",
            "Cadence and playlist structure",
            "Thumbnails, titles, Shorts, community posts",
            "Launch sequence and channel identity",
        ]
    if d == ProjectDestination.FILM_FESTIVALS:
        return [
            "Runtime and category fit",
            "Eligibility and premiere status",
            "Submission calendar (requires sourced research)",
            "Press kit, stills, poster, captions",
        ]
    if d in {
        ProjectDestination.PRODUCER_PITCH,
        ProjectDestination.NETWORK_PITCH,
        ProjectDestination.STREAMER_PITCH,
    }:
        return [
            "Logline and treatment",
            "Pitch deck / series bible / pilot promise",
            "Audience and comparables with differentiation",
            "Production feasibility and rights readiness",
        ]
    if d == ProjectDestination.PROOF_OF_CONCEPT:
        return [
            "Strongest dramatic promise in manageable scope",
            "Visual identity and emotional hook",
            "Future expansion and pitch usefulness",
        ]
    if d == ProjectDestination.PERSONAL:
        return [
            "Honor personal goals — no forced marketing",
            "Document creative decisions for the creator",
        ]
    return ["Keep destination undecided until the idea has shape."]
