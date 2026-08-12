"""Response grounding / quality gates against DialoguePlan (+ companion gates)."""

from __future__ import annotations

import re
from typing import Any

from .schemas import DialoguePlan, IntentAnalysis, ResponseGroundingCheck

_TITLE_PREMISE_RE = re.compile(
    r"("
    r"clear project title|"
    r"one[- ]sentence (?:creative )?premise|"
    r"what(?:'s| is) (?:the|your) (?:title|premise|logline|genre)|"
    r"tell me (?:the|your) (?:title|premise|logline)|"
    r"choose a (?:title|premise)|"
    r"need a (?:title|premise|logline)"
    r")",
    re.I,
)
_QUESTIONNAIRE_RE = re.compile(
    r"("
    r"first[,:]?\s*(?:what|who|where)|"
    r"answer these questions|"
    r"fill (?:in|out)|"
    r"before we (?:can )?continue[,:].{0,40}\?"
    r")",
    re.I,
)
_PREMATURE_PLAN_RE = re.compile(
    r"("
    r"let(?:'|’)s (?:start|begin) (?:production|planning)|"
    r"production plan|"
    r"scene breakdown|"
    r"shot list|"
    r"here(?:'|’)s (?:a|the) (?:schedule|budget)"
    r")",
    re.I,
)
_GENERIC_PRAISE_RE = re.compile(
    r"("
    r"you(?:'re| are) (?:a )?genius|"
    r"everything (?:you create )?is (?:amazing|excellent|perfect)|"
    r"you(?:'re| are) (?:so )?talented|"
    r"this is perfect(?:!|\.)|"
    r"absolutely brilliant"
    r")",
    re.I,
)
_DEPENDENCY_RE = re.compile(
    r"\b(you need me|i'll always be here for you|trust me completely|without me you)\b",
    re.I,
)
_AUTO_AGREE_RE = re.compile(
    r"\b(you(?:'re| are) (?:totally )?right[,.]? (?:let(?:'|’)s|we should) (?:remove|delete|scrap)|"
    r"absolutely[,.]? (?:cut|remove) (?:it|the))\b",
    re.I,
)
_PREMATURE_CAUTION_RE = re.compile(
    r"\b(be careful|risk(?:s)? include|however[,.]|feasibility concern|may not work|"
    r"market (?:will|won['’]?t)|too ambitious)\b",
    re.I,
)
_UNINVITED_CRITIQUE_RE = re.compile(
    r"\b(the (?:weak(?:est)?|problem|flaw)|this (?:doesn['’]?t|does not) work|"
    r"you should cut|fundamentally broken)\b",
    re.I,
)


def reply_violates_dialogue_plan(reply: str, plan: DialoguePlan) -> list[str]:
    """Return violation notes if reply contradicts DialoguePlan."""

    notes: list[str] = []
    text = reply or ""
    if plan.question_budget <= 0 and text.count("?") >= 1:
        if _TITLE_PREMISE_RE.search(text) or _QUESTIONNAIRE_RE.search(text) or text.count("?") >= 2:
            notes.append("Exceeded question_budget=0")
    if plan.workflow_advance_policy == "HOLD":
        if _TITLE_PREMISE_RE.search(text):
            notes.append("Title/premise intake while workflow HOLD")
        if _PREMATURE_PLAN_RE.search(text):
            notes.append("Premature production planning while workflow HOLD")
        if _QUESTIONNAIRE_RE.search(text):
            notes.append("Questionnaire pattern while workflow HOLD")
    for prohibited in plan.prohibited_elements:
        key = prohibited.lower()
        if "title" in key and _TITLE_PREMISE_RE.search(text):
            notes.append(f"Prohibited element: {prohibited}")
        if "premise" in key and re.search(r"\bpremise\b", text, re.I) and _TITLE_PREMISE_RE.search(text):
            notes.append(f"Prohibited element: {prohibited}")
        if "questionnaire" in key and _QUESTIONNAIRE_RE.search(text):
            notes.append(f"Prohibited element: {prohibited}")
        if "empty praise" in key and _GENERIC_PRAISE_RE.search(text):
            notes.append("NO_GENERIC_PRAISE")
        if "automatic agreement" in key and _AUTO_AGREE_RE.search(text):
            notes.append("NO_AUTOMATIC_AGREEMENT")
    if plan.tool_policy == "NONE" and re.search(r"\b(?:i (?:have )?run|tool|queued generation)\b", text, re.I):
        notes.append("Claimed tool use under tool_policy=NONE")
    return notes


def evaluate_grounding(
    *,
    user_message: str,
    reply: str,
    intent: IntentAnalysis,
    plan: DialoguePlan,
    companion: dict[str, Any] | None = None,
) -> ResponseGroundingCheck:
    """Deterministic grounding checks before a reply is shown."""

    text = reply or ""
    lowered = text.lower()
    companion = companion or {}
    violations = reply_violates_dialogue_plan(text, plan)

    addresses = len(text.strip()) >= 24
    reflects = True
    if plan.mode.value == "LISTENING":
        listening_markers = bool(
            re.search(
                r"\b(listen|hear|story|learn|understand|share|tell me|tracking|holding|"
                r"whenever you(?:'|’)re ready|before (?:we )?plan)\b",
                lowered,
            )
        )
        # INFORM lore: content overlap counts as reflecting the user's goal.
        user_tokens = {
            t
            for t in re.findall(r"[a-z0-9']{4,}", (user_message or "").lower())
            if t
            not in {
                "that",
                "this",
                "with",
                "from",
                "have",
                "about",
                "into",
                "your",
                "what",
                "when",
                "there",
                "their",
                "them",
                "then",
                "than",
            }
        }
        reply_tokens = set(re.findall(r"[a-z0-9']{4,}", lowered))
        content_overlap = len(user_tokens & reply_tokens) >= 2
        reflects = listening_markers or (intent.primary_intent.value == "INFORM" and content_overlap)

    premature = bool(_PREMATURE_PLAN_RE.search(text) or _TITLE_PREMISE_RE.search(text)) and plan.workflow_advance_policy == "HOLD"
    unnecessary_q = plan.question_budget <= 0 and (
        bool(_TITLE_PREMISE_RE.search(text)) or text.count("?") >= 2 or bool(_QUESTIONNAIRE_RE.search(text))
    )
    contradicts = premature or bool(violations)

    notes = list(violations)
    if not addresses:
        notes.append("Reply too short to address the latest message")
    if plan.mode.value == "LISTENING" and not reflects:
        notes.append("Listening reply does not reflect listening/story goal")

    # Companion / advisory gates
    if _GENERIC_PRAISE_RE.search(text):
        notes.append("NO_GENERIC_PRAISE")
    if _DEPENDENCY_RE.search(text):
        notes.append("NO_DEPENDENCY_LANGUAGE")
    if companion.get("direct_critique_requested") and re.search(
        r"\b(you(?:'re| are) doing (?:great|amazing)|don['’]?t worry|believe in yourself)\b",
        lowered,
    ):
        notes.append("DIRECT_CRITIQUE_REQUEST_HONORED")
    if companion.get("no_relitigation") and re.search(
        r"\b(as i (?:already )?warned|you ignored my advice|i still think (?:removing|cutting))\b",
        lowered,
    ):
        notes.append("NO_REPEATED_ARGUMENT_AFTER_CONFIRMATION")
    if companion.get("exploration_only") and re.search(
        r"\b(canon (?:is )?updated|i(?:'|’)ve (?:updated|changed) (?:the )?(?:bible|wiki|canon))\b",
        lowered,
    ):
        notes.append("EXPLORATION_NOT_CANONIZED")
    if companion.get("should_encourage_with_evidence") and _GENERIC_PRAISE_RE.search(text):
        notes.append("PROJECT_SPECIFIC_SUPPORT_PRESENT_WHEN_ENCOURAGING")

    # Personality / discovery gates
    if companion.get("emergence_protection"):
        if companion.get("caution_allowed") is False and _PREMATURE_CAUTION_RE.search(text):
            notes.append("NO_PREMATURE_CAUTION")
        if companion.get("critique_allowed") is False and not companion.get("direct_critique_requested"):
            if _UNINVITED_CRITIQUE_RE.search(text):
                notes.append("NO_UNINVITED_CRITIQUE_DURING_EMERGENCE")
    if companion.get("require_response_evidence"):
        evidence = companion.get("response_evidence") or {}
        count = int(evidence.get("count") or 0)
        if count < int(evidence.get("required_minimum") or 2):
            notes.append("RESPONSE_EVIDENCE_PRESENT")
    if companion.get("fake_wiki_claim"):
        notes.append("NO_FAKE_WIKI_CLAIMS")
    user_name = str(companion.get("user_preferred_name") or "").strip()
    if user_name and companion.get("require_name_respect") and len(text) > 40:
        # Soft: if reply uses a different direct address heavily, note — not hard fail unless contradicted
        pass

    # Hands-on partnership gates
    if companion.get("require_useful_preview"):
        notes.append("USEFUL_PREVIEW_BEFORE_MAJOR_COMMITMENT")
    if companion.get("require_why_now"):
        notes.append("ARTIFACT_OFFER_EXPLAINS_WHY_NOW")
    if companion.get("no_unauthorized_authorship"):
        notes.append("NO_UNAUTHORIZED_AUTHORSHIP")
    if companion.get("premature_marketing"):
        notes.append("NO_PREMATURE_MARKETING_PRESSURE")
    if companion.get("locked_rewrite_attempt"):
        notes.append("NO_SILENT_CANON_OR_DELIVERABLE_LOCK")
    if companion.get("artifact_offer_active") and companion.get("preview_present"):
        if re.search(r"\bi can create (?:a |the )?(?:pitch|treatment|template)\.?$", lowered.strip()):
            if "possible central hook" not in lowered and "preview" not in lowered:
                notes.append("USEFUL_PREVIEW_BEFORE_MAJOR_COMMITMENT")

    # c2/D14: the previous `gate_fail` boolean was dead — it was computed and
    # assigned to `_` but never influenced the decision. The `violations` list
    # (below) is authoritative: companion notes that are not already present are
    # appended as violations, and `violates_dialogue_plan` is derived from it.
    # Removed the dead branch rather than wiring a redundant signal alongside the
    # authoritative one.
    # Treat new companion notes as violations
    companion_notes = [n for n in notes if n not in violations and n not in {"Reply too short to address the latest message", "Listening reply does not reflect listening/story goal"}]
    if companion_notes:
        violations = list(violations) + companion_notes

    return ResponseGroundingCheck(
        directly_addresses_latest_message=addresses,
        reflects_user_goal=reflects and bool(intent.user_goal_summary or user_message),
        contradicts_user_requested_flow=contradicts or bool(companion_notes),
        introduces_premature_workflow=premature,
        asks_unnecessary_question=unnecessary_q,
        contains_unsupported_assumption=bool(re.search(r"\bas we (?:already )?established\b", lowered))
        and "not yet" not in lowered,
        violates_dialogue_plan=bool(violations),
        notes=notes,
    )
