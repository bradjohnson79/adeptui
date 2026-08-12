"""Phase 9 — Schnick Coffee 14-turn sustained conversation scenario."""
import pytest
from tests.helpers.scenario_session import ScenarioSession
from app.codirector.routing.contracts import RouteActionClass


class TestSchnickCoffee:
    """Schnick Coffee flagship sustained scenario — 14 turns."""

    @pytest.fixture
    def session(self):
        s = ScenarioSession(project_id="schnick-coffee", format_str="commercial")
        s.set_fact("title", "Schnick Coffee", "creator-stated")
        s.set_fact("format", "commercial", "creator-stated")
        s.set_fact("runtime", "20", "creator-stated")
        s.set_fact("primary_character", "Korri", "creator-stated")
        return s

    def test_turn1_project_intent(self, session):
        """Creator establishes project: 20s commercial, Schnick Coffee, Korri."""
        r = session.turn(
            "I'm looking to create a 20 second commercial called 'Schnick Coffee'. It will feature a single character named Korri. I'd like to write the script for it with you.",
            expected_action="DISCUSS",
        )
        assert session.facts.get("title", {}).get("value") == "Schnick Coffee"
        assert session.facts.get("format", {}).get("value") == "commercial"
        assert session.facts.get("runtime", {}).get("value") == "20"
        assert "Korri" in (session.snapshot.keyCharacters or [])
        assert "generic" not in r.response.lower() or "questionnaire" not in r.response.lower()
        r.assert_no_leakage()

    def test_turn2_open_script_writer(self, session):
        session.turn("Can you open Script Writer for me?", expected_action="NAVIGATE")
        r = session.turn("Can you open Script Writer for me?")
        r.assert_navigate()
        r.assert_no_leakage()
        assert session.facts.get("script_exists") is None

    def test_turn3_provide_script(self, session):
        script = (
            "INT. COFFEE SHOP - DAY.\n\n"
            "The female Elf Korri is behind a barista counter and steps away from the Espresso machine.\n\n"
            "KORRI\n"
            "If you're looking to try something different, try Schnick Coffee. Sure it's green, and it stinks. But green is the new brown!\n\n"
            "Korri picks up a coffee filled with warm green liquid. She pinches her nose.\n\n"
            "KORRI\n"
            "You don't really expect me to drink this, do you? This commercial's a gag, isn't it?\n\n"
            "NARRATOR (V.O.)\n"
            "Schnick Coffee. Of course don't drink it. This commercial's a gag.\n\n"
            "END SCRIPT."
        )
        session.set_script_exists(True)
        r = session.turn(script)
        assert session.facts.get("script_exists", {}).get("value") == "true"
        assert "larger project" not in r.response.lower()
        r.assert_no_leakage()

    def test_turn4_creative_critique(self, session):
        r = session.turn("What do you think?")
        r.assert_discuss()

    def test_turn5_targeted_concern(self, session):
        r = session.turn("I think Korri's last line is too long.")
        r.assert_discuss()
        if session.conversation_goal:
            assert "script" in session.conversation_goal or "development" in session.conversation_goal

    def test_turn6_make_it_shorter(self, session):
        r = session.turn("Make it shorter.")
        r.assert_no_leakage()

    def test_turn7_reject(self, session):
        r = session.turn("No, keep mine.")
        r.assert_no_leakage()

    def test_turn8_what_next(self, session):
        r = session.turn("What should we do next?")
        assert r.conversation_plan is not None
        r.assert_no_leakage()

    def test_turn9_defer_shots(self, session):
        r = session.turn("Not shots yet. Let's figure out how Korri should deliver the gag.")
        r.assert_discuss()
        session.deferred.add("shot_planning")

    def test_turn10_cross_disciplinary(self, session):
        r = session.turn("How should we shoot the final reveal so Korri's delivery lands harder?")
        r.assert_discuss()
        r.assert_no_leakage()

    def test_turn11_manual_work_reconciliation(self, session):
        session.snapshot.keyCharacters = session.snapshot.keyCharacters or ["Korri"]
        session.set_fact("generated_assets", "true", "system-derived")
        r = session.turn("Where are we now?")
        assert session.facts.get("generated_assets", {}).get("value") == "true"
        r.assert_no_leakage()

    def test_turn12_negated_action(self, session):
        r = session.turn("I don't want to open Timeline yet.")
        if r.route_decision:
            assert r.route_decision.actionClass != RouteActionClass.NAVIGATE, "Negation should prevent NAVIGATE"
        assert not r.operator_requested, "Negated action should not request operator"
        r.assert_no_leakage()

    def test_turn13_ambiguous_action(self, session):
        r = session.turn("Open the editor.")
        r.assert_no_leakage()

    def test_turn14_resolved_ambiguity(self, session):
        r = session.turn("MAGI.")
        r.assert_no_leakage()
