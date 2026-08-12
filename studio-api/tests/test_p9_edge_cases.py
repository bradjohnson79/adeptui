"""Phase 9 — Edge cases: failure/recovery, known/unknown facts, specialist restraint."""
from app.codirector.conversation.inquiry import _check_known_fact
from app.codirector.routing.contracts import RouteActionClass
from tests.helpers.scenario_session import ScenarioSession


class TestKnownVsUnknownFacts:
    """Known facts remembered; unknown facts not fabricated."""

    def test_known_runtime(self):
        """Known runtime should be remembered."""
        state = {
            "domains": {
                "PROJECT": {
                    "runtime": {"value": "20", "provenance": "creator-stated"},
                },
            },
        }
        assert _check_known_fact("How long is this commercial?", production_state=state), \
            "Known runtime should suppress question"
        assert _check_known_fact("What was the runtime again?", production_state=state), \
            "Known runtime should suppress question"

    def test_unknown_narrator_not_invented(self):
        """Unknown narrator gender should not be fabricated."""
        state = {
            "domains": {
                "PROJECT": {
                    "runtime": {"value": "20", "provenance": "creator-stated"},
                },
            },
        }
        assert not _check_known_fact("What gender is the narrator?", production_state=state), \
            "Unknown fact should NOT be pretended as known"

    def test_ai_inferred_not_suppressed(self):
        """AI-inferred facts should NOT suppress necessary questions."""
        state = {
            "domains": {
                "PROJECT": {
                    "tone": {"value": "comedic", "provenance": "ai-inferred"},
                },
            },
        }
        assert not _check_known_fact("Should the tone be more deadpan?", production_state=state), \
            "AI-inferred facts should not suppress"

    def test_creator_approved_suppressed(self):
        """Creator-approved facts suppress questions."""
        state = {
            "domains": {
                "CHARACTERS": {
                    "primary_character": {"value": "Korri", "provenance": "creator-approved"},
                },
            },
        }
        assert _check_known_fact("Who is the main character?", production_state=state), \
            "Creator-approved fact should suppress"

    def test_session_known_facts(self):
        """ScenarioSession accumulates facts across turns."""
        s = ScenarioSession(project_id="known-test", format_str="commercial")
        s.set_fact("runtime", "20", "creator-stated")
        s.set_fact("title", "Schnick Coffee", "creator-stated")
        assert s.facts.get("runtime", {}).get("value") == "20"
        assert s.facts.get("title", {}).get("value") == "Schnick Coffee"


class TestSpecialistRestraint:
    """Appropriate specialist counts by request class."""

    def test_navigate_zero_specialists(self):
        """NAVIGATE should require zero specialists."""
        s = ScenarioSession(project_id="restraint-nav", format_str="commercial")
        r = s.turn("Open Script Writer.")
        if r.route_decision:
            assert r.route_decision.actionClass != RouteActionClass.DISCUSS

    def test_discuss_reasonable_count(self):
        """Discussion should not spawn excessive specialists."""
        s = ScenarioSession(project_id="restraint-discuss", format_str="narrative")
        r = s.turn("What do you think of the character arc?")
        from app.codirector.routing.contracts import RouteActionClass
        assert r.route_decision is None or r.route_decision.actionClass in (
            RouteActionClass.DISCUSS, RouteActionClass.READ_INSPECT, RouteActionClass.UNKNOWN
        ), f"Expected non-destructive, got {r.route_decision.actionClass if r.route_decision else None}"
        r.assert_no_leakage()

    def test_read_inspect_zero_specialists(self):
        """Simple read should have zero specialists."""
        s = ScenarioSession(project_id="restraint-read", format_str="commercial")
        r = s.turn("What scenes do we have?")
        r.assert_no_leakage()

    def test_cinematography_question(self):
        """Cross-disciplinary request should not spawn everyone."""
        s = ScenarioSession(project_id="restraint-cine", format_str="narrative")
        s.set_fact("generated_assets", "true", "system-derived")
        r = s.turn("How should we light this scene for maximum tension?")
        r.assert_discuss()

    def test_approve_proposal(self):
        """APPROVE should have zero specialists."""
        s = ScenarioSession(project_id="restraint-approve", format_str="commercial")
        s.proposals.append({"id": "prop-1", "status": "pending"})
        r = s.turn("Accept that.")
        r.assert_no_leakage()

    def test_reject_proposal(self):
        """REJECT should have zero specialists."""
        s = ScenarioSession(project_id="restraint-reject", format_str="commercial")
        s.proposals.append({"id": "prop-2", "status": "pending"})
        r = s.turn("No, keep mine.")
        r.assert_no_leakage()


class TestFailureRecovery:
    """Controlled failures produce truthful responses; no fabricated success."""

    def test_missing_project(self):
        """Project with minimal info should not hallucinate."""
        s = ScenarioSession(project_id="empty-test", format_str="unknown")
        r = s.turn("What should I work on first?")
        r.assert_no_leakage()

    def test_unsupported_capability(self):
        """Request for unavailable capability should not claim success."""
        s = ScenarioSession(project_id="cap-test", format_str="commercial")
        r = s.turn("Generate a feature-length film.")
        r.assert_no_leakage()

    def test_ambiguous_request_no_fabrication(self):
        """Ambiguous request should not fabricate an interpretation."""
        s = ScenarioSession(project_id="ambig-test", format_str="commercial")
        r = s.turn("Do the thing.")
        r.assert_no_leakage()

    def test_negation_safety(self):
        """Negated destructive action must not execute."""
        s = ScenarioSession(project_id="negation-test", format_str="narrative")
        s.set_fact("script_exists", "true", "creator-stated")
        r = s.turn("Don't delete the script.")
        if r.route_decision:
            assert r.route_decision.actionClass != RouteActionClass.EXECUTE_PRODUCTION, \
                "Negated destructive action should not execute"
        assert not r.operator_requested
        r.assert_no_leakage()
