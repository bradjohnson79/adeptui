"""Compatibility adapter — canonical RouteDecision ↔ legacy IntentKind / ProductionStage / complexity."""

from __future__ import annotations

import warnings
from typing import Literal, Optional

from app.codirector.routing.contracts import RouteActionClass, RouteDecision

# ── reverse map (canonical → legacy IntentKind) per contract §2C ──────────────
_CANONICAL_TO_LEGACY_INTENT: dict[RouteActionClass, str] = {
    RouteActionClass.DISCUSS: "unknown",
    RouteActionClass.NAVIGATE: "unknown",
    RouteActionClass.READ_INSPECT: "review_asset",
    RouteActionClass.MODIFY_KNOWLEDGE: "update_production_bible",
    RouteActionClass.PROPOSE_CREATIVE_CHANGE: "plan_scene",
    RouteActionClass.EXECUTE_PRODUCTION: "execute_project_action",
    RouteActionClass.APPROVE: "unknown",
    RouteActionClass.REJECT: "unknown",
    RouteActionClass.CLARIFY: "unknown",
    RouteActionClass.AMBIGUOUS: "unknown",
    RouteActionClass.UNKNOWN: "unknown",
}

# ── canonical → legacy ProductionStage ────────────────────────────────────────
_CANONICAL_TO_LEGACY_STAGE: dict[RouteActionClass, str] = {
    RouteActionClass.DISCUSS: "development",
    RouteActionClass.NAVIGATE: "project_management",
    RouteActionClass.READ_INSPECT: "project_management",
    RouteActionClass.MODIFY_KNOWLEDGE: "project_management",
    RouteActionClass.PROPOSE_CREATIVE_CHANGE: "preproduction",
    RouteActionClass.EXECUTE_PRODUCTION: "production",
    RouteActionClass.APPROVE: "project_management",
    RouteActionClass.REJECT: "project_management",
    RouteActionClass.CLARIFY: "project_management",
    RouteActionClass.AMBIGUOUS: "project_management",
    RouteActionClass.UNKNOWN: "project_management",
}

# ── canonical → legacy complexity ─────────────────────────────────────────────
_CANONICAL_TO_LEGACY_COMPLEXITY: dict[RouteActionClass, str] = {
    RouteActionClass.DISCUSS: "standard",
    RouteActionClass.NAVIGATE: "simple",
    RouteActionClass.READ_INSPECT: "simple",
    RouteActionClass.MODIFY_KNOWLEDGE: "standard",
    RouteActionClass.PROPOSE_CREATIVE_CHANGE: "standard",
    RouteActionClass.EXECUTE_PRODUCTION: "complex",
    RouteActionClass.APPROVE: "simple",
    RouteActionClass.REJECT: "simple",
    RouteActionClass.CLARIFY: "simple",
    RouteActionClass.AMBIGUOUS: "simple",
    RouteActionClass.UNKNOWN: "standard",
}


def translate_to_legacy_intent_kind(decision: RouteDecision, active: Optional[bool] = False) -> str:
    """Map a canonical RouteDecision to a legacy IntentKind string.

    Parameters
    ----------
    decision : RouteDecision
        The canonical route decision to translate.
    active : bool, optional
        Reserved for future use — not yet implemented.

    Returns
    -------
    str
        A legacy IntentKind literal (e.g. "unknown", "review_asset").
    """
    return _CANONICAL_TO_LEGACY_INTENT[decision.actionClass]


def canonical_to_legacy_production_stage(decision: RouteDecision) -> str:
    """Map a canonical RouteDecision to a legacy ProductionStage string."""
    return _CANONICAL_TO_LEGACY_STAGE[decision.actionClass]


def canonical_to_legacy_complexity(decision: RouteDecision) -> Literal["simple", "standard", "complex"]:
    """Map a canonical RouteDecision to a legacy complexity literal."""
    value = _CANONICAL_TO_LEGACY_COMPLEXITY[decision.actionClass]
    return value  # type: ignore[return-value]


class ActionDecisionMapper:
    """Deprecated — builds a legacy IntentClassification from a RouteDecision.

    Only needed until the dormant specialist path (intelligence/service.py:139)
    is rewired in Phase 7.
    """

    def __init__(self, decision: RouteDecision, route_stage: str = "") -> None:
        warnings.warn(
            "ActionDecisionMapper is deprecated. Use the canonical RouteDecision directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._decision = decision
        self._route_stage = route_stage

    @property
    def primary_intent(self) -> str:
        return translate_to_legacy_intent_kind(self._decision)

    @property
    def production_stage(self) -> str:
        return canonical_to_legacy_production_stage(self._decision)

    @property
    def complexity(self) -> Literal["simple", "standard", "complex"]:
        return canonical_to_legacy_complexity(self._decision)

    @property
    def requires_approval(self) -> bool:
        return self._decision.writeAllowed

    @property
    def needs_clarification(self) -> bool:
        return self._decision.actionClass in (RouteActionClass.CLARIFY, RouteActionClass.AMBIGUOUS)

    @property
    def is_simple_question(self) -> bool:
        return self._decision.actionClass in (RouteActionClass.NAVIGATE, RouteActionClass.READ_INSPECT)
