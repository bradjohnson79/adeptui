"""ERS knowledgebase loader + dedicated prompt compiler."""

from __future__ import annotations

import inspect
import re

from app.codirector.knowledgebase.ers_compiler import (
    ERS_COMPILER_ID,
    ERS_LAYOUT,
    ERS_PURPOSE,
    compile_environment_reference_sheet_prompt,
    compile_ers_prompt_from_body,
)
from app.codirector.knowledgebase.ers_layout_gate import (
    ERS_LAYOUT_NONCOMPLIANT,
    assess_ers_layout,
)
from app.codirector.knowledgebase.ers_loader import load_ers_knowledgebase
from app.image_product.compile import compile_image_request


_CHARACTER_SHEET_LAYOUT = re.compile(
    r"(?is)(front\s*/\s*side\s*/\s*back|full[- ]body\s+front|full[- ]body\s+side|"
    r"full[- ]body\s+back|head[- ]and[- ]shoulders\s+close[- ]?up|"
    r"four[- ]panel\s+character|character\s+turnaround)"
)


def test_ers_loader_loads_spec_and_lists_both_exemplars() -> None:
    kb = load_ers_knowledgebase()
    assert "unified production-design document" in kb.spec_text.lower()
    assert "character sheet" in kb.spec_text.lower()
    names = {path.name for path in kb.exemplar_paths}
    assert names == {"ERS_REFERENCE_01.png", "ERS_REFERENCE_02.png"}
    for path in kb.exemplar_paths:
        assert path.is_file()
        assert path.stat().st_size > 1000


def test_schnick_coffee_compile_has_ers_sections_not_character_sheet() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Schnick Coffee",
        environment_description="Neighborhood cafe. Intimate, warm, lived-in.",
    )
    prompt = compiled["prompt"]
    lowered = prompt.lower()
    for needle in (
        "hero",
        "spatial",
        "top-down",
        "n / e / s / w",
        "materials",
        "lighting",
        "dna",
        "continuity",
    ):
        assert needle in lowered, needle
    assert "north" in lowered and "east" in lowered and "south" in lowered and "west" in lowered
    assert compiled["purpose"] == ERS_PURPOSE
    assert compiled["layout"] == ERS_LAYOUT
    assert compiled["compiler"] == ERS_COMPILER_ID
    assert _CHARACTER_SHEET_LAYOUT.search(prompt) is None
    assert "Front/Side/Back/Close-Up" not in prompt
    assert "front/side/back" not in lowered
    assert "close-up" not in lowered
    assert "venture" not in lowered
    assert "mother sphere" not in lowered
    assert "korri" not in lowered
    assert "32m" not in lowered


def test_purpose_environment_reference_sheet_uses_ers_compiler() -> None:
    compiled = compile_image_request(
        "proj-schnick-ers",
        {
            "prompt": "Schnick Coffee neighborhood cafe",
            "purpose": "environment_reference_sheet",
            "source": "local",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "lockModelFamily": True,
            "width": 1280,
            "height": 720,
        },
    )
    intent = compiled["imageIntent"]
    prompt = str(intent["prompt"])
    assert intent["purpose"] == ERS_PURPOSE
    assert intent["metadata"].get("ersCompiler") == ERS_COMPILER_ID
    assert intent["metadata"].get("layout") == ERS_LAYOUT
    lowered = prompt.lower()
    for needle in ("hero", "spatial", "top-down", "materials", "lighting", "dna", "continuity"):
        assert needle in lowered, needle
    assert _CHARACTER_SHEET_LAYOUT.search(prompt) is None
    src = inspect.getsource(compile_image_request)
    assert "apply_ers_compile_to_body" in src
    assert "strengthen_four_view_prompt" in src
    # ERS purpose must skip the four-view strengthen, not call it first.
    ers_idx = src.find('purpose != "environment_reference_sheet"')
    strengthen_idx = src.find("strengthen_four_view_prompt")
    assert ers_idx != -1 and strengthen_idx != -1
    assert ers_idx < strengthen_idx


def test_ers_compile_from_body_sets_production_ers_layout() -> None:
    compiled = compile_ers_prompt_from_body(
        {
            "purpose": "environment_reference_sheet",
            "prompt": "Schnick Coffee",
            "name": "Schnick Coffee",
        }
    )
    assert compiled["layout"] == "production_ers"
    assert compiled["compiler"] == ERS_COMPILER_ID


def test_ers_layout_gate_rejects_character_sheet_language() -> None:
    result = assess_ers_layout(
        prompt=(
            "Create a professional four-panel character turnaround sheet. "
            "Front/Side/Back/Close-Up of the same person."
        )
    )
    assert result["layoutNoncompliant"] is True
    assert result["code"] == ERS_LAYOUT_NONCOMPLIANT


def test_ers_layout_gate_rejects_variation_grid() -> None:
    result = assess_ers_layout(prompt="Four variations of the same cafe as a variation grid.")
    assert result["layoutNoncompliant"] is True
    assert result["code"] == ERS_LAYOUT_NONCOMPLIANT


def test_ers_layout_gate_accepts_schnick_compile() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Schnick Coffee",
        environment_description="Neighborhood cafe.",
    )
    result = assess_ers_layout(
        prompt=compiled["prompt"],
        purpose=compiled["purpose"],
        layout=compiled["layout"],
    )
    assert result["layoutNoncompliant"] is False
    assert result["code"] is None


def test_contextual_subjects_stay_in_one_panel_not_directional() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Harbor Warehouse",
        environment_description="A cold industrial warehouse interior with high windows.",
        characters=["char-a"],
        props=["crate-1"],
        contextual_subjects=[
            "Character Mira, slot 1 — species: human; wardrobe: waxed canvas coat",
            "Prop lantern — description: dented brass lantern with cracked glass",
        ],
    )
    prompt = compiled["prompt"]
    lowered = prompt.lower()
    assert "contextual production — occupied scale" in lowered
    assert "waxed canvas coat" in lowered
    assert "dented brass lantern" in lowered
    assert "characters (scale / occupancy" not in lowered
    hero_idx = lowered.index("1. hero environment")
    contextual_idx = lowered.index("9. contextual production")
    directional_idx = lowered.index("4. directional")
    assert hero_idx < directional_idx < contextual_idx
    hero_chunk = lowered[hero_idx:directional_idx]
    assert "environment-only" in hero_chunk
    assert "waxed canvas coat" not in hero_chunk
    assert "dented brass lantern" not in hero_chunk

