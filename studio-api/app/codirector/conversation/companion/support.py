"""Creative support assessment — conversational working state, not diagnosis."""

from __future__ import annotations

import re

from .schemas import CompanionNeed, CreativeSupportAssessment, CreativeWorkingState, CreatorCompanionState

_DISCOURAGED = re.compile(
    r"\b(doesn['’]?t work|does not work|wonder whether|giving up|not good enough|story (?:is )?(?:broken|dead)|anymore)\b",
    re.I,
)
_STUCK = re.compile(r"\b(i['’]?m stuck|stuck on|don['’]?t know what happens|writer['’]?s block|blank)\b", re.I)
_CRITIQUE = re.compile(
    r"\b(don['’]?t encourage|be direct|be honest|tell me honestly|critique|what is weak|no praise)\b",
    re.I,
)
_CELEBRATE = re.compile(r"\b(we (?:nailed|landed)|this finally works|breakthrough|proud of)\b", re.I)
_OVERWHELMED = re.compile(r"\b(too much|overwhelmed|can['’]?t keep track|everything at once)\b", re.I)
_FRUSTRATED = re.compile(r"\b(frustrated|this keeps failing|keeps breaking|sick of)\b", re.I)
_TECHNICAL = re.compile(r"\b(timeout|vram|cuda|render failed|model (?:error|crash)|comfy|gpu)\b", re.I)
_ENCOURAGE = re.compile(r"\b(need encouragement|reassure|am i crazy|should i keep going)\b", re.I)
_EXPLORE = re.compile(r"\bwhat if\b|\bexplore (?:a |the )?version\b|\balternate\b", re.I)
_EXECUTE = re.compile(r"\b(draft|create|generate|run|build)\b.+\b(plan|scene|shot|render)\b", re.I)


def assess_creative_support(
    user_message: str,
    *,
    companion_state: CreatorCompanionState | None = None,
) -> CreativeSupportAssessment:
    text = " ".join((user_message or "").split())
    evidence: list[str] = []
    state = CreativeWorkingState.NEUTRAL
    need = CompanionNeed.LISTEN
    strategy: list[str] = ["Address the latest message specifically"]
    avoid: list[str] = ["Generic praise", "Therapeutic language", "Dependency language"]
    emotional = False
    conf = 0.55
    goal = "Continue the creative conversation"

    def _hit(pattern: re.Pattern[str], label: str) -> bool:
        m = pattern.search(text)
        if m:
            evidence.append(m.group(0)[:120] or label)
            return True
        return False

    if _hit(_CRITIQUE, "direct critique"):
        state = CreativeWorkingState.SEEKING_CRITIQUE
        need = CompanionNeed.CRITIQUE
        strategy = [
            "Honor direct-critique request",
            "Separate strengths and weaknesses with evidence",
            "No unnecessary reassurance",
        ]
        avoid += ["Encouragement", "Softening that hides the critique"]
        emotional = False
        conf = 0.9
        goal = "Provide honest critique without flattery"
    elif _hit(_DISCOURAGED, "discouragement"):
        state = CreativeWorkingState.DISCOURAGED
        need = CompanionNeed.REFRAME
        strategy = [
            "Acknowledge uncertainty without automatic disagreement",
            "Reflect project-specific strengths with evidence",
            "Separate foundational weakness from execution difficulty",
            "Offer one diagnostic next step",
        ]
        avoid += ["Blind disagreement", "Empty praise", "Motivational slogans"]
        emotional = True
        conf = 0.85
        goal = "Restore clarity about what is and is not working"
    elif _hit(_STUCK, "stuck"):
        state = CreativeWorkingState.STUCK
        need = CompanionNeed.UNBLOCK
        strategy = [
            "Classify or narrow the block",
            "Recall relevant strengths or return points",
            "Offer one focused next step",
        ]
        avoid += ["Large idea dumps", "Forced questionnaires", "Immediate foundational rewrite"]
        emotional = True
        conf = 0.85
        goal = "Unblock with one useful next step"
    elif _hit(_OVERWHELMED, "overwhelmed"):
        state = CreativeWorkingState.OVERWHELMED
        need = CompanionNeed.SIMPLIFY
        strategy = ["Separate creative purpose from implementation burden", "Reduce to one next action"]
        avoid += ["Adding more open loops"]
        emotional = True
        conf = 0.8
        goal = "Simplify the workload"
    elif _hit(_FRUSTRATED, "frustrated") or _hit(_TECHNICAL, "technical"):
        state = CreativeWorkingState.FRUSTRATED
        need = CompanionNeed.EXECUTE if _TECHNICAL.search(text) else CompanionNeed.REFRAME
        strategy = [
            "Detect technical friction vs story failure",
            "Preserve creative purpose",
            "Suggest production alternatives when technical",
        ]
        avoid += ["Treating technical failure as story failure"]
        emotional = False
        conf = 0.8
        goal = "Preserve intent and fix the real layer"
    elif _hit(_CELEBRATE, "celebration"):
        state = CreativeWorkingState.CELEBRATING_PROGRESS
        need = CompanionNeed.CELEBRATE
        strategy = ["Name the specific achievement", "Explain why it matters", "Moderate enthusiasm"]
        avoid += ["Exaggerated celebration"]
        emotional = True
        conf = 0.75
        goal = "Recognize meaningful progress specifically"
    elif _hit(_ENCOURAGE, "encouragement request"):
        state = CreativeWorkingState.SEEKING_VALIDATION
        need = CompanionNeed.ENCOURAGE
        strategy = ["Evidence-based encouragement tied to the work", "Proportionate support"]
        avoid += ["Generic praise"]
        emotional = True
        conf = 0.8
        goal = "Encourage with project-specific evidence"
    elif _hit(_EXPLORE, "exploration"):
        state = CreativeWorkingState.EXPLORING
        need = CompanionNeed.ADVISE
        strategy = ["Mark as exploratory", "Compare gains and losses", "Do not alter canon"]
        avoid += ["Silent canonization"]
        conf = 0.8
        goal = "Explore consequences without changing canon"
    elif _hit(_EXECUTE, "execution"):
        state = CreativeWorkingState.FLOWING
        need = CompanionNeed.EXECUTE
        strategy = ["Confirm authorized action", "Stay operational and transparent"]
        avoid += ["Emotional commentary unless asked"]
        emotional = False
        conf = 0.7
        goal = "Execute or plan production in service of confirmed intent"
    elif len(text) > 40:
        state = CreativeWorkingState.EXPLORING if "story" in text.lower() else CreativeWorkingState.NEUTRAL
        need = CompanionNeed.LISTEN
        strategy = ["Listen and reflect specifics", "Track facts carefully"]
        conf = 0.5
        goal = "Understand and track the creator’s material"

    if companion_state and companion_state.critique_preference == "direct":
        if need == CompanionNeed.ENCOURAGE and state != CreativeWorkingState.SEEKING_VALIDATION:
            need = CompanionNeed.CRITIQUE

    if not evidence and text:
        evidence.append(text[:120])

    return CreativeSupportAssessment(
        working_state=state,
        support_needed=need,
        confidence=conf,
        evidence_spans=evidence[:8],
        likely_user_goal=goal,
        suggested_response_strategy=strategy,
        should_avoid=avoid,
        emotional_commentary_appropriate=emotional,
    )
