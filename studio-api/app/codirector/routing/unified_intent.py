"""Unified intent classification — the single vocabulary for Co-Director dispatch.

Replaces the two parallel routing vocabularies (foundation `IntentType` 19 values
and Phase 3 `RouteActionClass` 11 values) with one classification that the
hybrid dispatch architecture reads.

The Agent Execution Law depends on this contract: when `intent == EXECUTION`,
the dispatcher MUST act (execute, request missing info, request approval, or
report real failure) — never acknowledge and return to conversation.

FROZEN CONTRACT — Law #16. Do not change field names without primary approval.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class UnifiedIntentKind(str, Enum):
    """The five canonical intent classes from spec §5."""

    CONVERSATION = "CONVERSATION"
    ANALYSIS = "ANALYSIS"
    PROPOSAL = "PROPOSAL"
    EXECUTION = "EXECUTION"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class DispatchStrategy(str, Enum):
    """How an EXECUTION intent should be dispatched (hybrid dispatch)."""

    # High-confidence execution → bypass LLM, dispatch directly to capability handler.
    DETERMINISTIC = "deterministic"
    # Nuanced/compound execution → inject curated tool catalog, let LLM call tools.
    CURATED_TOOLS = "curated_tools"
    # Not executable (conversation/analysis/proposal/clarification) → LLM-only.
    LLM_ONLY = "llm_only"


class UnifiedIntent(BaseModel):
    """The single classification output for one user turn.

    Consumed by `service.py` to decide the dispatch branch:
    - DETERMINISTIC → `ExecutionDispatcher.dispatch`
    - CURATED_TOOLS → `build_generation_messages(curated_tool_ids=...)`
    - LLM_ONLY → existing foundation LLM path

    The `capability` field is empty for non-execution intents. When non-empty,
    it names the `CapabilityId` the dispatcher should resolve (spec §9).
    """

    intent: UnifiedIntentKind = UnifiedIntentKind.CONVERSATION
    capability: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    dispatch: DispatchStrategy = DispatchStrategy.LLM_ONLY

    # Machine-readable execution decision (spec §6). Only populated when
    # intent == EXECUTION. Not exposed to the user directly.
    execution_decision: Optional[dict[str, Any]] = None

    # True when genuinely required information is missing (spec §7, §31).
    requires_clarification: bool = False
    clarification_question: str = ""
    missing_required_fields: list[str] = Field(default_factory=list)

    # Traceability — which classifier produced this (deterministic regex,
    # semantic similarity, or LLM reasoning).
    classifier_source: Literal["deterministic", "semantic", "llm"] = "deterministic"

    # Evidence for observability (spec §48).
    evidence: list[str] = Field(default_factory=list)

    # Target workspace/tab if the intent implies navigation (NAVIGATE-class).
    target_workspace: Optional[str] = None

    # Curated tool IDs to inject into the LLM prompt when dispatch == CURATED_TOOLS.
    curated_tool_ids: list[str] = Field(default_factory=list)

    @property
    def is_execution(self) -> bool:
        return self.intent == UnifiedIntentKind.EXECUTION

    @property
    def is_high_confidence_execution(self) -> bool:
        return self.is_execution and self.confidence >= 0.7 and self.dispatch == DispatchStrategy.DETERMINISTIC


def from_route_decision(route_decision: Optional[Any]) -> UnifiedIntent:
    """Bridge an existing Phase 3 `RouteDecision` to a `UnifiedIntent`.

    This is the adapter that lets the unified dispatcher consume the existing
    two classifiers without rewriting them. Called during the transition period
    while the unified classifier is being wired.
    """
    if route_decision is None:
        return UnifiedIntent(
            intent=UnifiedIntentKind.CONVERSATION,
            classifier_source="deterministic",
        )

    action = getattr(route_decision, "actionClass", None)
    action_value = action.value if action else "UNKNOWN"

    kind_map = {
        "DISCUSS": UnifiedIntentKind.CONVERSATION,
        "NAVIGATE": UnifiedIntentKind.CONVERSATION,
        "READ_INSPECT": UnifiedIntentKind.ANALYSIS,
        "MODIFY_KNOWLEDGE": UnifiedIntentKind.PROPOSAL,
        "PROPOSE_CREATIVE_CHANGE": UnifiedIntentKind.PROPOSAL,
        "EXECUTE_PRODUCTION": UnifiedIntentKind.EXECUTION,
        "APPROVE": UnifiedIntentKind.EXECUTION,
        "REJECT": UnifiedIntentKind.EXECUTION,
        "CLARIFY": UnifiedIntentKind.CLARIFICATION_REQUIRED,
        "AMBIGUOUS": UnifiedIntentKind.CLARIFICATION_REQUIRED,
        "UNKNOWN": UnifiedIntentKind.CONVERSATION,
    }

    kind = kind_map.get(action_value, UnifiedIntentKind.CONVERSATION)
    confidence = float(getattr(route_decision, "confidence", 0.0) or 0.0)
    classifier_source = getattr(route_decision, "classifierSource", "deterministic")

    dispatch = DispatchStrategy.LLM_ONLY
    if kind == UnifiedIntentKind.EXECUTION:
        if confidence >= 0.7 and getattr(route_decision, "capabilityAvailable", True):
            dispatch = DispatchStrategy.DETERMINISTIC
        else:
            dispatch = DispatchStrategy.CURATED_TOOLS

    return UnifiedIntent(
        intent=kind,
        confidence=confidence,
        dispatch=dispatch,
        classifier_source=classifier_source,
        evidence=list(getattr(route_decision, "evidence", []) or []),
        target_workspace=getattr(route_decision, "targetWorkspace", None),
    )


# --------------------------------------------------------------------------
# Capability detection — message → CapabilityId
# --------------------------------------------------------------------------

# Order matters: more specific phrases first so a "storyboard frame" isn't
# collapsed to "image.generate". Patterns are case-insensitive.
#
# Spatial Map + Atlas + ERS + Scene Creator capability patterns (m413) run
# EARLY so a precise "generate the ers" / "create an atlas shot" is not
# collapsed into a generic image.generate. They map to the frozen capability
# ids registered in ``capabilities.registry`` (atlas.generate, ers.generate,
# scene.generate).
_CAPABILITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # --- Production-orchestrator milestone: conversational production commands ---
    # "images from the ERS" / "shots using the saved cameras" → scene.generate
    (re.compile(r"\b(?:create|generate|make|render)\b.*\bimages?\b.*\bfrom\s+(?:the\s+)?(?:ers|environment\s+reference\s+(?:sheet|package))\b", re.I), "scene.generate"),
    (re.compile(r"\b(?:create|generate|make|render)\b.*\b(?:shots?|images?)\b.*\b(?:using|from|with)\s+(?:the\s+)?(?:[a-z]+\s+)?(?:saved\s+)?cameras?\b", re.I), "scene.generate"),
    # Timeline edits → timeline.add_asset (TOOL capability; curated tools path)
    (re.compile(r"\b(?:put|add|place|move|insert|attach)\b.*\b(?:on|to|into|in|at|onto)\s+(?:the\s+)?timeline\b", re.I), "timeline.add_asset"),
    (re.compile(r"\b(?:timed\s+prompt|prompt\s+clip|prompt\s+track)\b", re.I), "timeline.add_asset"),
    (re.compile(r"\b(?:create|make|add|build|start)\s+(?:a\s+|the\s+|another\s+|next\s+)?batch\b", re.I), "timeline.add_asset"),
    (re.compile(r"\b(?:16\s*:\s*9|21\s*:\s*9|9\s*:\s*16|1\s*:\s*1)\b", re.I), "timeline.add_asset"),

    # --- m413 Spatial Map + Atlas + ERS + Scene Creator (specific first) ---
    # Atlas shot (roofless top-down environment reference) — must precede the
    # generic "shot"/"image" patterns so it wins.
    (re.compile(r"\b(?:create|generate|make|render|build)\b.*\batlas\s+shot\b", re.I), "atlas.generate"),
    (re.compile(r"\broofless\s+(?:shot|map|view)\b", re.I), "atlas.generate"),
    # ERS — environment reference sheet/package. Precedes generic image gen.
    (re.compile(r"\b(?:generate|create|make|build|assemble)\b.*\b(?:ers|environment\s+reference\s+(?:sheet|package|set))\b", re.I), "ers.generate"),
    # Scene Creator shot generation: "generate four shots", "generate N scene
    # shots", "make 3 scene images". Precedes generic image gen + storyboard.
    # Matches the deterministic classifier's coverage: digit OR word-number
    # counts, and the "scene" qualifier with an optional article. A bare
    # "create shots" (no count, no scene qualifier) is intentionally NOT
    # matched here so it falls through to the semantic classifier (preserves
    # the test_phase3_router corpus expectation).
    (re.compile(
        r"\b(?:generate|create|make|render|build)\b\s+"
        r"(?:"
        r"(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a\s+couple\s+of|a\s+few)\s+)"
        r"(?:scene\s+)?(?:shots?|images?|scene\s+images?)"
        r"|"
        r"(?:an?\s+|some\s+)?scene\s+(?:shots?|images?)"
        r")\b",
        re.I,
    ), "scene.generate"),
    # "regenerate shot N" — targeted scene shot regen (not storyboard frame).
    (re.compile(r"\b(?:regenerate|redo|re-?render)\s+(?:shot|frame)\s*\d+\b", re.I), "scene.generate"),
    # Storyboard variants
    (re.compile(r"\bstory ?board\b", re.I), "storyboard.generate"),
    (re.compile(r"\bregenerate (?:a |the )?(?:story ?board )?frame\b", re.I), "storyboard.regenerate_frame"),
    # Character candidates / casting
    (re.compile(r"\b(?:generate|create|make)\b.*\bcandidates?\b", re.I), "character.generate_candidates"),
    (re.compile(r"\bcasting (?:image|candidates?)\b", re.I), "character.generate_candidates"),
    # Image edits before plain generation (edit/mask/inpaint/outpaint)
    (re.compile(r"\b(?:edit|inpaint|outpaint|mask|modify|touch up|revise)\b.*\bimage\b", re.I), "image.edit"),
    (re.compile(r"\bimage\b.*\b(?:edit|inpaint|outpaint|mask|touch up)\b", re.I), "image.edit"),
    # Image batch before single image (batch / several / N images)
    (re.compile(r"\b(?:generate|create|make)\b.*\b(?:batch|several|\d+\s*images|\d+\s*variations)\b", re.I), "image.generate_batch"),
    # Voice generation
    (re.compile(r"\b(?:generate|create|make|render)\b.*\bvoice\b", re.I), "voice.generate"),
    (re.compile(r"\bvoice (?:clip|segment|audio|take)\b", re.I), "voice.generate"),
    # Image generation — "image of [character]", "generate/render an image"
    (re.compile(r"\bimage of\b", re.I), "image.generate"),
    (re.compile(r"\b(?:generate|render|create|make) (?:a |an |some )?image\b", re.I), "image.generate"),
    (re.compile(r"\b(?:portrait|key art|concept art|visual)\b", re.I), "image.generate"),
    # Library
    (re.compile(r"\bsave (?:this|that|the)?\s*(?:asset|image|frame|clip)?\s*to (?:the )?library\b", re.I), "library.save"),
    (re.compile(r"\bcreate (?:a )?collection\b", re.I), "library.group"),
    (re.compile(r"\badd (?:to|into) (?:a )?collection\b", re.I), "library.assign"),
    # Timeline placement
    (re.compile(r"\bplace (?:this|that|the)?\s*(?:asset|image|frame|clip)?\s*on (?:the )?timeline\b", re.I), "timeline.add_asset"),
    (re.compile(r"\badd (?:audio|voice|music)\s*(?:asset|clip|segment)?\s*to (?:the )?timeline\b", re.I), "timeline.add_audio"),
    # Script editing (proposal-style)
    (re.compile(r"\b(?:edit|rewrite|revise|change|update)\b.*\bscript\b", re.I), "script.propose_edit"),
    (re.compile(r"\bscript (?:edit|rewrite|revise)\b", re.I), "script.propose_edit"),
    # Story refinement
    (re.compile(r"\b(?:refine|polish|tighten|improve)\b.*\b(?:story|logline|synopsis)\b", re.I), "story.refine"),
    # Approve / assign references
    (re.compile(r"\b(?:approve|accept|use|assign)\b.*\b(?:casting|reference|candidate)\b", re.I), "character.assign_reference"),
    (re.compile(r"\bassign voice\b", re.I), "voice.assign"),
)

# Action-verb foundation intents that imply execution when the deterministic
# classifier didn't already catch them. See spec §5 (EXECUTION branch).
_EXECUTION_FOUNDATION_INTENTS: frozenset[str] = frozenset(
    {
        "REQUEST_GENERATION",
        "REQUEST_ACTION",
        "REQUEST_EDIT",
    }
)

# Foundation intents that are conversational / analytical (not executable).
_CONVERSATIONAL_FOUNDATION_INTENTS: frozenset[str] = frozenset(
    {
        "INFORM",
        "EXPLAIN_PROJECT",
        "BRAINSTORM",
        "REQUEST_FEEDBACK",
        "REQUEST_PLAN",
        "REQUEST_RESEARCH",
        "REQUEST_REVIEW",
        "SEEK_REASSURANCE",
        "SET_PREFERENCE",
        "PAUSE_ACTION",
        "CONTINUE_PREVIOUS_WORK",
        "CORRECT_ASSISTANT",
        "EXPRESS_DISSATISFACTION",
        "UNKNOWN",
    }
)

# Deterministic RouteActionClass values that are conversational/analytical.
_CONVERSATIONAL_ACTIONS: frozenset[str] = frozenset(
    {"DISCUSS", "NAVIGATE", "READ_INSPECT", "CLARIFY", "AMBIGUOUS", "UNKNOWN"}
)
_ANALYTICAL_ACTIONS: frozenset[str] = frozenset({"READ_INSPECT"})
_PROPOSAL_ACTIONS: frozenset[str] = frozenset({"MODIFY_KNOWLEDGE", "PROPOSE_CREATIVE_CHANGE"})


def _resolve_capability(message: str) -> tuple[str, list[str]]:
    """Resolve a capability ID + curated tool_ids from the message text.

    Returns ("", []) when no capability pattern matches.
    """
    from ..capabilities.registry import get_capability

    for pattern, capability_id in _CAPABILITY_PATTERNS:
        if pattern.search(message):
            cap = get_capability(capability_id)
            if cap is not None:
                return capability_id, list(cap.tool_ids)
            return capability_id, []
    return "", []


def classify_intent(
    message: str,
    context: Optional[dict[str, Any]] = None,
    *,
    route_decision: Optional[Any] = None,
    foundation_intent: Optional[Any] = None,
) -> UnifiedIntent:
    """Classify one user turn into a single `UnifiedIntent`.

    Wraps the existing Phase 3 `classify_deterministic()` (passed in as
    `route_decision` by the orchestrator) and the foundation
    `analyze_intent()` (passed in as `foundation_intent`) and maps them onto
    the unified vocabulary. Does NOT replace or rewrite either classifier.

    Mapping rules (spec §5):
    - EXECUTE_PRODUCTION / EXECUTE_GENERATE high-confidence → EXECUTION +
      DETERMINISTIC, capability resolved from message.
    - Foundation REQUEST_GENERATION / REQUEST_ACTION / REQUEST_EDIT the
      deterministic classifier missed → EXECUTION + CURATED_TOOLS (lower
      confidence), capability best-guessed from message.
    - READ_INSPECT / explain-questions / brainstorming → ANALYSIS + LLM_ONLY.
    - DISCUSS / NAVIGATE → CONVERSATION + LLM_ONLY.
    - MODIFY_KNOWLEDGE / PROPOSE_CREATIVE_CHANGE → PROPOSAL + LLM_ONLY.
    - CLARIFY / AMBIGUOUS → CLARIFICATION_REQUIRED + LLM_ONLY.
    """
    context = context or {}
    evidence: list[str] = []

    action_value = "UNKNOWN"
    deterministic_confidence = 0.0
    classifier_source = "deterministic"
    if route_decision is not None:
        action = getattr(route_decision, "actionClass", None)
        action_value = action.value if action else "UNKNOWN"
        deterministic_confidence = float(getattr(route_decision, "confidence", 0.0) or 0.0)
        classifier_source = getattr(route_decision, "classifierSource", "deterministic")
        evidence.extend(list(getattr(route_decision, "evidence", []) or []))

    foundation_value = "UNKNOWN"
    foundation_confidence = 0.0
    if foundation_intent is not None:
        primary = getattr(foundation_intent, "primary_intent", None)
        foundation_value = primary.value if primary else "UNKNOWN"
        foundation_confidence = float(getattr(foundation_intent, "confidence", 0.0) or 0.0)
        spans = getattr(foundation_intent, "evidence_spans", None) or []
        for span in spans:
            if span and span not in evidence:
                evidence.append(span)

    # 1. High-confidence deterministic execution → EXECUTION + DETERMINISTIC.
    if action_value in {"EXECUTE_PRODUCTION"} and deterministic_confidence >= 0.7:
        capability_id, tool_ids = _resolve_capability(message)
        return UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability=capability_id,
            confidence=deterministic_confidence,
            dispatch=DispatchStrategy.DETERMINISTIC if capability_id else DispatchStrategy.CURATED_TOOLS,
            classifier_source=classifier_source,
            evidence=evidence or ["Matched deterministic execution pattern"],
            curated_tool_ids=tool_ids,
        )

    # 2. Foundation action intent that the deterministic classifier missed.
    if (
        foundation_value in _EXECUTION_FOUNDATION_INTENTS
        and action_value not in {"EXECUTE_PRODUCTION"}
    ):
        capability_id, tool_ids = _resolve_capability(message)
        # Lower confidence — the LLM should still see tools (curated catalog).
        confidence = max(0.45, min(foundation_confidence, 0.65))
        return UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability=capability_id,
            confidence=confidence,
            dispatch=DispatchStrategy.CURATED_TOOLS,
            classifier_source="deterministic",
            evidence=evidence or [f"Foundation intent {foundation_value}"],
            curated_tool_ids=tool_ids,
        )

    # 3. Proposal-class (modify knowledge / propose creative change).
    if action_value in _PROPOSAL_ACTIONS:
        return UnifiedIntent(
            intent=UnifiedIntentKind.PROPOSAL,
            confidence=deterministic_confidence or foundation_confidence or 0.6,
            dispatch=DispatchStrategy.LLM_ONLY,
            classifier_source=classifier_source,
            evidence=evidence,
            target_workspace=getattr(route_decision, "targetWorkspace", None) if route_decision else None,
        )

    # 4. Clarification / ambiguity.
    if action_value in {"CLARIFY", "AMBIGUOUS"}:
        return UnifiedIntent(
            intent=UnifiedIntentKind.CLARIFICATION_REQUIRED,
            confidence=deterministic_confidence or 0.6,
            dispatch=DispatchStrategy.LLM_ONLY,
            classifier_source=classifier_source,
            evidence=evidence,
            requires_clarification=True,
            clarification_question=(getattr(route_decision, "clarificationOptions", None) or [""])[0]
            if route_decision and getattr(route_decision, "clarificationOptions", None)
            else "",
        )

    # 5. Analytical (READ_INSPECT / explain questions).
    if action_value in _ANALYTICAL_ACTIONS or foundation_value in {"REQUEST_RESEARCH", "REQUEST_REVIEW"}:
        return UnifiedIntent(
            intent=UnifiedIntentKind.ANALYSIS,
            confidence=deterministic_confidence or foundation_confidence or 0.7,
            dispatch=DispatchStrategy.LLM_ONLY,
            classifier_source=classifier_source,
            evidence=evidence,
            target_workspace=getattr(route_decision, "targetWorkspace", None) if route_decision else None,
        )

    # 6. Conversational default.
    return UnifiedIntent(
        intent=UnifiedIntentKind.CONVERSATION,
        confidence=deterministic_confidence or foundation_confidence or 0.5,
        dispatch=DispatchStrategy.LLM_ONLY,
        classifier_source=classifier_source,
        evidence=evidence,
        target_workspace=getattr(route_decision, "targetWorkspace", None) if route_decision else None,
    )
