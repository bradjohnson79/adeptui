"""CreativeAdvisoryPlan builder and advisory decision state machine."""

from __future__ import annotations

import re

from .schemas import (
    AdvisoryDecisionState,
    AdvisoryStrength,
    CreativeAdvisoryPlan,
    CreativeSupportAssessment,
    CompanionNeed,
    StoryDeviationAssessment,
)

_CONFIRM_CHANGE = re.compile(
    r"\b("
    r"keep the change|make it canon|change it anyway|go ahead and change|"
    r"i still want (?:the change|to change|to remove|it removed|to cut)"
    r")\b",
    re.I,
)
_CONFIRM_KEEP = re.compile(
    r"\b(keep the original|keep (?:it|the encounter)|don['’]?t remove|change the pacing|staging instead)\b",
    re.I,
)
_EXPLORE = re.compile(
    r"\b("
    r"still want to explore|want to explore|explore the version|exploratory|"
    r"what if|as a variant|without (?:changing|touching) canon"
    r")\b",
    re.I,
)


def build_advisory_plan(
    *,
    support: CreativeSupportAssessment,
    deviation: StoryDeviationAssessment | None,
    decision_state: AdvisoryDecisionState,
) -> CreativeAdvisoryPlan:
    if decision_state in {
        AdvisoryDecisionState.USER_CONFIRMED_CHANGE,
        AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT,
        AdvisoryDecisionState.COLLABORATING_ON_DIRECTION,
        AdvisoryDecisionState.CANON_UPDATED,
    }:
        return CreativeAdvisoryPlan(
            should_advise=False,
            acknowledge_user_logic=True,
            identify_story_strength=False,
            identify_actual_problem=False,
            compare_gains_and_losses=False,
            provide_alternative=False,
            advisory_strength=AdvisoryStrength.OBSERVATION,
            request_confirmation=False,
            preserve_as_variant=False,
            canon_write_allowed=decision_state
            in {AdvisoryDecisionState.USER_CONFIRMED_CHANGE, AdvisoryDecisionState.CANON_UPDATED},
            accept_after_confirmation=True,
            no_relitigation_after_confirmation=True,
        )

    if not deviation or not deviation.triggered:
        advise = support.support_needed in {CompanionNeed.ADVISE, CompanionNeed.CRITIQUE, CompanionNeed.REFRAME}
        return CreativeAdvisoryPlan(
            should_advise=advise,
            acknowledge_user_logic=True,
            identify_story_strength=support.support_needed
            in {CompanionNeed.REFRAME, CompanionNeed.ENCOURAGE, CompanionNeed.UNBLOCK, CompanionNeed.CRITIQUE},
            identify_actual_problem=support.support_needed in {CompanionNeed.REFRAME, CompanionNeed.UNBLOCK, CompanionNeed.ADVISE},
            compare_gains_and_losses=False,
            provide_alternative=False,
            advisory_strength=AdvisoryStrength.OBSERVATION,
            request_confirmation=False,
            preserve_as_variant=False,
            canon_write_allowed=False,
            accept_after_confirmation=False,
            no_relitigation_after_confirmation=True,
        )

    foundational = deviation.advisory_strength in {
        AdvisoryStrength.STRONG_RECOMMENDATION,
        AdvisoryStrength.FOUNDATIONAL_WARNING,
    }
    return CreativeAdvisoryPlan(
        should_advise=True,
        acknowledge_user_logic=True,
        identify_story_strength=True,
        identify_actual_problem=True,
        compare_gains_and_losses=True,
        provide_alternative=bool(deviation.alternative_adjustments),
        advisory_strength=deviation.advisory_strength,
        request_confirmation=foundational and decision_state not in {AdvisoryDecisionState.EXPLORATORY, AdvisoryDecisionState.TEST_VARIANT},
        preserve_as_variant=deviation.deviation_type.value == "EXPERIMENTAL_VARIANT"
        or decision_state == AdvisoryDecisionState.EXPLORATORY,
        canon_write_allowed=False,
        accept_after_confirmation=False,
        no_relitigation_after_confirmation=True,
    )


def transition_advisory_state(
    current: AdvisoryDecisionState,
    user_message: str,
    *,
    deviation: StoryDeviationAssessment | None,
) -> AdvisoryDecisionState:
    text = user_message or ""
    # Exploration must win over vague “I still want…” confirmation phrasing.
    if _EXPLORE.search(text):
        return AdvisoryDecisionState.EXPLORATORY
    if _CONFIRM_KEEP.search(text):
        return AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT
    if _CONFIRM_CHANGE.search(text):
        return AdvisoryDecisionState.USER_CONFIRMED_CHANGE
    if deviation and deviation.triggered:
        if current == AdvisoryDecisionState.ADVISED and re.search(
            r"\bi understand,? but\b|\bstill considering\b",
            text,
            re.I,
        ):
            return AdvisoryDecisionState.USER_RECONSIDERING
        if current in {AdvisoryDecisionState.IDLE, AdvisoryDecisionState.ASSESSED}:
            return AdvisoryDecisionState.ADVISED
        return AdvisoryDecisionState.ASSESSED if current == AdvisoryDecisionState.IDLE else current
    if current == AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT:
        return AdvisoryDecisionState.COLLABORATING_ON_DIRECTION
    if current == AdvisoryDecisionState.USER_CONFIRMED_CHANGE:
        return AdvisoryDecisionState.CANON_UPDATE_PENDING
    return current
