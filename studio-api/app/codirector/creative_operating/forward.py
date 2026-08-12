"""One-step-ahead / format-aware forward development suggestions."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .contracts import (
    CreativeOperatingBundle,
    EpisodeProgressionState,
    ForwardDevelopmentSuggestion,
    ProjectFormat,
)
from .format_detect import next_unit_label, uses_episodes


def _sid(project_id: str, suggestion: str) -> str:
    digest = hashlib.sha1(f"{project_id}:{suggestion.strip().lower()}".encode("utf-8")).hexdigest()[:12]
    return f"fds-{digest}"


def detect_episode_progression(
    *,
    user_message: str,
    wiki_text: str = "",
    prior: EpisodeProgressionState | None = None,
) -> EpisodeProgressionState:
    state = prior or EpisodeProgressionState()
    corpus = f"{user_message}\n{wiki_text}"
    nums = [int(n) for n in re.findall(r"\bepisode\s*(\d+)\b", corpus, flags=re.I)]
    if nums:
        latest = max(nums)
        state.latestConfirmedEpisode = max(state.latestConfirmedEpisode, latest)
        state.latestAnalyzedEpisode = max(state.latestAnalyzedEpisode, latest)
        state.nextMissingEpisode = state.latestConfirmedEpisode + 1
    elif state.latestConfirmedEpisode > 0:
        state.nextMissingEpisode = state.latestConfirmedEpisode + 1
    return state


def build_forward_suggestions(
    bundle: CreativeOperatingBundle,
    *,
    project_format: ProjectFormat,
    listening_only: bool,
    foundation_lines: list[str],
    unresolved: list[str],
    max_suggestions: int = 3,
) -> list[ForwardDevelopmentSuggestion]:
    if listening_only:
        return []
    if len(foundation_lines) < 1 and not unresolved:
        return []

    dismissed = set(bundle.dismissedSuggestionIds or [])
    active_existing = {
        s.suggestion.strip().lower()
        for s in bundle.forwardSuggestions
        if s.state == "ACTIVE"
    }
    unit = next_unit_label(project_format)
    suggestions: list[ForwardDevelopmentSuggestion] = []

    if uses_episodes(project_format):
        ep = bundle.episodeProgression or EpisodeProgressionState()
        if ep.latestConfirmedEpisode > 0 and ep.nextMissingEpisode > ep.latestConfirmedEpisode:
            text = (
                f"Episode {ep.nextMissingEpisode} is not yet defined. "
                f"A possible direction is emerging from Episode {ep.latestConfirmedEpisode}'s unresolved material."
            )
            # Tie id to current unresolved setups so dismissing one opening does not
            # permanently block a later distinct one-step-ahead suggestion.
            if unresolved:
                text = f"{text} Open thread: {unresolved[0][:120]}"
            why = "Stay one installment ahead using unresolved setups — exploratory only, not canon."
            sid = _sid(bundle.projectId, text)
            if sid not in dismissed and text.lower() not in active_existing:
                suggestions.append(
                    ForwardDevelopmentSuggestion(
                        id=sid,
                        projectId=bundle.projectId,
                        currentDevelopmentUnit=f"Episode {ep.latestConfirmedEpisode}",
                        nextDevelopmentUnit=f"Episode {ep.nextMissingEpisode}",
                        confirmedFoundation=foundation_lines[:4],
                        unresolvedSetups=unresolved[:4],
                        availableDirections=[unit],
                        suggestion=text,
                        whyItFits=why,
                        confidence=0.5,
                        format=project_format,
                    )
                )
    else:
        # Non-episodic: format-specific one-step suggestions — never invent episodes.
        templates: dict[ProjectFormat, tuple[str, str]] = {
            "FEATURE_FILM": (
                f"A natural next step is clarifying the {unit}.",
                "Film development advances by sequence and structural turn, not episodes.",
            ),
            "SHORT_FILM": (
                f"A natural next step is clarifying the {unit}.",
                "Short films move by compact sequence, not episodic installments.",
            ),
            "DOCUMENTARY": (
                f"A natural next step is identifying a {unit}.",
                "Documentary progression follows research, interviews, and perspectives — not fictional episodes.",
            ),
            "GAME": (
                f"A natural next step is defining the {unit}.",
                "Game progression follows quests, mechanics, and player dependencies.",
            ),
            "NOVEL": (
                f"A natural next step is clarifying the {unit}.",
                "Novel progression follows chapter and point-of-view continuity.",
            ),
            "MUSIC_VIDEO": (
                f"A natural next step is shaping the {unit}.",
                "Music videos progress through visual sequences and performance beats.",
            ),
            "COMMERCIAL": (
                f"A natural next step is locking the {unit}.",
                "Commercials progress through brand beats and deliverable variations.",
            ),
        }
        text, why = templates.get(
            project_format,
            (f"A natural next step is the {unit}.", "Stay one meaningful development unit ahead."),
        )
        if unresolved:
            text = f"{text} Unresolved setup: {unresolved[0]}"
        sid = _sid(bundle.projectId, text)
        if sid not in dismissed and text.lower() not in active_existing:
            suggestions.append(
                ForwardDevelopmentSuggestion(
                    id=sid,
                    projectId=bundle.projectId,
                    currentDevelopmentUnit="current material",
                    nextDevelopmentUnit=unit,
                    confirmedFoundation=foundation_lines[:4],
                    unresolvedSetups=unresolved[:4],
                    availableDirections=[unit],
                    suggestion=text,
                    whyItFits=why,
                    confidence=0.45,
                    format=project_format,
                )
            )

    # Persist new suggestions (cap)
    new_ids = {s.id for s in suggestions}
    kept = [s for s in bundle.forwardSuggestions if s.state != "DISMISSED" or s.id in dismissed]
    for s in suggestions:
        if s.id not in {x.id for x in kept}:
            kept.insert(0, s)
    bundle.forwardSuggestions = kept[:12]
    return [s for s in suggestions if s.id in new_ids][:max_suggestions]


def dismiss_suggestion(bundle: CreativeOperatingBundle, suggestion_id: str) -> bool:
    found = False
    for s in bundle.forwardSuggestions:
        if s.id == suggestion_id:
            s.state = "DISMISSED"
            found = True
    if suggestion_id not in bundle.dismissedSuggestionIds:
        bundle.dismissedSuggestionIds = [*bundle.dismissedSuggestionIds, suggestion_id][:40]
    return found


def surface_one(
    suggestions: list[ForwardDevelopmentSuggestion],
    bundle: CreativeOperatingBundle,
) -> ForwardDevelopmentSuggestion | None:
    dismissed = set(bundle.dismissedSuggestionIds or [])
    for s in suggestions:
        if s.id not in dismissed and s.state == "ACTIVE":
            return s
    for s in bundle.forwardSuggestions:
        if s.id not in dismissed and s.state == "ACTIVE":
            return s
    return None


def why_it_matters_for_record(statement: str, *, format_label: str = "UNKNOWN") -> dict[str, str]:
    """Evidence-grounded story + production importance (no invented production facts)."""
    lower = (statement or "").lower()
    story = "This detail shapes how the audience understands character, conflict, or theme."
    production = "This detail can inform scripts, continuity, and later asset work when confirmed."
    if re.search(r"\b(look|visual|wardrobe|costume|light)\b", lower):
        production = "Visual and wardrobe cues affect image generation, continuity, and costume planning."
        story = "Visual identity reinforces character or place meaning on screen."
    if re.search(r"\b(sound|music|voice|whisper)\b", lower):
        production = "Sound and performance cues affect audio, voice, and scene atmosphere work."
    if format_label == "DOCUMENTARY":
        story = "This detail affects factual framing, subject representation, or research clarity."
        production = "This may inform interview plans, archival needs, or chronology — when confirmed."
    if format_label == "GAME":
        story = "This detail affects player experience, faction pressure, or quest meaning."
        production = "This may inform mechanics, NPC work, or progression dependencies — when confirmed."
    return {"storyImportance": story, "productionImportance": production}
