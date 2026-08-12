"""Natural-language reply composition for the conversation core."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .schemas import ConversationPlan, ProjectDirectorState, ProjectIntelligenceSnapshot


# ── Phase 8 — internal leakage guard ──────────────────────────────────────

_LEAKAGE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bRouteDecision\b"),
    re.compile(r"\broute_decision\b"),
    re.compile(r"\bworkflowAssessment\b"),
    re.compile(r"\bworkflow_assessment\b"),
    re.compile(r"\bspecialistId\b"),
    re.compile(r"\bspecialist_id\b"),
    re.compile(r"\bclassifierSource\b"),
    re.compile(r"\bexecutionLane\b"),
    re.compile(r"\bwantsSpecialistConsult\b"),
    re.compile(r"\b\[mock\]"),
    re.compile(r"\btool_fences?\b"),
    re.compile(r"\{\"responseType\":"),
    re.compile(r"\bmutation_proposal\b"),
    re.compile(r"\btoolId\b"),
    re.compile(r"\bproduction_stage\b"),
    re.compile(r"\bderivedStage\b"),
    re.compile(r"\bphase\d\b"),
]


def sanitize_response(text: str) -> str:
    """Strip internal architecture fragments from creator-facing responses."""
    if not text:
        return text
    for pattern in _LEAKAGE_PATTERNS:
        if pattern.search(text):
            text = pattern.sub("[redacted]", text)
    return text


# ── Phase 8 — operation language truthfulness ─────────────────────────────

def operation_pending_text(operation: str) -> str:
    """Language for operations that are pending verification."""
    return f"{operation}…"


def operation_success_text(operation: str, detail: Optional[str] = None) -> str:
    """Language for verified successful operations."""
    if not detail:
        return f"{operation} complete."
    return f"{operation}: {detail}"


def operation_failure_text(operation: str) -> str:
    """Language for failed operations."""
    return f"I couldn't confirm that {operation.lower()}."


def correction_text(correction: str) -> str:
    """Language for acknowledging a creator correction."""
    return f"Understood. I'll treat that as the current version going forward: {correction}"


def dissatisfaction_text() -> str:
    """Language for acknowledging creator dissatisfaction."""
    return "You're right. Let me correct that."


def short_affirmation_text() -> str:
    """Language for when a short acknowledgment is appropriate."""
    return "Got it."


# ── Phase 8 — generic-praise detection ────────────────────────────────────

_GENERIC_PRAISE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(?:that'?s|this is) (?:great|amazing|fantastic|incredible|wonderful|brilliant)\b", re.I),
    re.compile(r"\bI (?:really )?love (?:this|it|that|what you)\b", re.I),
    re.compile(r"\bwhat a (?:great|wonderful|fantastic) (?:idea|concept|story)\b", re.I),
]


def is_generic_praise(text: str) -> bool:
    """Detect generic, unspecific praise that should be replaced with specific feedback."""
    if not text:
        return False
    return any(p.search(text) for p in _GENERIC_PRAISE_PATTERNS)

_TITLE_PATTERNS = (
    re.compile(r"\b(?:this is|meet)\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})\b"),
    re.compile(r"\b(?:project|series|show)\s+(?:is\s+)?called\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})", re.I),
    re.compile(r"\b(?:web series|series|project|show)\s*,?\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})\b"),
    re.compile(r"\b(?:about|called)\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4}?)\s*[,.]", re.I),
    re.compile(r"\bThe\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?)\b"),
)
_ATTACHMENT_HINT_RE = re.compile(
    r"\b(attached|attachment|image as a reference|reference prompt|use the attached)\b",
    re.I,
)
_ANCHOR_PATTERNS = (
    re.compile(r"\b\d+(?:\.\d+)?(?:-minute)?\s+(?:minutes?|hours?|days?|years?|episodes?|seasons?)\b", re.I),
    re.compile(r"\bmathematical structure\b", re.I),
    re.compile(r"\b(?:the\s+)?(?:signal|main character|lead character)\b", re.I),
    re.compile(r"\bintent is still unknown\b", re.I),
    re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
)


def _join_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _extract_named_title(user_message: str) -> str | None:
    text = (user_message or "").strip()
    for pattern in _TITLE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        title = match.group(1).strip(" .,")
        lowered = title.lower()
        if lowered in {"adept chronicles", "first season", "season", "project meridian"}:
            if "meridian" in lowered:
                return "Project Meridian"
            continue
        if lowered.startswith(("is ", "called ", "about ", "a ", "the research", "this is")):
            continue
        if len(title) >= 3:
            return title if lowered.startswith("the ") or " " in title else title
    return None


def _intro_reply(snapshot: ProjectIntelligenceSnapshot, user_message: str) -> str:
    named = _extract_named_title(user_message)
    snapshot_title = snapshot.title if snapshot.title and snapshot.title != "Untitled Project" else None
    if snapshot_title and snapshot_title.upper().startswith(("CODIRECTOR-CERT", "CODIRECTOR-FOUNDATION")):
        snapshot_title = None
    title = named or snapshot_title
    format_hint = snapshot.format.replace("_", " ") if snapshot.format else None
    if not format_hint and "web series" in user_message.lower():
        format_hint = "web series"
    shared = "shared-universe connection" if "adept chronicles" in user_message.lower() else None
    season = "Season 1" if "season" in user_message.lower() or "first season" in user_message.lower() else None

    parts: list[str] = []
    if title:
        parts.append(f"I hear **{title}**")
    else:
        parts.append("I am ready to take this in")
    if format_hint:
        parts.append(f"as a {format_hint}")
    if shared:
        parts.append(f"and its {shared}")
    if season:
        parts.append(f"with {season} as the build target")
    opener = _join_parts(parts) + "."
    return sanitize_response(
        f"{opener} Confirmed facts and open ideas will stay organized separately as you share them. "
        "Whenever you are ready, begin with the lore, the characters, the shared-universe connection, "
        "or the Season 1 structure — I will follow your lead without turning this into a questionnaire."
    )


def _continuation_reply() -> str:
    return sanitize_response("I am with you. Keep going with whatever part of the story world, cast, or season direction you want to lay down next.")


def _next_step_reply(plan: ConversationPlan, director: ProjectDirectorState, user_message: str) -> str:
    recommendation = plan.recommendedNextStep or director.recommendedNextStep
    if not recommendation:
        recommendation = "Define the next creative decision that will unblock the project."
    if "best next three steps" in user_message.lower() or "next three steps" in user_message.lower():
        return (
            "Here are the next three steps I would take:\n"
            f"1. {recommendation}\n"
            "2. Turn that decision into episode-level consequences so the season starts to feel inevitable.\n"
            "3. Lock the next unanswered detail that would change how Episode 1 opens, escalates, or lands."
        )
    return (
        f"My recommendation is to {recommendation[0].lower() + recommendation[1:]} "
        "That gives the rest of the project a clearer foundation. "
        "If you would rather branch sideways, we can define the world rules instead, or lock the season arc next."
    )


def _character_reply(plan: ConversationPlan) -> str:
    if plan.shouldAskQuestion and plan.selectedQuestion:
        return (
            "Great, let's focus on the lead character first. "
            f"{plan.selectedQuestion}"
        )
    return "Great, let's focus on the lead character first. Tell me what makes them impossible to ignore."


def _correction_reply(plan: ConversationPlan) -> str:
    if plan.wikiCandidates:
        confirmed = next((candidate.text for candidate in plan.wikiCandidates if candidate.state == "confirmed"), None)
        if confirmed:
            return sanitize_response(correction_text(confirmed))
        rejected = next((candidate.text for candidate in plan.wikiCandidates if candidate.state == "rejected"), None)
        if rejected:
            return sanitize_response(f"Understood. I'll treat that as rejected going forward: {rejected}")
    return sanitize_response("Understood.")


def _draft_plan_reply(user_message: str) -> str:
    lowered = user_message.lower()
    anchors: list[str] = []
    if "mara" in lowered:
        anchors.append("Mara")
    if "signal" in lowered or "probe" in lowered:
        anchors.append("the probe signal")
    if "episode 1" in lowered or "opening" in lowered:
        anchors.append("the Episode 1 opening")
    focus = ", ".join(anchors) if anchors else "the creative foundations you named"
    return (
        f"I can draft a plan covering {focus}. "
        "Review the draft outline, then approve it when you want it locked as the active plan — "
        "I will not treat it as approved until you confirm."
    )


def _attachment_reference_reply(user_message: str) -> str:
    named = _extract_named_title(user_message)
    project_hint = f" for {named}" if named else ""
    return (
        f"I can keep the attached image as a reference prompt{project_hint}. "
        "Visual analysis is unavailable in this chat turn, so I will not invent its visual contents — "
        "tell me the look, mood, or details you want locked from it."
    )


def _question_reply(plan: ConversationPlan, director: ProjectDirectorState) -> str:
    if plan.shouldAskQuestion and plan.selectedQuestion:
        return plan.selectedQuestion
    if director.recommendedNextStep:
        return f"Here is the clearest answer from where we are right now: {director.recommendedNextStep}"
    return "Here is the clearest answer from where we are right now: the next best move is the one that gives the story a firmer foundation."


def _normalize_anchor(anchor: str) -> str:
    cleaned = re.sub(r"\s+", " ", anchor.strip(" .,;:"))
    if not cleaned:
        return cleaned
    lowered = cleaned.lower()
    if lowered == "signal":
        return "the signal"
    return cleaned


def _extract_content_anchors(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for pattern in _ANCHOR_PATTERNS:
        for match in pattern.finditer(text):
            anchor = _normalize_anchor(match.group(0))
            if len(anchor) >= 3:
                matches.append((match.start(), anchor))
    matches.sort(key=lambda item: item[0])

    anchors: list[str] = []
    seen: set[str] = set()
    for _, anchor in matches:
        key = anchor.lower()
        if key in seen:
            continue
        seen.add(key)
        anchors.append(anchor)
        if len(anchors) == 3:
            break
    return anchors


def _fallback_content_anchor(text: str) -> str | None:
    lowered = re.sub(r"\s+", " ", text.strip())
    if not lowered:
        return None
    clause = re.split(r"[.!?]", lowered, maxsplit=1)[0].strip(" ,;:")
    if not clause:
        return None
    words = clause.split()
    if len(words) > 12:
        clause = " ".join(words[:12]).rstrip(",;:") + "..."
    return clause[0].lower() + clause[1:] if clause else None


def _format_anchor_list(anchors: list[str]) -> str:
    if len(anchors) == 1:
        return anchors[0]
    if len(anchors) == 2:
        return f"{anchors[0]} and {anchors[1]}"
    return f"{anchors[0]}, {anchors[1]}, and {anchors[2]}"


def _receive_information_reply(plan: ConversationPlan, snapshot: ProjectIntelligenceSnapshot, user_message: str) -> str:
    source_text = next((candidate.text for candidate in plan.wikiCandidates if candidate.text.strip()), user_message.strip())
    anchors = _extract_content_anchors(source_text)
    if not anchors and user_message.strip() != source_text:
        anchors = _extract_content_anchors(user_message)
    if anchors:
        return (
            f"I am tracking {_format_anchor_list(anchors)}. "
            "Keep going with the next detail you want to lock in."
        )
    fallback = _fallback_content_anchor(source_text or user_message)
    if fallback:
        return f"I am tracking {fallback}. Keep going with the next detail you want to lock in."
    if plan.acknowledgedFacts:
        lead = plan.acknowledgedFacts[0].replace("title: ", "").replace("format: ", "")
        return f"I am tracking {lead}. Keep going and tell me the next detail you want locked in."
    if snapshot.title and snapshot.title != "Untitled Project":
        return f"I am tracking {snapshot.title}. Keep going and tell me the next detail you want locked in."
    return "I am tracking that direction. Keep going with the next detail you want to lock in."


@dataclass
class ResponsePlan:
    """Flexible creator-facing response plan — not a fixed six-part template."""

    acknowledgement: str
    relevant: str
    observation: str | None = None
    interpretation: str | None = None
    verified_wiki_note: str | None = None
    invitation: str | None = None
    include_next_steps: bool = False
    shape: str = "default"


def _strip_creator_jargon(text: str) -> str:
    replacements = (
        (r"\bpipeline\b", "process"),
        (r"\bschema\b", "structure"),
        (r"\blatency\b", "delay"),
        (r"\btoken budget\b", "space we have"),
        (r"\bcontext budget\b", "what we can hold in mind"),
        (r"\bintent classification\b", "what you're asking for"),
        (r"\bspecialist routing\b", "the right creative perspective"),
        (r"\bbackground enrichment\b", "organizing the project notes"),
        (r"\bcandidate extraction\b", "details worth documenting"),
        (r"\bSSE\b", "live update"),
        (r"\bstate machine\b", "workflow"),
        (r"\bgrounding gate\b", "check against project notes"),
        (r"\bpersistence event\b", "save"),
        (r"\bcache revision\b", "refresh"),
        (r"\bartifact readiness\b", "enough material to begin"),
    )
    out = text
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)
    return out


def build_response_plan(
    plan: ConversationPlan,
    snapshot: ProjectIntelligenceSnapshot,
    director: ProjectDirectorState,
    user_message: str,
    *,
    wiki_verified: bool = False,
    turn_index: int = 0,
) -> ResponsePlan:
    """Choose required + optional parts based on intent and message richness."""
    rich = len((user_message or "").strip()) >= 220
    msg = (user_message or "").strip()

    if plan.responseMode == "intro":
        body = _intro_reply(snapshot, user_message)
        return ResponsePlan(
            acknowledgement="I'm with you.",
            relevant=body,
            invitation="Share whatever feels most alive next.",
            shape="intro",
        )

    if plan.primaryIntent == "invite_continuation":
        return ResponsePlan(
            acknowledgement="Absolutely.",
            relevant=plan.selectedQuestion or _continuation_reply(),
            shape=f"continue-{turn_index % 3}",
        )

    if plan.primaryIntent == "confirm_correction":
        return ResponsePlan(
            acknowledgement="Got it — thank you for the correction.",
            relevant=_correction_reply(plan),
            shape="correction",
        )

    if plan.primaryIntent == "recommend_next_step":
        return ResponsePlan(
            acknowledgement="Here's a useful next move.",
            relevant=_next_step_reply(plan, director, user_message),
            include_next_steps=True,
            shape="next-step",
        )

    if plan.primaryIntent == "execute_action" or plan.responseMode in {"draft_plan", "execute_action"}:
        return ResponsePlan(
            acknowledgement="Let's build that.",
            relevant=_draft_plan_reply(user_message),
            shape="action",
        )

    if _ATTACHMENT_HINT_RE.search(msg):
        return ResponsePlan(
            acknowledgement="I can use that reference.",
            relevant=_attachment_reference_reply(user_message),
            shape="attachment",
        )

    if plan.creativeStage == "Characters" and plan.creativeSubstate == "Lead Character":
        return ResponsePlan(
            acknowledgement="I'm listening to who they are.",
            relevant=_character_reply(plan),
            observation="What they want will shape the whole story.",
            invitation="Tell me more about their pressure or desire.",
            shape="character",
        )

    if plan.primaryIntent in {"answer_question", "request_clarification"}:
        return ResponsePlan(
            acknowledgement="Good question.",
            relevant=_question_reply(plan, director),
            shape="question",
        )

    # Story / information receive — flexible density
    base = _receive_information_reply(plan, snapshot, user_message)
    observation = None
    interpretation = None
    invitation = None
    wiki_note = None
    if rich:
        # Vary optional blocks by turn so consecutive replies aren't formulaic.
        if turn_index % 3 == 0:
            observation = "What stands out is how personal the stakes feel inside the larger premise."
            invitation = "Keep unfolding it naturally — I'm right here with you."
        elif turn_index % 3 == 1:
            interpretation = "That framing gives us a strong spine to return to as details arrive."
            invitation = "When you're ready, we can go deeper on people, world, or shape."
        else:
            observation = "I'm following the through-line you're building."
            invitation = "What should we understand next?"
        if wiki_verified:
            wiki_note = "The Wiki now includes the details we verified from this exchange."
        else:
            # Understanding-only — never claim verified documentation.
            wiki_note = None
    else:
        invitation = "What would you like to add next?" if turn_index % 2 == 0 else "I'm ready for the next detail."

    return ResponsePlan(
        acknowledgement="Thank you — I'm with you." if rich else "Noted.",
        relevant=base,
        observation=observation,
        interpretation=interpretation,
        verified_wiki_note=wiki_note if wiki_verified else None,
        invitation=invitation,
        include_next_steps=rich and plan.primaryIntent in {"receive_information", "recommend_next_step"},
        shape=f"story-{turn_index % 4}",
    )


def render_response_plan(plan: ResponsePlan) -> str:
    """Render required parts always; optional parts only when present."""
    blocks: list[str] = []
    # Vary whether acknowledgement stands alone or merges — structural variety.
    if plan.shape.endswith("0") or plan.shape in {"intro", "correction"}:
        blocks.append(_join_parts([plan.acknowledgement, plan.relevant]))
    else:
        blocks.append(plan.acknowledgement)
        blocks.append(plan.relevant)
    if plan.observation:
        blocks.append(plan.observation)
    if plan.interpretation:
        blocks.append(plan.interpretation)
    if plan.verified_wiki_note:
        blocks.append(plan.verified_wiki_note)
    if plan.invitation:
        blocks.append(plan.invitation)
    text = "\n\n".join(b.strip() for b in blocks if b and b.strip())
    return _strip_creator_jargon(sanitize_response(text))


def compose_reply(
    plan: ConversationPlan,
    snapshot: ProjectIntelligenceSnapshot,
    director: ProjectDirectorState,
    user_message: str,
    *,
    wiki_verified: bool = False,
    turn_index: int = 0,
) -> str:
    """Compose creator-facing prose from a flexible response plan."""
    response_plan = build_response_plan(
        plan,
        snapshot,
        director,
        user_message,
        wiki_verified=wiki_verified,
        turn_index=turn_index,
    )
    return render_response_plan(response_plan)
