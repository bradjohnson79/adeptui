"""Story deviation assessment for consequential proposed changes."""

from __future__ import annotations

import re

from .problem_source import classify_problem_source, foundational_rewrite_likely_premature
from .schemas import (
    AdvisoryEpistemics,
    AdvisoryStrength,
    StoryDeviationAssessment,
    StoryDeviationType,
    StoryPrinciple,
    StoryProblemSource,
)

_CHANGE_RE = re.compile(
    r"\b(remov(?:e|ing)|cut(?:ting)?|replac(?:e|ing)|rewrit(?:e|ing)|chang(?:e|ing)|"
    r"drop(?:ping)?|delet(?:e|ing)|never met|without (?:the|it)|retcon|considering remov)\b",
    re.I,
)
_EXPLORE_RE = re.compile(r"\bwhat if\b|\bexplore\b|\balternate\b|\bversion without\b", re.I)
_FOUNDATIONAL_TARGET = re.compile(
    r"\b(central|core|main|foundational|premise|encounter|entity|protagonist)\b",
    re.I,
)


def assess_story_deviation(
    user_message: str,
    *,
    principles: list[StoryPrinciple] | None = None,
    prior_decision_state: str | None = None,
) -> StoryDeviationAssessment:
    text = user_message or ""
    if not (_CHANGE_RE.search(text) or _EXPLORE_RE.search(text)):
        return StoryDeviationAssessment(triggered=False)

    source = classify_problem_source(text)
    explore = bool(_EXPLORE_RE.search(text))
    foundational_target = bool(_FOUNDATIONAL_TARGET.search(text))
    premature = foundational_rewrite_likely_premature(source) and foundational_target

    affected = [
        p.id
        for p in (principles or [])
        if p.status.value in {"CONFIRMED", "APPROVED", "EMERGING"} and p.importance.value in {"FOUNDATIONAL", "MAJOR"}
    ][:6]

    if explore:
        dtype = StoryDeviationType.EXPERIMENTAL_VARIANT
        strength = AdvisoryStrength.SUGGESTION
    elif premature:
        dtype = StoryDeviationType.ACCIDENTAL_DRIFT
        strength = AdvisoryStrength.FOUNDATIONAL_WARNING
    elif source == StoryProblemSource.FOUNDATIONAL_STORY:
        dtype = StoryDeviationType.INTENTIONAL_RETCON
        strength = AdvisoryStrength.STRONG_RECOMMENDATION
    else:
        dtype = StoryDeviationType.NATURAL_EVOLUTION
        strength = AdvisoryStrength.RECOMMENDATION

    alts: list[str] = []
    if premature:
        alts = [
            "Adjust pacing, staging, or information delivery first",
            "Preserve the encounter’s function while changing surrounding craft",
            "Try a provisional staging alternate without removing the center",
        ]

    recommendation = (
        "The difficulty may be how the scene communicates the idea, not whether the idea belongs. "
        "Protect the demonstrated center and change surrounding craft first."
        if premature
        else (
            "Treat this as an exploratory variant: map gains and losses without changing active canon."
            if explore
            else "Evaluate gains and losses against confirmed strengths before adopting the change."
        )
    )

    return StoryDeviationAssessment(
        proposed_change=text[:280],
        user_goal_behind_change="Solve a felt creative or production problem via story change.",
        affected_principle_ids=affected,
        problem_source=source,
        deviation_type=dtype,
        likely_gains=["May simplify local pacing" if premature else "May clarify creator intent"],
        likely_losses=(
            ["May remove a demonstrated emotional/story engine", "May weaken continuity promises"]
            if foundational_target
            else ["May require downstream continuity updates"]
        ),
        continuity_effects=["Active canon should remain unchanged until confirmation"] if explore or premature else [],
        emotional_effects=["Risk of losing the relationship/encounter charge"] if foundational_target else [],
        thematic_effects=[],
        production_effects=["Downstream plans may need restaging rather than story deletion"] if premature else [],
        story_change_necessary=not premature and not explore and source == StoryProblemSource.FOUNDATIONAL_STORY,
        alternative_adjustments=alts,
        advisory_strength=strength,
        recommendation=recommendation,
        epistemics=AdvisoryEpistemics(
            confidence=0.75 if premature or explore else 0.6,
            evidence_quality="heuristic+principles" if affected else "heuristic",
            supporting_source_ids=affected,
            missing_context=[] if affected else ["Confirmed story principles still thin"],
            interpretation_status="inferred",
            user_confirmation_needed=foundational_target and not explore,
        ),
        triggered=True,
    )
