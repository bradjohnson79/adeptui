"""Normalize commitment signals from foundation / speech / pending into one enum."""

from __future__ import annotations

import re
from typing import Any

from .contracts import Commitment
from . import reason_codes as RC

# Explicit confirm-execute / authorize-pending (Do it, Go ahead, Generate that, Yes proceed).
_EXPLICIT_RE = re.compile(
    r"(?:"
    r"^\s*(?:yes[,.]?\s+)?(?:please\s+)?(?:go\s+ahead(?:\s+and)?\s+)?"
    r"(?:create|generate|do|run|execute|proceed)\s+(?:it|that|this)\b"
    r"|"
    r"^\s*(?:yes[,.]?\s+)?(?:please\s+)?(?:go\s+ahead|proceed)\b"
    r"|"
    r"\b(?:do\s+it|do\s+that|generate\s+that|create\s+it|render\s+it|build\s+it)\b"
    r"|"
    r"^\s*(?:yes|yep|yeah)[,.]?\s+(?:proceed|confirm|do\s+it|go\s+ahead)\b"
    r"|"
    r"shall i proceed\b"  # mirrored confirm answer context handled by pending
    r")",
    re.I,
)

# Soft commitment that still needs a target brief (Make that better is NOT commitment).
_IMPLIED_COMMIT_RE = re.compile(
    r"\b(?:that\s+works?|that'?s?\s+(?:good|great|perfect)|i\s+like\s+that|let'?s\s+see\s+it)\b",
    re.I,
)


def normalize_commitment(
    *,
    user_message: str = "",
    foundation_intent: Any = None,
    speech_act: str = "",
    pending_execution: Any = None,
    production_action: str = "",
) -> tuple[Commitment, list[str]]:
    """Map trifurcated commitment signals → NONE | IMPLIED | EXPLICIT."""

    text = (user_message or "").strip()
    reasons: list[str] = []

    pending_awaiting = False
    if pending_execution is not None:
        state = str(getattr(pending_execution, "state", "") or "")
        if state.upper() in {"AWAITING_CONFIRMATION", "PENDING", "AWAITING"}:
            pending_awaiting = True
        elif isinstance(pending_execution, dict):
            state = str(pending_execution.get("state") or "")
            pending_awaiting = state.upper() in {"AWAITING_CONFIRMATION", "PENDING", "AWAITING"}

    if pending_awaiting and (_EXPLICIT_RE.search(text) or re.match(r"^\s*(?:yes|yep|yeah|ok|okay|confirm)\b", text, re.I)):
        reasons.append(RC.COMMITMENT_EXPLICIT)
        return Commitment.EXPLICIT, reasons

    if _EXPLICIT_RE.search(text):
        reasons.append(RC.COMMITMENT_EXPLICIT)
        return Commitment.EXPLICIT, reasons

    # Speech confirm-execute patterns already covered by _EXPLICIT_RE.
    speech = (speech_act or "").upper()
    primary = ""
    if foundation_intent is not None:
        pi = getattr(foundation_intent, "primary_intent", None)
        primary = getattr(pi, "value", None) or str(pi or "")

    # Foundation REQUEST_ACTION with commitment-like short utterance → EXPLICIT
    # when it matches authorize-pending language; else IMPLIED if production verb.
    if primary in {"REQUEST_ACTION", "APPROVE"} and len(text.split()) <= 6:
        if re.search(r"\b(?:go\s+ahead|proceed|do\s+it|generate\s+that|make\s+that)\b", text, re.I):
            # "Make that better" is improvement ask, not authorize.
            if re.search(r"\bbetter\b|\bfix\b|\bimprove\b", text, re.I):
                return Commitment.NONE, reasons
            reasons.append(RC.COMMITMENT_EXPLICIT)
            return Commitment.EXPLICIT, reasons

    if speech == "COMMAND" and (production_action or primary in {"REQUEST_GENERATION", "REQUEST_ACTION"}):
        reasons.append(RC.COMMITMENT_IMPLIED)
        return Commitment.IMPLIED, reasons

    if _IMPLIED_COMMIT_RE.search(text):
        reasons.append(RC.COMMITMENT_IMPLIED)
        return Commitment.IMPLIED, reasons

    return Commitment.NONE, reasons
