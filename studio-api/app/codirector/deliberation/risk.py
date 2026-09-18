"""Destructive / risk assessment for deliberation (unified risk → ASK)."""

from __future__ import annotations

import re

from .contracts import RiskAssessment, RiskLevel
from . import reason_codes as RC

_DESTRUCTIVE_RE = re.compile(
    r"\b(?:"
    r"delete\s+(?:this\s+|the\s+|all\s+|every\s+)?"
    r"(?:scene|scenes|timeline\s+batches?|batches?|clips?|shots?|project|character|asset|assets|"
    r"track|tracks|segment|segments|panel|panels|canon|bible\s+entr(?:y|ies)|record|records)"
    r"|"
    r"remove\s+(?:all|every)\s+(?:timeline\s+)?(?:batches?|scenes?|clips?|shots?)"
    r"|"
    r"wipe\s+(?:the\s+)?(?:timeline|project|scene)"
    r"|"
    r"destroy\s+(?:this\s+|the\s+)?(?:scene|project|timeline)"
    r")\b",
    re.I,
)

_REVERSIBLE_MUTATION_RE = re.compile(
    r"\b(?:remove|clear|reset|undo)\b.+\b(?:clip|shot|marker|tag)\b",
    re.I,
)


def assess_risk(*, user_message: str, capability_id: str = "") -> RiskAssessment:
    text = user_message or ""
    cap = (capability_id or "").lower()

    if _DESTRUCTIVE_RE.search(text) or "delete" in cap or "destroy" in cap:
        return RiskAssessment(
            level=RiskLevel.DESTRUCTIVE,
            confirmationRequired=True,
            destructive=True,
            confirmationQuestion=(
                "This will permanently delete production data. "
                "Confirm that you want me to proceed?"
            ),
            reasonCodes=[RC.DESTRUCTIVE_CONFIRMATION_REQUIRED, RC.RISK_CONFIRMATION_REQUIRED],
        )

    if _REVERSIBLE_MUTATION_RE.search(text):
        return RiskAssessment(
            level=RiskLevel.REVERSIBLE,
            confirmationRequired=False,
            destructive=False,
            reasonCodes=[],
        )

    return RiskAssessment(level=RiskLevel.SAFE)
