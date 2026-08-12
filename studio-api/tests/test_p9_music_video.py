"""Phase 9 — Music video / non-script-heavy workflow scenario."""
import pytest
from tests.helpers.scenario_session import ScenarioSession


class TestMusicVideo:
    @pytest.fixture
    def session(self):
        s = ScenarioSession(project_id="mv-1", format_str="music_video")
        s.set_fact("title", "Neon Drift", "creator-stated")
        s.set_fact("format", "music_video", "creator-stated")
        s.set_fact("primary_character", "Dancer", "creator-stated")
        return s

    def test_turn1_establish_project(self, session):
        """Creator establishes a music-video project. No screenplay gate should block recommendations."""
        r = session.turn(
            "I'm working on a music video called 'Neon Drift'. It's a synthwave track and I want a cyberpunk visual style."
        )
        assert session.facts.get("format", {}).get("value") == "music_video"
        r.assert_no_leakage()
        # Should NOT demand a screenplay — music video format doesn't require one

    def test_turn2_what_to_work_on_first(self, session):
        """What next? — should give music-video appropriate options, not script-first."""
        r = session.turn("What should we work on first?")
        r.assert_no_leakage()
        # Should not demand a screenplay

    def test_turn3_focus_on_visuals(self, session):
        """Creator chooses visual development. Goal should switch."""
        r = session.turn("Let's work on the look first — neon color palette and lighting.")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn4_discuss_performer(self, session):
        """Discuss performer/character without a screenplay."""
        r = session.turn("The dancer should feel disconnected from the neon world around them. What do you think?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn5_choreography_question(self, session):
        """Ask about choreography — discussion, zero writes."""
        r = session.turn("How should the dancer's movements contrast with the pulsing lights?")
        r.assert_discuss()
        r.assert_no_leakage()
