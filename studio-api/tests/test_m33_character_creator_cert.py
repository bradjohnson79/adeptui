"""M33-CC Character Creator certification unit tests."""

from __future__ import annotations

from app.codirector.intelligence.specialist_registry import SpecialistRegistry
from app.codirector.intelligence import specialist_selector
from app.codirector.tools import registry as tool_registry


def test_m33_cc_01_character_creator_registered():
    reg = SpecialistRegistry()
    ids = {s.id for s in reg.all()}
    assert "character-creator" in ids


def test_m33_cc_03_character_request_routes_to_creator():
    mapping = getattr(specialist_selector, "_INTENT_SPECIALISTS", None) or getattr(
        specialist_selector, "INTENT_SPECIALISTS", None
    )
    assert mapping is not None
    selected = mapping.get("create_character") or mapping.get("revise_character") or ()
    flat = list(selected) if isinstance(selected, (list, tuple)) else [selected]
    assert any("character-creator" in str(x) for x in flat)


def test_m33_cc_tools_include_plans_and_brief():
    defs = {d.tool_id for d in tool_registry.all_definitions()}
    for tid in (
        "character_creator.create_from_brief",
        "character_creator.inspect_readiness",
        "character_creator.build_reference_plan",
        "character_creator.build_expression_plan",
        "character_creator.build_pose_plan",
        "character_creator.build_voice_plan",
        "character_creator.submit_for_review",
        "character_creator.create_from_script",
        "character_creator.audit_profile",
    ):
        assert tid in defs, tid
