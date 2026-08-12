"""Intent analysis with evidence spans — not labels alone."""

from __future__ import annotations

import re

from .schemas import IntentAnalysis, IntentType, InteractionPosture

# Listening / explain-before-production patterns (semantic coverage, not Dreamweaver-specific).
_EXPLAIN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bi will tell you\b", re.I), "I will tell you"),
    (re.compile(r"\bi['’]m going to tell you\b|\bi am going to tell you\b", re.I), "I am going to tell you"),
    (re.compile(r"\bi want to (?:tell|explain|teach)\b", re.I), "I want to tell/explain/teach"),
    (re.compile(r"\blet me (?:give you|explain|tell|begin|walk you)\b", re.I), "Let me explain/tell"),
    (re.compile(r"\bbefore we (?:do anything|start|move|begin|plan|get into)\b", re.I), "before we start/move"),
    (re.compile(r"\bbefore (?:you|we) (?:start )?suggest", re.I), "before suggesting production"),
    (re.compile(r"\bbefore we move into production\b", re.I), "before we move into production"),
    (re.compile(r"\bjust listen\b|\bplease just listen\b|\bkeep listening\b|\bi['’]?m not finished\b", re.I), "listen / not finished"),
    (re.compile(r"\bdon['’]?t organize\b|\bdon['’]?t (?:start )?(?:planning|suggesting)\b", re.I), "don't organize/plan yet"),
    (re.compile(r"\bwalk you through\b|\bgive you the background\b|\bexplain the story\b", re.I), "walk through / background / story"),
    (re.compile(r"\bfamiliar with (?:the )?story\b|\bunderstand the story\b|\bteach you about\b", re.I), "understand/teach story"),
    (re.compile(r"\bsound good\??\b|\bok(?:ay)?\??\s*$", re.I), "Sound good?"),
]

_CORRECTION_RE = re.compile(
    r"^(?:correction:|actually\b|instead\b|no[,.]?\s+that['’]?s wrong)",
    re.I,
)
_NEXT_STEP_RE = re.compile(
    r"what should we (?:do|define) next|next three steps|best next",
    re.I,
)
_FEEDBACK_RE = re.compile(
    r"\bbe honest\b|\btell me (?:honestly|whether|if)\b|\bcritique\b|\bdoes this work\b",
    re.I,
)
_DISSATISFACTION_RE = re.compile(
    r"\bthat (?:was|is) wrong\b|\byou (?:failed|ignored|didn['’]?t listen)\b|\bnot what i (?:asked|said)\b",
    re.I,
)
_ACTION_RE = re.compile(
    r"\b(?:generate|render|create|run|execute|build)\b.+\b(?:scene|image|video|clip|shot)\b",
    re.I,
)
# c2/D13: broaden action coverage to common creator imperatives that target a
# concrete production object (scene/character/asset/voice/bible/canon/batch/…).
# This catches "Add an image to Batch 3", "Change Barnes' voice", "Update the
# Production Bible summary", "Remove the canon record", "Delete the clip", etc.
# Explain questions ("How does … work?") are checked BEFORE this so they never
# mutate.
_ACTION_IMPERATIVE_RE = re.compile(
    r"\b(?:add|change|update|remove|delete|make|put|set|move|rename|replace|swap|drop|insert|split|merge|fix|adjust|swap)\b"
    r".+\b(?:scene|image|video|clip|shot|character|asset|plan|bible|canon|continuity|reference|voice|batch|step|summary|entry|record|tag|segment|panel|track|draft)\b",
    re.I,
)
# c2/D13: explain questions are informational — they must NOT mutate. Match
# "How does Timeline Batch generation work?", "What is the Production Bible?",
# "Explain how the Spatial Map works", "What does canon lock mean?".
_EXPLAIN_QUESTION_RE = re.compile(
    r"^\s*(?:how (?:does|do|did|can|could|would|should)\b.*\b(?:work|works|mean)\b"
    r"|how to\b.*\b(?:use|work|works|mean)\b"
    r"|what (?:does|do)\b.*\bmean\b"
    r"|what (?:is|are)\b.*"
    r"|explain (?:how|what|why|the|a|an|this|that)\b"
    r"|tell me (?:about|how|what)\b.*\??\s*$"
    r")",
    re.I,
)
_PLAN_RE = re.compile(r"\b(?:draft|make|create)\b.+\bplan\b|\bproduction plan\b", re.I)


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _span(text: str, pattern: re.Pattern[str], label: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    raw = m.group(0).strip()
    # Prefer a slightly wider natural phrase when available.
    start = max(0, m.start() - 0)
    end = min(len(text), m.end() + 40)
    window = text[start:end].strip()
    if len(window) > 8:
        return window[:120]
    return raw or label


def analyze_intent(user_message: str) -> IntentAnalysis:
    """Classify intent and collect evidence spans for diagnosis."""

    text = _clean(user_message)
    lowered = text.lower()
    evidence: list[str] = []

    for pattern, label in _EXPLAIN_PATTERNS:
        span = _span(text, pattern, label)
        if span and span not in evidence:
            evidence.append(span)

    explain_hits = sum(1 for p, _ in _EXPLAIN_PATTERNS if p.search(text))
    has_story_token = any(
        tok in lowered
        for tok in ("story", "project", "universe", "lore", "series", "season", "background", "world")
    )
    workflow_hold = bool(
        re.search(
            r"before (?:we|you).*(?:production|planning|suggest)|don['’]?t organize|just listen|not finished",
            lowered,
        )
    )

    if _CORRECTION_RE.search(text):
        return IntentAnalysis(
            primary_intent=IntentType.CORRECT_ASSISTANT,
            secondary_intents=[IntentType.INFORM],
            required_postures=[InteractionPosture.APOLOGIZE_AND_CORRECT, InteractionPosture.ACKNOWLEDGE],
            forbidden_postures=[InteractionPosture.PLAN, InteractionPosture.EXECUTE],
            confidence=0.9,
            user_goal_summary="Correct prior assistant understanding or canon.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=True,
        )

    if _DISSATISFACTION_RE.search(text):
        return IntentAnalysis(
            primary_intent=IntentType.EXPRESS_DISSATISFACTION,
            secondary_intents=[IntentType.CORRECT_ASSISTANT],
            required_postures=[InteractionPosture.APOLOGIZE_AND_CORRECT, InteractionPosture.LISTEN],
            forbidden_postures=[InteractionPosture.PLAN, InteractionPosture.EXECUTE],
            confidence=0.85,
            user_goal_summary="Signal that the assistant failed to follow intent.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=True,
        )

    if _FEEDBACK_RE.search(text):
        return IntentAnalysis(
            primary_intent=IntentType.REQUEST_FEEDBACK,
            required_postures=[InteractionPosture.REVIEW, InteractionPosture.ADVISE],
            forbidden_postures=[],
            confidence=0.8,
            user_goal_summary="Request honest creative feedback.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=False,
        )

    if _NEXT_STEP_RE.search(text):
        return IntentAnalysis(
            primary_intent=IntentType.REQUEST_PLAN,
            required_postures=[InteractionPosture.ADVISE, InteractionPosture.PLAN],
            forbidden_postures=[],
            confidence=0.85,
            user_goal_summary="Ask what to do next in production/creative workflow.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=False,
        )

    # Prefer concrete "draft/create a plan" action over generic next-step planning.
    if _PLAN_RE.search(text) or re.search(r"\bdraft (?:a |the )?(?:production )?plan\b", text, re.I):
        span = _span(text, _PLAN_RE, "draft/create plan") or text[:120]
        return IntentAnalysis(
            primary_intent=IntentType.REQUEST_ACTION,
            secondary_intents=[IntentType.REQUEST_PLAN],
            required_postures=[InteractionPosture.CLARIFY, InteractionPosture.EXECUTE],
            forbidden_postures=[],
            confidence=0.8,
            user_goal_summary="Request drafting or executing a production plan.",
            evidence_spans=evidence + ([span] if span not in evidence else []),
            should_ask_question=False,
            should_use_tools=True,
            should_write_memory=False,
        )

    # c2/D13: explain questions are informational and must NOT mutate. Catch
    # them before the action branch so "How does Timeline Batch generation
    # work?" / "What is the Production Bible?" classify as INFORM, not action.
    if _EXPLAIN_QUESTION_RE.search(text):
        span = _span(text, _EXPLAIN_QUESTION_RE, "explain/how/what question") or text[:120]
        return IntentAnalysis(
            primary_intent=IntentType.INFORM,
            secondary_intents=[IntentType.EXPLAIN_PROJECT],
            required_postures=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            forbidden_postures=[InteractionPosture.PLAN, InteractionPosture.EXECUTE, InteractionPosture.CREATE],
            confidence=0.82,
            user_goal_summary="Ask an informational question about how a feature or concept works.",
            evidence_spans=evidence + ([span] if span not in evidence else []),
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=False,
        )

    if _ACTION_RE.search(text) or _ACTION_IMPERATIVE_RE.search(text):
        span = (
            _span(text, _ACTION_RE, "generate/render action")
            or _span(text, _ACTION_IMPERATIVE_RE, "imperative action")
            or text[:120]
        )
        return IntentAnalysis(
            primary_intent=IntentType.REQUEST_ACTION,
            required_postures=[InteractionPosture.CLARIFY, InteractionPosture.EXECUTE],
            forbidden_postures=[],
            confidence=0.78,
            user_goal_summary="Request a production or generation action.",
            evidence_spans=evidence + ([span] if span not in evidence else []),
            should_ask_question=True,
            should_use_tools=True,
            should_write_memory=False,
        )

    # Primary: user wants to explain / teach the project before production.
    if explain_hits >= 1 and (has_story_token or workflow_hold or "sound good" in lowered):
        secondary = [IntentType.SET_PREFERENCE] if workflow_hold else []
        if "sound good" in lowered:
            secondary.append(IntentType.SEEK_REASSURANCE)
        return IntentAnalysis(
            primary_intent=IntentType.EXPLAIN_PROJECT,
            secondary_intents=secondary or [IntentType.INFORM],
            required_postures=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            forbidden_postures=[
                InteractionPosture.ASK,
                InteractionPosture.PLAN,
                InteractionPosture.EXECUTE,
                InteractionPosture.CREATE,
            ],
            confidence=min(0.95, 0.7 + 0.05 * explain_hits),
            user_goal_summary=(
                "Explain the project/story before production planning; "
                "Co-Director should listen and learn."
            ),
            evidence_spans=evidence[:8],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=True,
        )

    if workflow_hold and not has_story_token:
        return IntentAnalysis(
            primary_intent=IntentType.PAUSE_ACTION,
            secondary_intents=[IntentType.SET_PREFERENCE],
            required_postures=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            forbidden_postures=[InteractionPosture.ASK, InteractionPosture.PLAN, InteractionPosture.EXECUTE],
            confidence=0.8,
            user_goal_summary="Pause planning/action and continue listening.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=True,
        )

    if len(text) >= 200 and has_story_token:
        return IntentAnalysis(
            primary_intent=IntentType.INFORM,
            secondary_intents=[IntentType.EXPLAIN_PROJECT],
            required_postures=[InteractionPosture.LISTEN, InteractionPosture.ACKNOWLEDGE],
            forbidden_postures=[InteractionPosture.PLAN, InteractionPosture.EXECUTE],
            confidence=0.7,
            user_goal_summary="Share substantial project information.",
            evidence_spans=evidence or [text[:120]],
            should_ask_question=False,
            should_use_tools=False,
            should_write_memory=True,
        )

    return IntentAnalysis(
        primary_intent=IntentType.UNKNOWN,
        required_postures=[InteractionPosture.ACKNOWLEDGE],
        forbidden_postures=[],
        confidence=0.4,
        user_goal_summary="Continue the conversation.",
        evidence_spans=evidence or ([text[:120]] if text else []),
        should_ask_question=False,
        should_use_tools=False,
        should_write_memory=False,
    )
