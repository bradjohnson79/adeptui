"""Director breakdown + cinematic ACTION — never copy the creator's request."""

from __future__ import annotations

from app.codirector.production.canonical_tags import prompt_facing_tag, suffixed_tag_variants
from app.codirector.production.contracts import ResolvedReference
from app.codirector.production.instruction_copy import contains_instruction_copy, instruction_copy_hits
from app.codirector.production.intent_parser import parse_scene_intent
from app.codirector.production.prompt_compiler import compile_generator_prompt, extract_prompt_section
from app.codirector.production.scene_breakdown import build_director_scene_intent

CADE_PROMPT = """
I would like you to build a scene in Timeline where we will have an establishing shot scene, where we will use the Earth Horizon Environment Reference Sheet as the scene. We will also use the Venture Spaceship Prop Reference Sheet, and also the Cade's Starfighter prop reference sheet.

The scene is that we will see the Venture Spaceship in orbit above the Earth's horizon. We will see a blue portal effect showing Cade's Starfighter appear. It will maneuver itself so that it remains directly above the Venture undetected. We want to appear of sizes between these two vessels. The Venture is over a kilometer long, and Cade's Starfighter is 9.8 meters long.

This scene will be created in Timeline using MiniMax H3, Megapixels 2.0 quality, 21:9 frame ratio. And will have a single batch runtime of 10 seconds.
"""


def _cade_refs() -> list[ResolvedReference]:
    return [
        ResolvedReference(
            status="found",
            query="Cade's Starfighter",
            display_name="Cade's Starfighter",
            asset_type="prop",
            asset_id="starfighter",
            canonical_tag="%CadeSStarfighter",
            identity_tag="CadeSStarfighter",
            verification="found",
            approved_sheet=True,
        ),
        ResolvedReference(
            status="found",
            query="Venture Spaceship",
            display_name="Venture Spaceship",
            asset_type="prop",
            asset_id="venture",
            canonical_tag="%VentureSpaceship",
            identity_tag="VentureSpaceship",
            verification="global_found",
            is_global=True,
            approved_sheet=True,
        ),
        ResolvedReference(
            status="found",
            query="Earth Horizon",
            display_name="Earth Horizon",
            asset_type="environment",
            asset_id="horizon",
            canonical_tag="#EarthHorizon",
            identity_tag="EarthHorizon",
            verification="found",
            approved_sheet=True,
        ),
    ]


def test_layers_do_not_collapse() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    refs = _cade_refs()
    intent = build_director_scene_intent(spec, refs, allow_llm=False)
    # Orchestrator flow: the compiler reuses the same Layer B intent.
    spec.director_intent = intent
    prompt = compile_generator_prompt(spec, refs)
    assert spec.source_user_prompt.lower().startswith("i would like you")
    assert intent.user_request == spec.source_user_prompt
    assert intent.action_text
    assert intent.action_text != spec.source_user_prompt
    assert "I would like" not in intent.action_text
    action = extract_prompt_section(prompt, "ACTION")
    assert action == intent.action_text


def test_action_rejects_instruction_copy() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    intent = build_director_scene_intent(spec, _cade_refs(), allow_llm=False)
    spec.director_intent = intent
    prompt = compile_generator_prompt(spec, _cade_refs())
    action = extract_prompt_section(prompt, "ACTION")
    assert action
    assert not contains_instruction_copy(action), instruction_copy_hits(action)
    for phrase in (
        "I would like you",
        "build a scene in Timeline",
        "use the reference sheet",
        "runtime of 10 seconds",
        "frame ratio",
        "quality",
    ):
        assert phrase.lower() not in action.lower()
    lower = action.lower()
    assert "orbit" in lower
    assert "portal" in lower
    assert "starfighter" in lower
    assert "above" in lower
    assert "undetected" in lower or "unnoticed" in lower
    # Scale language belongs in SPATIAL RELATIONSHIPS, not ACTION prose.
    spatial = extract_prompt_section(prompt, "SPATIAL RELATIONSHIPS").lower()
    assert "kilometer" in spatial or "1 km" in spatial
    assert "9.8" in spatial
    assert "dwarf" in spatial or "more visual mass" in spatial or "scale" in spatial


def test_canonical_tags_are_stable() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    refs = _cade_refs()
    prompt = compile_generator_prompt(spec, refs)
    for tag in ("%VentureSpaceship", "%CadeSStarfighter", "#EarthHorizon"):
        assert tag in prompt
        for variant in suffixed_tag_variants(tag):
            assert variant not in prompt


def test_collision_alias_is_stripped_from_prompt_tag() -> None:
    assert prompt_facing_tag("%", "VentureSpaceship3", "Venture Spaceship") == "%VentureSpaceship"
    assert prompt_facing_tag("%", "VentureSpaceship-3", "Venture Spaceship") == "%VentureSpaceship"
    assert prompt_facing_tag("#", "EarthHorizon2", "Earth Horizon") == "#EarthHorizon"
    assert prompt_facing_tag("%", "CadeSStarfighter", "Cade's Starfighter") == "%CadeSStarfighter"
    assert prompt_facing_tag("%", "venture-spaceship-4", "Venture Spaceship") == "%VentureSpaceship"
    assert prompt_facing_tag("%", "cade-s-starfighter-2", "Cade's Starfighter") == "%CadeSStarfighter"
    assert prompt_facing_tag("#", "environment_reference", "Earth Horizon") == "#EarthHorizon"


def test_director_intent_has_verified_breakdown() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    intent = build_director_scene_intent(spec, _cade_refs(), allow_llm=False)
    assert "establishing" in intent.shot_type
    assert intent.environment.tag == "#EarthHorizon"
    assert intent.environment.verified
    tags = {item.tag for item in intent.subjects}
    assert "%VentureSpaceship" in tags
    assert "%CadeSStarfighter" in tags
    assert any("primary" in item.role for item in intent.subjects)
    assert all(item.role for item in intent.subjects)
    assert intent.vfx_event
    assert "portal" in intent.vfx_event.lower()
    assert intent.scale_summary
    assert "1 km" in intent.scale_summary or "kilometer" in intent.scale_summary.lower()
    assert "9.8" in intent.scale_summary
    assert len(intent.timed_beats) >= 3
    assert intent.timed_beats[0].start_sec == 0
    assert intent.timed_beats[-1].end_sec == spec.duration_seconds
    assert any("undetected" in beat.lower() for beat in intent.beats)


def test_suffix_authoritative_tag_does_not_leak_into_prompt() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    prompt = compile_generator_prompt(spec, _cade_refs())
    assert "%VentureSpaceship" in prompt
    assert "%VentureSpaceship2" not in prompt
    assert "%VentureSpaceship3" not in prompt
    assert "%VentureSpaceship4" not in prompt
    assert "%CadeSStarfighter2" not in prompt
    assert "#EarthHorizon2" not in prompt
