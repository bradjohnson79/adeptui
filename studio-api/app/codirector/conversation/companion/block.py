"""Writer's-block intelligence and intervention map."""

from __future__ import annotations

import re

from .schemas import CreativeBlockAssessment, CreativeBlockType, CreatorCompanionState

_INTERVENTIONS: dict[CreativeBlockType, tuple[str, list[str]]] = {
    CreativeBlockType.CONCEPTUAL: (
        "Restate the core idea and isolate the missing principle.",
        ["Restate the premise in one sentence", "Name the missing principle"],
    ),
    CreativeBlockType.STRUCTURAL: (
        "Identify what must change next and offer a small number of paths with consequences.",
        ["Name the structural hinge", "Compare 2–3 paths with consequences"],
    ),
    CreativeBlockType.CHARACTER: (
        "Return to desire, fear, contradiction, choice, and relationship.",
        ["Restate character desire vs fear", "Ask what choice raises the cost"],
    ),
    CreativeBlockType.EMOTIONAL: (
        "Identify what should change internally during the scene.",
        ["Name the internal shift", "Locate the beat where feeling turns"],
    ),
    CreativeBlockType.CONTINUITY: (
        "Isolate conflicting facts and distinguish active canon from superseded material.",
        ["List conflicting facts", "Mark active vs superseded canon"],
    ),
    CreativeBlockType.CHOICE_PARALYSIS: (
        "Compare options against story strengths and creator intent.",
        ["Reduce to two options", "Score against story strengths"],
    ),
    CreativeBlockType.PERFECTION_PRESSURE: (
        "Reduce the task to a provisional beat, scene, test, or alternate.",
        ["Propose a provisional draft", "Defer polish"],
    ),
    CreativeBlockType.PRODUCTION_OVERLOAD: (
        "Separate creative purpose from implementation burden.",
        ["Name the creative purpose", "Defer tooling until purpose is clear"],
    ),
    CreativeBlockType.TECHNICAL_FRICTION: (
        "Preserve creative intent and replace the execution strategy.",
        ["Preserve creative purpose", "Swap execution path"],
    ),
    CreativeBlockType.FATIGUE: (
        "Summarize, preserve the stopping point, simplify, and avoid forcing ideation.",
        ["Summarize stopping point", "Offer a minimal next bookmark"],
    ),
    CreativeBlockType.UNKNOWN: (
        "Clarify the likely block and offer one focused next step.",
        ["Ask what feels stuck", "Offer one focused step"],
    ),
}


def assess_creative_block(
    user_message: str,
    *,
    companion_state: CreatorCompanionState | None = None,
    strength_ids: list[str] | None = None,
    return_point_ids: list[str] | None = None,
) -> CreativeBlockAssessment | None:
    text = user_message or ""
    lowered = text.lower()
    stuckish = bool(
        re.search(
            r"\bstuck\b|don['’]?t know what happens|writer['’]?s block|blank page|what happens next",
            lowered,
        )
    )
    if not stuckish:
        return None

    block = CreativeBlockType.UNKNOWN
    evidence: list[str] = []
    if m := re.search(r"character|relationship|desire|fear", lowered):
        block = CreativeBlockType.CHARACTER
        evidence.append(m.group(0))
    elif m := re.search(r"structure|act |beat|plot|sequence", lowered):
        block = CreativeBlockType.STRUCTURAL
        evidence.append(m.group(0))
    elif m := re.search(r"continuity|contradict|canon", lowered):
        block = CreativeBlockType.CONTINUITY
        evidence.append(m.group(0))
    elif m := re.search(r"too many (?:options|choices)|can['’]?t decide|paralys", lowered):
        block = CreativeBlockType.CHOICE_PARALYSIS
        evidence.append(m.group(0))
    elif m := re.search(r"perfect|not good enough|polish", lowered):
        block = CreativeBlockType.PERFECTION_PRESSURE
        evidence.append(m.group(0))
    elif m := re.search(r"render|timeout|vram|model|gpu|technical", lowered):
        block = CreativeBlockType.TECHNICAL_FRICTION
        evidence.append(m.group(0))
    elif m := re.search(r"tired|exhausted|fatigue", lowered):
        block = CreativeBlockType.FATIGUE
        evidence.append(m.group(0))
    elif m := re.search(r"emotion|feel|tone|mood", lowered):
        block = CreativeBlockType.EMOTIONAL
        evidence.append(m.group(0))
    elif m := re.search(r"idea|premise|concept|theme", lowered):
        block = CreativeBlockType.CONCEPTUAL
        evidence.append(m.group(0))
    elif m := re.search(r"production|schedule|scope|too much to (?:build|make)", lowered):
        block = CreativeBlockType.PRODUCTION_OVERLOAD
        evidence.append(m.group(0))
    else:
        if m := re.search(r"stuck|what happens next", lowered):
            evidence.append(m.group(0))

    first, options = _INTERVENTIONS[block]
    return CreativeBlockAssessment(
        block_type=block,
        evidence_spans=evidence or [text[:120]],
        likely_root_problem=f"Creative block appears {block.value.lower().replace('_', ' ')}.",
        relevant_story_strength_ids=list(strength_ids or (companion_state.known_strength_ids if companion_state else [])[:4]),
        relevant_return_point_ids=list(return_point_ids or [])[:4],
        intervention_options=options,
        recommended_first_step=first,
        focused_question_required=block in {CreativeBlockType.UNKNOWN, CreativeBlockType.CONCEPTUAL},
        confidence=0.7 if block != CreativeBlockType.UNKNOWN else 0.55,
    )
