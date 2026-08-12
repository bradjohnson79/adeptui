"""Creative development stage + temperature (emergence protection)."""

from __future__ import annotations

import re

from .schemas import CreativeDevelopmentStage, CreativeTemperature

_CRITIQUE_ASK = re.compile(r"\b(critique|be direct|don['’]?t encourage|honest(?:ly)?|what(?:'|’)s weak)\b", re.I)
_PROD = re.compile(r"\b(draft|plan|generate|render|produce|execute|production plan)\b", re.I)
_EVAL = re.compile(r"\b(stress[- ]test|risk|compare alternatives|evaluate|does this work)\b", re.I)
_FORM = re.compile(r"\b(premise|structure|outline|character bible|formalize)\b", re.I)
_EXPLORE = re.compile(r"\b(what if|explore|variant|alternate)\b", re.I)


def assess_creative_temperature(
    user_message: str,
    *,
    prior_stage: CreativeDevelopmentStage | None = None,
    explicit_critique: bool = False,
) -> CreativeTemperature:
    text = user_message or ""
    stage = prior_stage or CreativeDevelopmentStage.EMERGENCE

    if explicit_critique or _CRITIQUE_ASK.search(text):
        stage = CreativeDevelopmentStage.EVALUATION
    elif _PROD.search(text):
        stage = CreativeDevelopmentStage.PRODUCTION
    elif _EVAL.search(text):
        stage = CreativeDevelopmentStage.EVALUATION
    elif _FORM.search(text):
        stage = CreativeDevelopmentStage.FORMATION
    elif _EXPLORE.search(text):
        stage = CreativeDevelopmentStage.EXPLORATION
    elif len(text.strip()) >= 80 and stage == CreativeDevelopmentStage.EMERGENCE:
        stage = CreativeDevelopmentStage.EMERGENCE

    if stage == CreativeDevelopmentStage.EMERGENCE:
        return CreativeTemperature(
            stage=stage,
            momentum="BUILDING" if len(text) > 40 else "FRAGILE",
            critique_allowed=False,
            caution_allowed=False,
            intrigue_priority="HIGH",
            documentation_priority="HIGH",
            question_budget=1 if len(text) > 120 else 0,
        )
    if stage == CreativeDevelopmentStage.EXPLORATION:
        return CreativeTemperature(
            stage=stage,
            momentum="BUILDING",
            critique_allowed=False,
            caution_allowed=False,
            intrigue_priority="HIGH",
            documentation_priority="HIGH",
            question_budget=3,
        )
    if stage == CreativeDevelopmentStage.FORMATION:
        return CreativeTemperature(
            stage=stage,
            momentum="STABLE",
            critique_allowed=True,
            caution_allowed=False,
            intrigue_priority="MEDIUM",
            documentation_priority="HIGH",
            question_budget=5,
        )
    if stage == CreativeDevelopmentStage.EVALUATION:
        return CreativeTemperature(
            stage=stage,
            momentum="STABLE",
            critique_allowed=True,
            caution_allowed=True,
            intrigue_priority="MEDIUM",
            documentation_priority="MEDIUM",
            question_budget=2,
        )
    return CreativeTemperature(
        stage=CreativeDevelopmentStage.PRODUCTION,
        momentum="HIGH",
        critique_allowed=True,
        caution_allowed=True,
        intrigue_priority="LOW",
        documentation_priority="MEDIUM",
        question_budget=2,
    )
