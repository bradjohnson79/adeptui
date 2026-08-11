"""Deterministic classifier for the Co-Director 2.0 router — §8 of the Phase 3 contract."""

from __future__ import annotations

import re
from typing import Optional

from .contracts import RouteActionClass, RouteDecision


_NEGATION_PATTERN = re.compile(
    r"\b(?:don't|do not|won't|not|never|no|isn't|aren't|didn't|doesn't|can't|cannot|not yet)\b",
    re.I,
)

_NAVIGATE_PATTERN = re.compile(
    r"(?:"
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch|load)\b.*\b(?:"
    r"script writer|timeline|audio studio|voice studio|magi|continuity|"
    r"bible|posecraft|runtime manager|references|characters|casting|"
    r"editor|workspace|studio|panel|view|mode"
    r")"
    r"|"
    r"\b(?:open|show)\s+(?:script|writer|timeline|audio|voice)\b"
    r")",
    re.I,
)

_APPROVE_PATTERN = re.compile(
    r"\b(?:approve|accept(?: this)?|use this|looks good|confirmed|that works|go ahead|sounds? good|perfect"
    r"|proceed|yes|yep|yeah|sure|ok|okay|please proceed|do it|continue|start|approved|alright|let'?s do it"
    r"|that'?s fine|please continue|generate it)\b",
    re.I,
)

# Execution-specific confirmation pattern (spec §4) — affirmative responses that
# resolve a PENDING EXECUTION (not a Wiki/Bible proposal). Checked BEFORE generic
# intent classification so the LLM cannot hijack a confirmation turn (spec §35).
_EXECUTION_CONFIRMATION_PATTERN = re.compile(
    r"\b(?:yes|yep|yeah|sure|ok|okay|please|proceed|go ahead|do it|continue|start|generate it"
    r"|approved|sounds? good|let'?s do it|that'?s fine|alright|please proceed|please continue"
    r"|looks good|confirmed|perfect|that works|that'?ll do)\b",
    re.I,
)

_REJECT_PATTERN = re.compile(
    r"\b(?:reject|decline|don't use|keep mine|keep what I|revert|undo|discard|no[,.] keep|that's? not right|that's? wrong"
    r"|nope|no thanks|don't|stop|cancel|never mind)\b",
    re.I,
)

_READ_INSPECT_PATTERN = re.compile(
    r"\b(?:what|show me|inspect|list|get|find|search|describe|what's in|how many|what are)\b"
    r".*\b(?:scenes?|assets?|characters?|batch(?:es)?|plans?|clips?|tracks?|shots?|versions?|drafts?|"
    r"bible|wiki|locations?|canon|entries?|decisions?|proposals?|jobs?|renders?|images?|videos?|panels?|segments?)\b",
    re.I,
)

_DISCUSS_FEEDBACK_PATTERN = re.compile(
    r"\b(?:be honest|critique|does this work|what's your take|how do you feel about|what do you think)\b",
    re.I,
)

_DISCUSS_CORRECTION_PATTERN = re.compile(
    r"^(?:correction:|actually,\s?|instead,\s?|no[,.] that's wrong|no[,.] that didn't)",
    re.I,
)

_DISCUSS_EXPLAIN_PATTERN = re.compile(
    r"\b(?:I want to tell you|let me explain|before we start|walk you through|"
    r"let me give you|just listen|I'm going to tell)\b",
    re.I,
)

_DISCUSS_COLLABORATE_PATTERN = re.compile(
    r"\b(?:can you help me|let's (?:talk|discuss|work on|think about)|what about)\b",
    re.I,
)

_DISCUSS_OPINION_PATTERN = re.compile(
    r"\bwhat do you think\b|\bhow (?:do|would) you\b.*\b(?:feel|like|approach)\b",
    re.I,
)

_MODIFY_KNOWLEDGE_PATTERN = re.compile(
    r"\b(?:add|update|change|put|save|write|set)\b.*\b(?:"
    r"wiki|summary|bible|canon|knowledge|logline|synopsis|description|premise|tone|genre"
    r")\b",
    re.I,
)

_EXECUTE_DESTRUCTIVE_PATTERN = re.compile(
    r"\b(?:delete|remove|destroy|erase|clear|trash)\b.*\b(?:"
    r"batch|scene|clip|sequence|shot|track|asset|version|plan|block|frame"
    r")\b",
    re.I,
)

_EXECUTE_GENERATE_PATTERN = re.compile(
    r"\b(?:create|generate|render|build|execute|run|queue|start|begin|make)\b.*\b(?:"
    r"scene|shot|clip|batch|plan|sequence|render|image|video|portrait|storyboard|frame|picture|version|variation|alternative"
    r")\b",
    re.I,
)

_DISCUSS_SEEKING_PATTERN = re.compile(
    r"\b(?:think about|opinion|suggest)\b",
    re.I,
)


NAVIGATION_TARGETS: dict[str, str] = {
    "script writer": "script_writer",
    "script": "script_writer",
    "writer": "script_writer",
    "timeline": "timeline",
    "audio studio": "audiostudio",
    "audio": "audiostudio",
    "voice studio": "voicestudio",
    "voice": "voicestudio",
    "magi": "magi",
    "continuity": "continuity",
    "bible": "bible",
    "posecraft": "posecraft",
    "pose craft": "posecraft",
    "runtime manager": "runtime_manager",
    "references": "references",
    "characters": "characters",
    "casting": "casting",
    "editor": "editor",
}

_ENTITY_TOOL_MAP: dict[str, list[str]] = {
    "scene": ["scene.list", "scene.get", "scene.list_characters"],
    "scenes": ["scene.list", "scene.get", "scene.list_characters"],
    "asset": ["asset.list", "asset.get"],
    "assets": ["asset.list", "asset.get"],
    "character": ["character.list", "character.get"],
    "characters": ["character.list", "character.get"],
    "batch": ["batch.list", "batch.get"],
    "plan": ["plan.list", "plan.get"],
    "plans": ["plan.list", "plan.get"],
    "clip": ["clip.list", "clip.get"],
    "clips": ["clip.list", "clip.get"],
    "track": ["track.list", "track.get"],
    "tracks": ["track.list", "track.get"],
    "shot": ["shot.list", "shot.get"],
    "shots": ["shot.list", "shot.get"],
    "version": ["version.list", "version.get"],
    "versions": ["version.list", "version.get"],
    "draft": ["draft.list", "draft.get"],
    "drafts": ["draft.list", "draft.get"],
    "bible": ["bible.list", "bible.get", "bible.search"],
    "wiki": ["bible.list", "bible.search"],
    "location": ["location.list", "location.get"],
    "locations": ["location.list", "location.get"],
    "canon": ["canon.list", "canon.get"],
    "entry": ["entry.list", "entry.get"],
    "entries": ["entry.list", "entry.get"],
    "decision": ["decision.list", "decision.get"],
    "decisions": ["decision.list", "decision.get"],
    "proposal": ["proposal.list", "proposal.get"],
    "proposals": ["proposal.list", "proposal.get"],
    "job": ["job.list", "job.get"],
    "jobs": ["job.list", "job.get"],
    "render": ["render.list", "render.get"],
    "renders": ["render.list", "render.get"],
    "image": ["image.list", "image.get"],
    "images": ["image.list", "image.get"],
    "video": ["video.list", "video.get"],
    "videos": ["video.list", "video.get"],
    "panel": ["panel.list", "panel.get"],
    "panels": ["panel.list", "panel.get"],
    "segment": ["segment.list", "segment.get"],
    "segments": ["segment.list", "segment.get"],
}


def _has_negated_action(message: str) -> bool:
    if not _NEGATION_PATTERN.search(message):
        return False
    action_patterns = [
        _NAVIGATE_PATTERN,
        _APPROVE_PATTERN,
        _REJECT_PATTERN,
        _MODIFY_KNOWLEDGE_PATTERN,
        _EXECUTE_DESTRUCTIVE_PATTERN,
        _EXECUTE_GENERATE_PATTERN,
        _READ_INSPECT_PATTERN,
    ]
    return any(p.search(message) for p in action_patterns)


def is_execution_confirmation(message: str) -> bool:
    """Return True if `message` is an affirmative confirmation of a pending execution.

    Spec §4 + §35: this is checked BEFORE generic intent classification so the LLM
    cannot hijack a confirmation turn. Returns False for negated/reject responses.
    """
    if not message:
        return False
    # "not sure", "don't proceed", "no, don't" etc. are rejections, not confirmations.
    if _NEGATION_PATTERN.search(message):
        return False
    if _REJECT_PATTERN.search(message):
        return False
    return bool(_EXECUTION_CONFIRMATION_PATTERN.search(message))


def is_execution_rejection(message: str) -> bool:
    """Return True if `message` rejects a pending execution."""
    if not message:
        return False
    lower = message.lower().strip()
    # Standalone "no" is a rejection.
    if lower in ("no", "nope", "n", "no.", "no,", "cancel", "stop"):
        return True
    return bool(_REJECT_PATTERN.search(message))


def _extract_navigate_target(
    message: str,
    available_workspaces: Optional[frozenset[str]],
) -> tuple[Optional[str], Optional[str]]:
    lower = message.lower()
    for name, ws_id in sorted(NAVIGATION_TARGETS.items(), key=lambda x: -len(x[0])):
        if name in lower:
            if available_workspaces is not None and ws_id not in available_workspaces:
                return None, ws_id
            return ws_id, ws_id
    return None, None


def _detect_read_entity(message: str) -> Optional[list[str]]:
    lower = message.lower()
    for entity, tool_ids in sorted(_ENTITY_TOOL_MAP.items(), key=lambda x: -len(x[0])):
        if entity in lower:
            return tool_ids
    return None


def _is_discussion_seeking(message: str) -> bool:
    return bool(_DISCUSS_SEEKING_PATTERN.search(message))


def classify_deterministic(
    message: str,
    *,
    active_workspace: Optional[str] = None,
    derived_stage: Optional[str] = None,
    pending_proposal_ids: Optional[list[str]] = None,
    available_workspaces: Optional[frozenset[str]] = None,
) -> Optional[RouteDecision]:
    """Classify a user message using deterministic patterns.

    Returns a RouteDecision for obvious matches, or None to fall back
    to the semantic classifier.
    """

    # 1. Negation detection (run FIRST — §8.7)
    if _has_negated_action(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.75,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Negation detected — action intent negated by user"],
        )

    # 2. NAVIGATE (§8.1)
    nav_match = _NAVIGATE_PATTERN.search(message)
    if nav_match:
        target_ws, unresolved_target = _extract_navigate_target(message, available_workspaces)
        confidence = 0.92
        target = target_ws if target_ws is not None else unresolved_target
        evidence_text = f"matched pattern: {nav_match.group().strip()}"
        evidence = [evidence_text]
        if unresolved_target is not None and target_ws is None:
            confidence = 0.85
            evidence.append(
                f"target workspace '{unresolved_target}' not in available workspaces"
            )
        return RouteDecision(
            actionClass=RouteActionClass.NAVIGATE,
            target=target,
            targetWorkspace=target,
            confidence=confidence,
            executionLane="operator",
            writeAllowed=False,
            destructive=False,
            evidence=evidence,
        )

    # 3. APPROVE (§8.4)
    if _APPROVE_PATTERN.search(message):
        if not pending_proposal_ids:
            return RouteDecision(
                actionClass=RouteActionClass.CLARIFY,
                target=None,
                confidence=0.9,
                executionLane="discuss",
                writeAllowed=False,
                destructive=False,
                evidence=["No pending proposal to approve — returning CLARIFY"],
            )
        return RouteDecision(
            actionClass=RouteActionClass.APPROVE,
            target=pending_proposal_ids[0],
            confidence=0.9,
            executionLane="approve",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched approve pattern with pending proposals"],
        )

    # 4. REJECT (§8.4)
    if _REJECT_PATTERN.search(message):
        if not pending_proposal_ids:
            return RouteDecision(
                actionClass=RouteActionClass.CLARIFY,
                target=None,
                confidence=0.9,
                executionLane="discuss",
                writeAllowed=False,
                destructive=False,
                evidence=["No pending proposal to reject — returning CLARIFY"],
            )
        return RouteDecision(
            actionClass=RouteActionClass.REJECT,
            target=pending_proposal_ids[0],
            confidence=0.88,
            executionLane="reject",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched reject pattern with pending proposals"],
        )

    # 5. READ_INSPECT (§8.2)
    if _READ_INSPECT_PATTERN.search(message) and not _is_discussion_seeking(message):
        entity_tools = _detect_read_entity(message)
        return RouteDecision(
            actionClass=RouteActionClass.READ_INSPECT,
            confidence=0.87,
            executionLane="read",
            writeAllowed=False,
            destructive=False,
            targetToolIds=entity_tools,
            evidence=["Matched read/inspect pattern"],
        )

    # 6. DISCUSS (§8.3) — ordered sub-patterns
    if _DISCUSS_FEEDBACK_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.86,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched feedback/critique discuss pattern"],
        )
    if _DISCUSS_CORRECTION_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.88,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched correction discuss pattern"],
        )
    if _DISCUSS_EXPLAIN_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.88,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched explain/listen discuss pattern"],
        )
    if _DISCUSS_COLLABORATE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.82,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched collaborate discuss pattern"],
        )
    if _DISCUSS_OPINION_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.86,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched opinion-seeking discuss pattern"],
        )

    # 7. MODIFY_KNOWLEDGE (§8.5)
    if _MODIFY_KNOWLEDGE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.MODIFY_KNOWLEDGE,
            confidence=0.83,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched modify knowledge pattern"],
        )

    # 8. EXECUTE_PRODUCTION (§8.6)
    if _EXECUTE_DESTRUCTIVE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=True,
            evidence=["Matched destructive production pattern"],
        )
    if _EXECUTE_GENERATE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched generate production pattern"],
        )

    # 9. No deterministic match — fall back to semantic classifier
    return None
