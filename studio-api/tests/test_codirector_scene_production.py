"""Co-Director Timeline scene production — intent, compiler, validator, routing."""

from __future__ import annotations

from app.codirector.production.generator_validator import (
    normalize_generator_config,
    validate_scene_spec_against_generator,
)
from app.codirector.production.intent_parser import parse_scene_intent
from app.codirector.production.prompt_compiler import compile_generator_prompt
from app.codirector.production.contracts import ResolvedReference
from app.codirector.routing.generation_authority import classify_generation_authority
from app.codirector.routing.unified_intent import classify_intent
from app.codirector.production.errors import GeneratorValidationError


CADE_PROMPT = """
I would like you to build a scene in Timeline where we will have an establishing shot scene, where we will use the Earth Horizon Environment Reference Sheet as the scene. We will also use the Venture Spaceship Prop Reference Sheet, and also the Cade's Starfighter prop reference sheet.

The scene is that we will see the Venture Spaceship in orbit above the Earth's horizon. We will see a blue portal effect showing Cade's Starfighter appear. It will maneuver itself so that it remains directly above the Venture undetected. We want to appear of sizes between these two vessels. The Venture is over a kilometer long, and Cade's Starfighter is 9.8 meters long.

This scene will be created in Timeline using MiniMax H3, Megapixels 2.0 quality, 21:9 frame ratio. And will have a single batch runtime of 10 seconds.
"""


def test_cade_intent_parser() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    assert spec.target == "timeline"
    assert spec.media_type == "video"
    assert spec.generator_id == "minimax-h3"
    assert spec.duration_seconds == 10
    assert spec.aspect_ratio == "21:9"
    assert spec.quality == "megapixels-2.0"
    assert spec.megapixels == 2.0
    assert spec.batch_count == 1
    names = [q.query.lower() for q in spec.reference_queries]
    assert any("starfighter" in n for n in names)
    assert any("venture" in n for n in names)
    assert any(n == "earth horizon" or n.endswith("earth horizon") for n in names)
    assert not any(n.startswith("where we will") for n in names)
    types = {q.query.lower(): q.expected_type for q in spec.reference_queries}
    assert any(t == "prop" for t in types.values())
    assert any(t == "environment" for t in types.values())
    assert spec.scale_relationships
    rel = spec.scale_relationships[0]
    assert "100" in rel.approximate_ratio or int(rel.approximate_ratio.split(":")[0]) >= 100
    assert spec.camera.shot_type == "establishing"
    assert spec.production_request_id


def test_cade_request_routes_to_prepare_scene() -> None:
    authority = classify_generation_authority(CADE_PROMPT)
    assert authority is not None
    assert authority.capability == "timeline.prepare_scene"
    unified = classify_intent(CADE_PROMPT, {})
    assert unified.capability == "timeline.prepare_scene"
    assert unified.capability != "ers.generate"
    assert unified.capability != "image.generate"


def test_minimax_compiler_keeps_scale() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    refs = [
        ResolvedReference(
            status="found",
            query="Cade's Starfighter",
            display_name="Cade's Starfighter",
            asset_type="prop",
            asset_id="starfighter",
            canonical_tag="%CadesStarfighter",
        ),
        ResolvedReference(
            status="found",
            query="Venture Spaceship",
            display_name="Venture Spaceship",
            asset_type="prop",
            asset_id="venture",
            canonical_tag="%VentureSpaceship",
        ),
        ResolvedReference(
            status="found",
            query="Earth Horizon",
            display_name="Earth Horizon",
            asset_type="environment",
            asset_id="horizon",
            canonical_tag="#EarthHorizon",
        ),
    ]
    prompt = compile_generator_prompt(spec, refs)
    assert "SPATIAL" in prompt
    assert "dwarf" in prompt.lower() or "scale" in prompt.lower()
    assert "Venture" in prompt
    assert "9.8" in prompt or "starfighter" in prompt.lower()
    assert "<subject" not in prompt
    assert "@Image1" not in prompt
    assert "[R2V]" not in prompt
    assert "I would like" not in prompt.split("ACTION", 1)[-1]


def test_h3_validator_accepts_cade_config() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    caps = validate_scene_spec_against_generator(spec)
    assert caps["generatorId"] == "minimax-h3"
    config = normalize_generator_config(spec)
    assert config["aspectRatio"] == "21:9"
    assert config["h3Resolution"] == {"mode": "manual", "megapixels": 2.0}
    assert config["width"] > config["height"]


def test_h3_validator_rejects_illegal_duration() -> None:
    spec = parse_scene_intent(CADE_PROMPT, project_id="proj")
    spec.duration_seconds = 90
    try:
        validate_scene_spec_against_generator(spec)
    except GeneratorValidationError as exc:
        assert "duration" in exc.message.lower()
    else:
        raise AssertionError("90s MiniMax H3 must be rejected")


def test_same_generate_service_import() -> None:
    import inspect

    from app.codirector.production.orchestrator import generate_prepared_scene
    from app.codirector.production.timeline_builder import create_or_update_shot_from_spec
    from app.director_timeline_w46.orchestrator import submit_batch_generation
    from app.director_timeline_w46.service import add_batch

    assert generate_prepared_scene.__name__ == "generate_prepared_scene"
    assert submit_batch_generation.__name__ == "submit_batch_generation"
    assert add_batch.__name__ == "add_batch"
    src = inspect.getsource(create_or_update_shot_from_spec)
    assert "if unused:" in src
    assert "else:" in src
    assert src.index("if unused:") < src.index("add_batch(")


def test_follow_up_edit_detects_portal_change() -> None:
    from app.codirector.production.intent_parser import is_follow_up_edit

    assert is_follow_up_edit("Make the portal larger and have Cade's ship emerge more slowly.")
    assert not is_follow_up_edit(CADE_PROMPT)


def test_chat_dispatches_timeline_prepare_without_flag() -> None:
    import inspect

    from app.codirector import service as chat_service

    src = inspect.getsource(chat_service)
    assert "should_act_timeline" in src
    assert "timeline.prepare_scene" in src
