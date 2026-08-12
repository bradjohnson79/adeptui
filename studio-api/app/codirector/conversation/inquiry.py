"""Inquiry policy for the conversation core."""

from __future__ import annotations

import re
from typing import Any, Optional

from .schemas import InquiryDecision, ProjectIntelligenceSnapshot

_NEXT_STEP_PATTERNS = (
    "what should we do next",
    "what should we define next",
    "what do we do next",
    "what do we define next",
    "best next three steps",
    "next three steps",
)
_ANNOUNCE_PREFIX_RE = re.compile(
    r"^(?:i am going to tell you|i'm going to tell you|let me explain|let me begin with|begin with|i'll explain|i want to tell you|here's the lore)\b"
)


def _clean(text: str) -> str:
    return " ".join((text or "").lower().split())


_QUESTION_FACT_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:how long|duration|runtime|length|seconds?|minutes?)\b"), "runtime"),
    (re.compile(r"\b(?:what(?:'s| is) the(?: project)? title|project (?:name|called)|title\b)"), "title"),
    (re.compile(r"\b(?:what (?:format|type)|is this a|commercial|narrative|feature|short|music video)\b"), "format"),
    (re.compile(r"\b(?:main character|primary character|protagonist|lead character|who (?:is|are) the)\b"), "primary_character"),
    (re.compile(r"\b(?:do we have a script|script (?:exist|ready|draft)|screenplay)\b"), "script_exists"),
    (re.compile(r"\b(?:what (?:workspace|tab) are we|where are we|current (?:workspace|tab))\b"), "active_workspace"),
    (re.compile(r"\b(?:which project|project id|current project)\b"), "project_id"),
]


def _extract_facts(known: dict[str, str], state: dict) -> None:
    domains = state.get("domains") or {}
    for domain_key, domain_data in domains.items():
        if isinstance(domain_data, dict):
            for field_key, field_data in domain_data.items():
                if isinstance(field_data, dict):
                    value = field_data.get("value")
                    provenance = str(field_data.get("provenance", "") or "")
                    if value and provenance in ("creator-stated", "creator-approved", "project-persisted"):
                        known[field_key] = str(value)


def _check_known_fact(
    question: str,
    *,
    production_state: Optional[dict] = None,
    story_evidence: Optional[Any] = None,
) -> bool:
    """Check if a question can be answered from authoritative state.

    Suppression rules:
    - creator-stated facts → suppress question entirely
    - creator-approved facts → suppress question entirely
    - ai-inferred → do NOT suppress (inference is not truth)
    - unknown → do not pretend to know (return False — don't suppress AND don't invent)

    Returns True when the question should NOT be asked (already known).
    """
    if not question:
        return False

    known: dict[str, str] = {}
    if isinstance(production_state, dict):
        _extract_facts(known, production_state)

    lower = question.lower()
    for pattern, key in _QUESTION_FACT_MAP:
        if pattern.search(lower):
            return key in known

    return False


def _check_result(
    decision: InquiryDecision,
    production_state: Optional[dict] = None,
) -> InquiryDecision:
    if decision.should_ask and decision.question and _check_known_fact(decision.question, production_state=production_state):
        return InquiryDecision(should_ask=False, question=None, mode="conversation")
    return decision


def _is_next_step_prompt(text: str) -> bool:
    return any(phrase in text for phrase in _NEXT_STEP_PATTERNS)


def _is_character_acceptance(text: str) -> bool:
    return bool(
        re.match(r"^(?:yes|ok|okay|sure|absolutely)\b", text)
        and any(phrase in text for phrase in ("main character", "lead character", "character"))
    )


def _is_announce_only_continuation(text: str) -> bool:
    if _is_character_acceptance(text):
        return False
    return bool(_ANNOUNCE_PREFIX_RE.match(text))


def decide_inquiry(
    user_message: str,
    snapshot: ProjectIntelligenceSnapshot,
    stage: str,
    substate: str | None,
    production_state: Optional[dict] = None,
) -> InquiryDecision:
    """Choose whether the reply should ask one grounded follow-up question."""

    text = _clean(user_message)
    if not text:
        return InquiryDecision(should_ask=False, mode="conversation")

    if _is_announce_only_continuation(text):
        return InquiryDecision(should_ask=False, mode="invite_continuation")

    if any(
        phrase in text
        for phrase in (
            "create a draft plan",
            "draft plan",
            "create a plan",
            "make a draft plan",
            "make a plan for",
        )
    ):
        return InquiryDecision(should_ask=False, mode="execute_action")

    if _is_next_step_prompt(text):
        return InquiryDecision(should_ask=False, mode="recommend_next_step")

    if (
        text.startswith("correction:")
        or text.startswith("actually ")
        or " don't use " in f" {text} "
        or " do not use " in f" {text} "
        or " don't define " in f" {text} "
        or " do not define " in f" {text} "
        or " don't make " in f" {text} "
        or " do not make " in f" {text} "
        or " don't treat " in f" {text} "
        or " do not treat " in f" {text} "
    ):
        return InquiryDecision(should_ask=False, mode="confirm_correction")

    if "let me explain the lore" in text or "explain the lore" in text:
        return InquiryDecision(should_ask=False, mode="receive_information")

    if stage == "Characters" and substate == "Lead Character":
        if "main character" in text or "lead character" in text:
            return _check_result(
                InquiryDecision(
                    should_ask=True,
                    question="What is the one trait or wound that most defines your lead character right now?",
                    mode="request_clarification",
                ),
                production_state=production_state,
            )
        if not snapshot.keyCharacters:
            return _check_result(
                InquiryDecision(
                    should_ask=True,
                    question="Who is the lead character, and what do they want more than anything at the start?",
                    mode="request_clarification",
                ),
                production_state=production_state,
            )

    if text in {"yes", "y", "continue", "go on", "keep going", "ok", "okay"}:
        question = snapshot.openQuestions[0] if snapshot.openQuestions else None
        if question:
            return _check_result(
                InquiryDecision(should_ask=True, question=question, mode="request_clarification"),
                production_state=production_state,
            )

    if text.endswith("?"):
        return InquiryDecision(should_ask=False, mode="answer_question")

    return InquiryDecision(should_ask=False, mode="receive_information")
