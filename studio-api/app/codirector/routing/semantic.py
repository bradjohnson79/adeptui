"""Semantic/Model fallback classifier — §9 of the Phase 3 router contract.

Resolves low-confidence deterministic routes by calling the configured LLM
provider for structured JSON classification.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from app.codirector.providers.base import ChatRequest
from app.codirector.routing.contracts import RouteActionClass, RouteDecision
from app.codirector.service import get_provider

SYSTEM_PROMPT = """You are a route classifier. Your job is to classify a user message into one of the following action classes.

Available action classes:
- DISCUSS: conversation, feedback, brainstorming — zero writes
- NAVIGATE: open/show/switch to workspace — Verified Operator lane
- READ_INSPECT: query data/list/inspect — zero writes
- MODIFY_KNOWLEDGE: wiki/bible edit — proposal/approval
- PROPOSE_CREATIVE_CHANGE: creative mutation — proposal/approval
- EXECUTE_PRODUCTION: destructive/execution — proposal/approval + safety
- APPROVE: accept proposal — ProposalService.approve
- REJECT: reject proposal — ProposalService.reject
- CLARIFY: specific ambiguity question — zero writes
- AMBIGUOUS: cannot resolve — zero writes
- UNKNOWN: fallback — zero writes

Respond with a JSON object only (no markdown, no explanation) with these fields:
- actionClass: string, one of the action classes above
- target: string or null, the specific workspace/tool/entity
- confidence: float between 0.0 and 1.0
- ambiguity: list of strings or null, what is ambiguous
- clarificationOptions: list of strings or null, options to offer the user
- destructive: boolean, whether this action is destructive
- writeAllowed: boolean, whether this action writes data"""


def _is_consequential(decision: RouteDecision) -> bool:
    """Check if an action is consequential per contract §4."""
    if decision.actionClass in (RouteActionClass.EXECUTE_PRODUCTION, RouteActionClass.MODIFY_KNOWLEDGE):
        return True
    if decision.actionClass == RouteActionClass.NAVIGATE and decision.destructive:
        return True
    return False


def validate_semantic_response(raw: str) -> Optional[RouteDecision]:
    """Parse and validate the model's JSON response."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    action_class_str = data.get("actionClass")
    if not isinstance(action_class_str, str):
        return None

    try:
        action_class = RouteActionClass(action_class_str)
    except ValueError:
        return None

    confidence = data.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        return None

    destructive = bool(data.get("destructive", False))
    target = data.get("target")
    if target is not None and not isinstance(target, str):
        return None

    if destructive and (not target or not isinstance(target, str) or not target.strip()):
        return None

    write_allowed = bool(data.get("writeAllowed", False))
    ambiguity = data.get("ambiguity")
    if ambiguity is not None and (not isinstance(ambiguity, list) or not all(isinstance(a, str) for a in ambiguity)):
        ambiguity = None
    clarification_options = data.get("clarificationOptions")
    if clarification_options is not None and (not isinstance(clarification_options, list) or not all(isinstance(c, str) for c in clarification_options)):
        clarification_options = None

    return RouteDecision(
        actionClass=action_class,
        target=target if isinstance(target, str) and target.strip() else None,
        confidence=float(confidence),
        ambiguity=ambiguity,
        clarificationOptions=clarification_options,
        destructive=destructive,
        writeAllowed=write_allowed,
        classifierSource="semantic",
    )


async def classify_semantic(
    message: str,
    *,
    derived_stage: Optional[str] = None,
    conversation_focus: Optional[str] = None,
    active_workspace: Optional[str] = None,
    available_action_classes: Optional[list[str]] = None,
    available_targets: Optional[list[str]] = None,
    stage_evidence: Optional[list[dict]] = None,
    recent_actions: Optional[list[str]] = None,
) -> Optional[RouteDecision]:
    """Classify the message using the configured LLM provider.

    Returns a RouteDecision with classifierSource='semantic', or None
    if the provider is unavailable, times out, or returns invalid output.
    """
    try:
        provider = get_provider()
    except Exception:
        return None

    targets_hint = ""
    if available_targets:
        targets_hint = f"\nAvailable targets: {', '.join(available_targets)}"

    actions_hint = ""
    if available_action_classes:
        actions_hint = f"\nAvailable action classes: {', '.join(available_action_classes)}"

    user_content = (
        f"Message: {message}\n"
        f"Derived stage: {derived_stage or 'unknown'}\n"
        f"Conversation focus: {conversation_focus or 'unknown'}\n"
        f"Active workspace: {active_workspace or 'unknown'}"
        f"{targets_hint}"
        f"{actions_hint}"
        "\n\nRespond with JSON only."
    )

    request_id = f"sem-classify-{uuid.uuid4().hex[:12]}"
    chat_request = ChatRequest(
        request_id=request_id,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        model_id=None,
        temperature=0.1,
    )

    try:
        result = await provider.generate(chat_request)
    except Exception:
        return None

    reply = result.reply.strip()
    if not reply:
        return None

    return validate_semantic_response(reply)


async def route_with_semantic_fallback(
    message: str,
    *,
    deterministic_result: Optional[RouteDecision],
    context: dict[str, Any],
) -> RouteDecision:
    """Apply the confidence zone rules from contract §4.

    - deterministic confidence >= 0.85 -> route directly
    - deterministic confidence 0.70-0.85 + non-consequential -> route directly
    - deterministic confidence 0.70-0.85 + consequential -> semantic validation
    - deterministic confidence < 0.70 or None -> run semantic classifier
    - semantic still low confidence -> CLARIFY/AMBIGUOUS
    - semantic None -> return UNKNOWN with confidence 0.0
    """
    if deterministic_result is not None and deterministic_result.confidence >= 0.85:
        return deterministic_result

    if deterministic_result is not None and 0.70 <= deterministic_result.confidence < 0.85:
        if not _is_consequential(deterministic_result):
            return deterministic_result
        semantic = await classify_semantic(
            message,
            derived_stage=context.get("derived_stage"),
            conversation_focus=context.get("conversation_focus"),
            active_workspace=context.get("active_workspace"),
            available_action_classes=context.get("available_action_classes"),
            available_targets=context.get("available_targets"),
            stage_evidence=context.get("stage_evidence"),
            recent_actions=context.get("recent_actions"),
        )
        if semantic is not None and semantic.confidence >= 0.85:
            return semantic
        return deterministic_result

    semantic = await classify_semantic(
        message,
        derived_stage=context.get("derived_stage"),
        conversation_focus=context.get("conversation_focus"),
        active_workspace=context.get("active_workspace"),
        available_action_classes=context.get("available_action_classes"),
        available_targets=context.get("available_targets"),
        stage_evidence=context.get("stage_evidence"),
        recent_actions=context.get("recent_actions"),
    )

    if semantic is None:
        return RouteDecision(
            actionClass=RouteActionClass.UNKNOWN,
            target=None,
            confidence=0.0,
            writeAllowed=False,
            classifierSource="semantic",
        )

    if semantic.confidence >= 0.85:
        return semantic

    if semantic.confidence >= 0.70 and not _is_consequential(semantic):
        return semantic

    return RouteDecision(
        actionClass=RouteActionClass.CLARIFY,
        target=None,
        confidence=semantic.confidence,
        ambiguity=semantic.ambiguity or ["Could not determine action with sufficient confidence"],
        clarificationOptions=semantic.clarificationOptions or None,
        writeAllowed=False,
        classifierSource="semantic",
    )
