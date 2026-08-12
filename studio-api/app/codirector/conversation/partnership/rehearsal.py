"""Pitch rehearsal modes — realistic questions without claiming real-company representation."""

from __future__ import annotations

from .schemas import PitchPackage, PitchRehearsalDebrief, PartnershipProjectBundle

_ROLES = {
    "producer": [
        "What's the emotional engine in one sentence?",
        "Who is the audience and why now?",
        "What's the production scale and first proof point?",
    ],
    "development_executive": [
        "What makes this distinct from recent comps?",
        "Where does episode two go if this is series?",
        "What would you cut if budget halves?",
    ],
    "festival_programmer": [
        "Why does this belong in a festival program?",
        "What is the cinematic signature?",
        "Is the runtime honest to the idea?",
    ],
    "youtube_audience_strategist": [
        "What's the clickable but honest promise?",
        "How does the first 30 seconds retain?",
        "What is the upload cadence?",
    ],
    "investor": [
        "What's the path to return without overclaiming?",
        "What rights are clear?",
        "What is the minimum viable release?",
    ],
}


def run_rehearsal(
    bundle: PartnershipProjectBundle,
    *,
    role: str,
    pitch: PitchPackage | None = None,
) -> tuple[list[str], PitchRehearsalDebrief]:
    key = (role or "producer").lower().replace(" ", "_")
    questions = _ROLES.get(key, _ROLES["producer"])
    pkg = pitch or (bundle.pitches[-1] if bundle.pitches else None)
    landed = []
    unclear = []
    generic = []
    if pkg:
        if pkg.logline and len(pkg.logline.split()) >= 8:
            landed.append("Logline has a concrete hook from the premise.")
        else:
            unclear.append("Logline needs a sharper protagonist/conflict.")
        if "generic" in (pkg.short_pitch or "").lower() or not pkg.differentiation:
            generic.append("Differentiation still thin — avoid genre-only claims.")
        if not pkg.comparable_works:
            unclear.append("Comparables not yet sourced (permissioned research).")
    debrief = PitchRehearsalDebrief(
        role=key,
        what_landed=landed or ["Core promise is present enough to rehearse."],
        what_was_unclear=unclear or ["Audience specificity could be sharper."],
        what_sounded_generic=generic,
        what_needs_evidence=["Any market or festival claims need sourced research."],
        what_should_be_shorter=["Opening promise — land the hook faster."],
        what_should_be_emphasized=["The distinctive reversal or emotional stake."],
        likely_follow_ups=questions,
    )
    bundle.last_rehearsal = debrief
    return questions, debrief
