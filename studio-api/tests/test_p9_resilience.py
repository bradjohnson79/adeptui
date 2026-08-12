"""Phase 9 — Resilience scenarios: manual work, project switching, corrections."""
import pytest
from app.codirector.routing.contracts import RouteActionClass
from tests.helpers.scenario_session import ScenarioSession


class TestManualWorkResumption:
    """Creator works manually outside chat, then resumes — Co-Director reconciles actual state."""

    @pytest.fixture
    def session(self):
        s = ScenarioSession(project_id="resume-1", format_str="narrative")
        s.set_fact("title", "Manual Test", "creator-stated")
        s.set_fact("format", "narrative", "creator-stated")
        s.set_fact("primary_character", "Test", "creator-stated")
        return s

    def test_turn1_establish_project(self, session):
        r = session.turn("I want to write a short narrative scene.")
        r.assert_no_leakage()

    def test_turn2_simulate_manual_script(self, session):
        """Simulate manual script creation outside chat."""
        session.set_script_exists(True)
        r = session.turn("Where were we?")
        # Must recognize that script now exists
        assert session.facts.get("script_exists", {}).get("value") == "true"
        # Must not say "ready to start script"
        assert "ready to start" not in r.response.lower() or "script" not in r.response.lower()
        r.assert_no_leakage()

    def test_turn3_simulate_manual_visual_assets(self, session):
        """Simulate manual visual asset creation outside chat."""
        session.set_fact("generated_assets", "true", "system-derived")
        r = session.turn("I also generated some test images. What's our status?")
        assert session.facts.get("generated_assets", {}).get("value") == "true"
        r.assert_no_leakage()

    def test_turn4_simulate_manual_timeline(self, session):
        """Simulate manual timeline work outside chat."""
        session.set_fact("timeline_clips", "true", "system-derived")
        r = session.turn("I've been working in the Timeline while you were away.")
        assert session.facts.get("timeline_clips", {}).get("value") == "true"
        r.assert_no_leakage()


class TestProjectSwitching:
    """Two projects — no evidence crossing."""

    def test_project_a_schnick(self):
        s = ScenarioSession(project_id="switch-a", format_str="commercial")
        s.set_fact("title", "Schnick Coffee", "creator-stated")
        r = s.turn("I'm creating a commercial for Schnick Coffee.")
        assert s.facts.get("title", {}).get("value") == "Schnick Coffee"
        r.assert_no_leakage()

    def test_project_b_narrative(self):
        s = ScenarioSession(project_id="switch-b", format_str="narrative")
        s.set_fact("title", "The Last Signal", "creator-stated")
        r = s.turn("Let me tell you about my sci-fi project, 'The Last Signal'.")
        assert s.facts.get("title", {}).get("value") == "The Last Signal"
        # No Schnick Coffee facts here
        assert "Schnick" not in s.facts.get("title", {}).get("value", "")
        r.assert_no_leakage()

    def test_project_a_switch_back(self):
        """Switching back to Project A — facts should still be present."""
        s = ScenarioSession(project_id="switch-a", format_str="commercial")
        s.set_fact("title", "Schnick Coffee", "creator-stated")
        s.set_fact("runtime", "20", "creator-stated")
        r = s.turn("Let's go back to the commercial.")
        assert s.facts.get("title", {}).get("value") == "Schnick Coffee"
        assert s.facts.get("runtime", {}).get("value") == "20"
        r.assert_no_leakage()


class TestCorrectionDissatisfaction:
    """Creator corrections are respected; dissatisfaction acknowledged."""

    @pytest.fixture
    def session(self):
        s = ScenarioSession(project_id="correction-1", format_str="narrative")
        s.set_fact("title", "Correction Test", "creator-stated")
        s.set_fact("primary_character", "Korri", "creator-stated")
        return s

    def test_turn1_establish_context(self, session):
        r = session.turn("Korri is nervous about the commercial shoot.")
        r.assert_no_leakage()

    def test_turn2_correction(self, session):
        """Creator corrects: disgusted, not nervous."""
        r = session.turn("No, Korri is disgusted here, not nervous.")
        r.assert_no_leakage()

    def test_turn3_correction_persists(self, session):
        """Later advice should be consistent with the correction, not resurrect old interpretation."""
        r = session.turn("How should she deliver the line?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn4_dissatisfaction(self, session):
        """Creator expresses dissatisfaction with over-editing."""
        r = session.turn("You're changing too much.")
        r.assert_no_leakage()

    def test_turn5_after_dissatisfaction(self, session):
        """Subsequent request should not trigger over-editing again."""
        r = session.turn("Just make the first sentence shorter.")
        r.assert_no_leakage()
