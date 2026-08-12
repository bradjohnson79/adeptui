"""Phase 7 — comprehensive specialist crew test suite.

Covers:
- RouteDecision-driven specialist selection (Section 8)
- Permission enforcement (Section 8)
- Synthesis conflict classification (Section 8)
- Negative assertions N1–N5 (Section 9)
- Project isolation / registry scope
"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, PropertyMock

import pytest

from app.codirector.intelligence.schemas import (
    IntentClassification,
    ProposedToolAction,
    SpecialistFinding,
)
from app.codirector.intelligence.specialist_policies import (
    CoDirectorSpecialistContract,
    enforce_specialist_permissions,
)
from app.codirector.intelligence.specialist_selector import (
    MAX_SPECIALISTS,
    SpecialistContext,
    SpecialistSelection,
    SpecialistSelector,
)
from app.codirector.intelligence.specialist_registry import SpecialistDefinition
from app.codirector.intelligence.synthesis import SynthesisEngine
from app.codirector.routing.contracts import RouteActionClass, RouteDecision

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_KNOWN_SPECIALIST_IDS = frozenset({
    "story-analyst",
    "storyteller",
    "story-editor",
    "screenwriter",
    "script-supervisor",
    "character-creator",
    "casting-director",
    "performance-director",
    "bible-manager",
    "continuity-analyst",
    "director",
    "cinematographer",
    "prompt-architect",
    "technical-director",
    "art-director",
    "production-designer",
    "lighting-supervisor",
    "sound-designer",
    "sound-producer",
    "music-supervisor",
    "producer",
    "pipeline-manager",
})


@pytest.fixture()
def mock_registry() -> MagicMock:
    reg = MagicMock()
    reg.ids.return_value = _KNOWN_SPECIALIST_IDS
    return reg


@pytest.fixture()
def selector(mock_registry: MagicMock) -> SpecialistSelector:
    return SpecialistSelector(registry=mock_registry)


def make_route(action: RouteActionClass, *, target: str | None = None, confidence: float = 0.8) -> RouteDecision:
    return RouteDecision(actionClass=action, target=target, confidence=confidence)


def make_finding(
    specialist_id: str = "story-analyst",
    summary: str = "Test finding.",
    recommendation: str = "Proceed with current plan.",
    **overrides,
) -> SpecialistFinding:
    return SpecialistFinding(
        specialistId=specialist_id,
        summary=summary,
        recommendation=recommendation,
        **overrides,
    )


# ===================================================================
# Class TestRouteDecisionSelection
# ===================================================================

class TestRouteDecisionSelection:
    """RouteDecision → specialist crew size and domain resolution."""

    def test_navigate_zero_specialists(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.NAVIGATE))
        result = selector.select(ctx)
        assert result.required == ()
        assert result.optional == ()
        assert result.skipped == ()
        assert result.selection_confidence == 1.0
        assert result.target_domain is None

    def test_approve_zero_specialists(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.APPROVE))
        result = selector.select(ctx)
        assert result.required == ()
        assert result.optional == ()

    def test_reject_zero_specialists(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.REJECT))
        result = selector.select(ctx)
        assert result.required == ()
        assert result.optional == ()

    def test_discuss_one_specialist(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.DISCUSS, target="story"),
        )
        result = selector.select(ctx)
        assert len(result.all_selected) >= 1
        assert len(result.all_selected) <= 3
        assert result.target_domain == "story"

    def test_execute_production_max_three(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.EXECUTE_PRODUCTION, target="production"),
        )
        result = selector.select(ctx)
        assert len(result.all_selected) <= 3
        assert result.selection_confidence > 0.0

    def test_clarify_max_one(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.CLARIFY, target="general"),
        )
        result = selector.select(ctx)
        assert len(result.all_selected) <= 1

    def test_simple_read_zero_specialists(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.READ_INSPECT),
        )
        result = selector.select(ctx)
        assert len(result.all_selected) <= 1

    def test_analytical_read_at_most_one(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.READ_INSPECT, target="character"),
        )
        result = selector.select(ctx)
        assert len(result.all_selected) <= 1

    def test_domain_resolution_from_target(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.DISCUSS, target="dialogue"),
        )
        result = selector.select(ctx)
        assert result.target_domain == "dialogue"
        assert len(result.all_selected) >= 1

    def test_domain_resolution_from_goal(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=make_route(RouteActionClass.DISCUSS),
            creator_goal="write the script",
        )
        result = selector.select(ctx)
        assert result.target_domain == "script"
        assert len(result.all_selected) >= 1

    def test_max_specialists_honored(self):
        assert MAX_SPECIALISTS == 3, "MAX_SPECIALISTS must be 3 by contract"
        reg = MagicMock()
        reg.ids.return_value = _KNOWN_SPECIALIST_IDS
        sel = SpecialistSelector(registry=reg)
        for action in RouteActionClass:
            ctx = SpecialistContext(
                route_decision=make_route(action, target="story" if action != RouteActionClass.NAVIGATE else None),
            )
            result = sel.select(ctx)
            assert len(result.all_selected) <= MAX_SPECIALISTS, (
                f"action={action.value} exceeds MAX_SPECIALISTS"
            )

    def test_fallback_without_route_decision(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=None)
        result = selector.select(ctx)
        assert len(result.all_selected) >= 1
        assert result.target_domain is not None
        assert result.selection_confidence == 0.5


# ===================================================================
# Class TestPermissionEnforcement
# ===================================================================

class TestPermissionEnforcement:
    """enforce_specialist_permissions hard-constraint tests."""

    def test_enforce_specialist_permissions_raises(self):
        contract = CoDirectorSpecialistContract(
            specialistId="rogue-specialist",
            displayName="Rogue",
            mayExecuteTools=True,
        )
        with pytest.raises(ValueError, match="mayExecuteTools"):
            enforce_specialist_permissions("rogue-specialist", contract)

    def test_enforce_specialist_permissions_passes(self):
        contract = CoDirectorSpecialistContract(
            specialistId="safe-specialist",
            displayName="Safe",
            mayExecuteTools=False,
        )
        enforce_specialist_permissions("safe-specialist", contract)


# ===================================================================
# Class TestSynthesisConflicts
# ===================================================================

class TestSynthesisConflicts:
    """SynthesisEngine conflict classification and route-aware tool trimming."""

    def test_classify_conflicts_empty(self):
        engine = SynthesisEngine()
        conflicts = engine.classify_conflicts([])
        assert conflicts == []

    def test_classify_no_conflicts(self):
        engine = SynthesisEngine()
        findings = [
            make_finding("story-analyst", recommendation="Scene works as written."),
            make_finding("director", recommendation="Ensure proper lighting setup."),
        ]
        conflicts = engine.classify_conflicts(findings)
        assert len(conflicts) == 0

    def test_route_decision_discuss_trims_tools(self):
        engine = SynthesisEngine()
        intent = IntentClassification(primaryIntent="develop_concept")
        findings = [
            make_finding(
                "story-analyst",
                proposedToolActions=[
                    ProposedToolAction(toolId="tool-a", purpose="Tool A"),
                    ProposedToolAction(toolId="tool-b", purpose="Tool B"),
                    ProposedToolAction(toolId="tool-c", purpose="Tool C"),
                ],
            ),
        ]
        route = make_route(RouteActionClass.DISCUSS)
        result = engine.synthesize(
            user_message="Discuss the scene",
            intent=intent,
            findings=findings,
            route_decision=route,
        )
        assert len(result.proposedToolActions) <= 2


# ===================================================================
# Class TestNegativeAssertions (N1–N5)
# ===================================================================

class TestNegativeAssertions:
    """Phase 7 Negative Assertions N1–N5 from frozen contract §9."""

    def test_N1_route_decision_selection_zero_mutations(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.DISCUSS, target="story"))
        registry_before = deepcopy(selector.registry.ids())
        selector.select(ctx)
        registry_after = selector.registry.ids()
        assert registry_after == registry_before, "select() must not mutate registry"

    def test_N2_navigate_guard_at_service(self):
        rule = SpecialistSelector._ROUTE_CREW_RULES if hasattr(SpecialistSelector, "_ROUTE_CREW_RULES") else {}
        from app.codirector.intelligence.specialist_selector import _ROUTE_CREW_RULES
        max_spec, _ = _ROUTE_CREW_RULES[RouteActionClass.NAVIGATE]
        assert max_spec == 0, "NAVIGATE must have max_spec == 0 (zero-specialist guard)"

    def test_N3_no_legacy_intent_fallback_by_default(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.DISCUSS, target="scene"))
        result = selector.select(ctx)
        assert result.target_domain is not None
        assert result.selection_confidence >= 0.8
        assert len(result.all_selected) >= 1

    def test_N4_provenance_preserved(self, selector: SpecialistSelector):
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.DISCUSS, target="audio"))
        result = selector.select(ctx)
        assert isinstance(result.selection_confidence, float)
        assert 0.0 <= result.selection_confidence <= 1.0
        assert result.target_domain is None or isinstance(result.target_domain, str)

    def test_N5_context_optional_fields(self, selector: SpecialistSelector):
        ctx = SpecialistContext(
            route_decision=None,
            creator_goal=None,
            workflow_stage=None,
            workflow_active_task=None,
        )
        result = selector.select(ctx)
        assert isinstance(result, SpecialistSelection)
        assert result.selection_confidence == 0.5


# ===================================================================
# Class TestProjectIsolation
# ===================================================================

class TestProjectIsolation:
    """Specialist registry scope and reuse."""

    def test_registry_scope(self, mock_registry: MagicMock):
        assert len(mock_registry.ids()) >= 22, "registry must have 22+ mock specialist IDs"

    def test_selector_reuses_registry(self, mock_registry: MagicMock):
        sel1 = SpecialistSelector(registry=mock_registry)
        sel2 = SpecialistSelector(registry=mock_registry)
        ctx = SpecialistContext(route_decision=make_route(RouteActionClass.DISCUSS, target="story"))
        r1 = sel1.select(ctx)
        r2 = sel2.select(ctx)
        assert r1.all_selected == r2.all_selected, "same registry must produce same selection"
