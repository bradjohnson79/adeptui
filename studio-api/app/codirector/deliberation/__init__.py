"""Co-Director Advanced Deliberation — frozen contracts + decision builder.

Converges existing classifiers into one DeliberationDecision (TALK|ASK|ACT|STOP).
Does not replace grounding, generation_memory, image_route STRICT, or dispatcher.
"""

from __future__ import annotations

from .contracts import (
    SCHEMA_VERSION,
    CapabilityCandidate,
    Commitment,
    DeliberationDecision,
    DeliberationMode,
    ExecutionPlanStub,
    ReferentialResolution,
    ResponsePlan,
    RiskAssessment,
    RiskLevel,
    RuntimePrecheck,
    SufficiencyResult,
    TalkAskAct,
)
from .commitment import normalize_commitment
from .risk import assess_risk
from .service import build_decision, resolve_effort_mode, resolve_referential_structure
from . import reason_codes

__all__ = [
    "SCHEMA_VERSION",
    "CapabilityCandidate",
    "Commitment",
    "DeliberationDecision",
    "DeliberationMode",
    "ExecutionPlanStub",
    "ReferentialResolution",
    "ResponsePlan",
    "RiskAssessment",
    "RiskLevel",
    "RuntimePrecheck",
    "SufficiencyResult",
    "TalkAskAct",
    "assess_risk",
    "build_decision",
    "resolve_effort_mode",
    "normalize_commitment",
    "reason_codes",
    "resolve_referential_structure",
]
