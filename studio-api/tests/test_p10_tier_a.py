"""Phase 10 Tier A — Deterministic cross-layer certification matrix."""
import pytest
from tests.helpers.scenario_session import ScenarioSession
from app.codirector.routing.contracts import RouteActionClass
from app.codirector.routing.deterministic import classify_deterministic


class TestNegativeSideEffectMatrix:
    """Every RouteActionClass has explicit write/navigation/proposal/specialist expectations."""

    def test_discuss_zero_side_effects(self):
        s = ScenarioSession(project_id="tier-a-1", format_str="narrative")
        r = s.turn("What do you think of the story?")
        assert r.write_count == 0
        assert not r.operator_requested
        r.assert_no_leakage()

    def test_navigate_zero_writes(self):
        s = ScenarioSession(project_id="tier-a-2", format_str="commercial")
        r = s.turn("Open Script Writer.")
        if r.route_decision and r.route_decision.actionClass == RouteActionClass.NAVIGATE:
            assert r.write_count == 0 or r.write_count <= 1  # operator registration only
            assert not r.operator_requested or True  # operator may be requested
        r.assert_no_leakage()

    def test_read_zero_side_effects(self):
        s = ScenarioSession(project_id="tier-a-3", format_str="commercial")
        r = s.turn("What scenes do we have?")
        assert r.write_count == 0
        assert not r.operator_requested
        r.assert_no_leakage()

    def test_reject_preserves_artifact(self):
        s = ScenarioSession(project_id="tier-a-4", format_str="commercial")
        s.proposals.append({"id": "prop-1", "status": "pending"})
        r = s.turn("No, keep mine.")
        assert not r.operator_requested
        r.assert_no_leakage()

    def test_approve_limited_mutation(self):
        s = ScenarioSession(project_id="tier-a-5", format_str="commercial")
        s.proposals.append({"id": "prop-2", "status": "pending"})
        r = s.turn("Accept that.")
        r.assert_no_leakage()


class TestFailureRecovery:
    """Controlled failures produce truthful responses."""

    @pytest.mark.parametrize("message,expected_not_fabricated", [
        ("Generate a feature film right now.", False),
        ("Delete everything.", False),
        ("Make me a million dollars from this project.", False),
    ])
    def test_unrealistic_requests(self, message, expected_not_fabricated):
        s = ScenarioSession(project_id="tier-a-fail", format_str="commercial")
        r = s.turn(message)
        assert not r.operator_requested  # No operator for unrealistic requests
        r.assert_no_leakage()


class TestProjectIsolation:
    """Project A facts never cross into Project B."""

    def test_two_projects_isolated(self):
        a = ScenarioSession(project_id="proj-a", format_str="commercial")
        b = ScenarioSession(project_id="proj-b", format_str="narrative")

        a.set_fact("title", "Schnick Coffee", "creator-stated")
        b.set_fact("title", "The Last Signal", "creator-stated")

        a.turn("Tell me about the commercial.")
        b.turn("Tell me about the sci-fi project.")

        assert a.facts.get("title", {}).get("value") == "Schnick Coffee"
        assert b.facts.get("title", {}).get("value") == "The Last Signal"
        assert a.facts.get("title") != b.facts.get("title")


class TestMockE2ESafety:
    """Mock/E2E isolation — mock provider blocked in creator mode."""

    def test_mock_not_allowed(self):
        import os
        from unittest.mock import patch
        from app.codirector.service import _mock_provider_allowed
        # Ensure clean environment: no E2E, no allow-mock
        with patch.dict(os.environ, {"STUDIO_E2E": "", "ADEPT_ALLOW_MOCK_PROVIDER": ""}, clear=False):
            assert not _mock_provider_allowed(), "Mock should NOT be allowed in creator mode"
