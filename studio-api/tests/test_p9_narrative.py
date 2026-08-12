"""Phase 9 — Narrative scene acceptance scenario."""
import pytest
from tests.helpers.scenario_session import ScenarioSession


class TestNarrativeScene:
    @pytest.fixture
    def session(self):
        s = ScenarioSession(project_id="narrative-1", format_str="narrative")
        s.set_fact("title", "The Last Signal", "creator-stated")
        s.set_fact("format", "narrative", "creator-stated")
        s.set_fact("primary_character", "Captain Chen", "creator-stated")
        return s

    def test_turn1_establish_scene(self, session):
        """Creator establishes a dramatic scene intent."""
        r = session.turn(
            "I want to write a dramatic scene where Captain Chen discovers a distress signal from a ship that vanished 20 years ago.",
        )
        # Format-aware: should NOT assume commercial workflow
        assert session.facts.get("format", {}).get("value") == "narrative"
        assert session.facts.get("primary_character", {}).get("value") == "Captain Chen"
        r.assert_no_leakage()

    def test_turn2_character_motivation(self, session):
        """Discuss character motivation — zero writes."""
        r = session.turn("What do you think drives Captain Chen to respond to the signal?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn3_open_script_writer(self, session):
        r = session.turn("Open Script Writer so I can draft this.")
        r.assert_no_leakage()

    def test_turn4_provide_script(self, session):
        session.set_script_exists(True)
        r = session.turn(
            "Here's the opening:\n\nINT. BRIDGE - SPACESHIP AURORA - NIGHT\n\nCaptain Chen stares at the flickering monitor...\n\nEND SCENE."
        )
        assert session.facts.get("script_exists", {}).get("value") == "true"
        r.assert_no_leakage()

    def test_turn5_ask_for_critique(self, session):
        r = session.turn("What do you think of the opening?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn6_ask_about_continuity(self, session):
        """Continuity question should engage discussion, not mutate."""
        r = session.turn("Does the discovery setup pay off later?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn7_ask_shot_readiness(self, session):
        """Are we ready for shots? Workflow Engine should assess readiness."""
        r = session.turn("Are we ready to start planning shots?")
        r.assert_no_leakage()

    def test_turn8_manual_visual_reference(self, session):
        """Simulate manual visual reference addition, then ask for DOP suggestion."""
        session.set_fact("generated_assets", "true", "system-derived")
        r = session.turn("I've added some visual references. How should we light the bridge scene?")
        assert session.facts.get("generated_assets", {}).get("value") == "true"
        r.assert_discuss()
        r.assert_no_leakage()
