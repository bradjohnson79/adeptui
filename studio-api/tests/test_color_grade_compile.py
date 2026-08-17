"""Cinematic color-grade compile + Image Generator category cleanup tests."""

from __future__ import annotations

from app.image_product.compile import compile_image_request
from app.image_product.prompt_intel import expand_prompt
from app.image_studio.color_grades import (
    color_grade_prompt_clause,
    list_color_grades,
    resolve_color_grade_id,
)
from app.image_studio.contracts import CinematicControls, CinematicGenerateRequest, cinematic_to_image_product_body


def test_natural_grade_adds_no_prompt_tokens() -> None:
    assert color_grade_prompt_clause("natural") == ""
    assert color_grade_prompt_clause(None, None) == ""
    assert color_grade_prompt_clause("", "unknown-grade") == ""
    info = expand_prompt("hero on bridge", visual_language={"colorGradePreset": "natural"})
    assert "Color grade:" not in info["expandedPrompt"]
    assert "colorGrade" not in info["improvements"]


def test_teal_orange_compile_differs_from_natural() -> None:
    natural = expand_prompt("hero on bridge", visual_language={"colorGradePreset": "natural"})
    teal = expand_prompt("hero on bridge", visual_language={"colorGradePreset": "teal_orange"})
    assert "Color grade:" in teal["expandedPrompt"]
    assert "Teal & Orange" in teal["expandedPrompt"]
    assert "cool teal shadows" in teal["expandedPrompt"]
    assert teal["expandedPrompt"] != natural["expandedPrompt"]
    assert "colorGrade" in teal["improvements"]


def test_legacy_color_treatment_maps_to_preset() -> None:
    assert resolve_color_grade_id(None, "Teal & orange") == "teal_orange"
    assert resolve_color_grade_id(None, "Neutral cinematic") == "cinematic_neutral"
    clause = color_grade_prompt_clause(None, "Teal & orange")
    assert "Teal & Orange" in clause


def test_cinematic_body_stores_color_grade_preset() -> None:
    req = CinematicGenerateRequest(
        prompt="wide dusk alley",
        projectId="proj-grade",
        controls=CinematicControls(colorGradePreset="teal_orange", category="general"),
    )
    body = cinematic_to_image_product_body(req)
    assert body["cinematic"]["colorGradePreset"] == "teal_orange"
    assert body["creativeContext"]["visualLanguage"]["colorGradePreset"] == "teal_orange"
    assert req.controls.category == "general"


def test_cinematic_controls_default_category_is_general() -> None:
    assert CinematicControls().category == "general"


def test_color_grade_list_includes_curated_set() -> None:
    ids = {g["id"] for g in list_color_grades()}
    assert "natural" in ids
    assert "teal_orange" in ids
    assert "cinematic_neutral" in ids
    assert "epic_blockbuster" in ids


def test_compile_image_request_injects_color_grade(monkeypatch) -> None:
    compiled = compile_image_request(
        "test-grade-compile",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "cinematic": {"colorGradePreset": "teal_orange"},
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
        },
    )
    prompt = compiled["promptIntel"]["expandedPrompt"]
    assert "Color grade:" in prompt
    assert "Teal & Orange" in prompt
    natural = compile_image_request(
        "test-grade-compile",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "cinematic": {"colorGradePreset": "natural"},
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
        },
    )
    assert "Color grade:" not in natural["promptIntel"]["expandedPrompt"]
    assert compiled["promptIntel"]["expandedPrompt"] != natural["promptIntel"]["expandedPrompt"]
