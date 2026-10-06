"""Frozen @ CRS / # ERS / % PRS / * video contract."""

from types import SimpleNamespace

from app.codirector.knowledgebase.video_generators import load_video_generator_knowledge
from app.scene_references.sheet_tags import (
    classify_asset,
    display_sheet_token,
    pascal_alias,
    prefix_for_reference,
)


def test_pascal_and_prefixes():
    assert pascal_alias("venture corridor scene") == "VentureCorridorScene"
    assert pascal_alias("%Coffee Mug") == "CoffeeMug"
    assert prefix_for_reference("character") == "@"
    assert prefix_for_reference("environment") == "#"
    assert prefix_for_reference("prop") == "%"
    assert prefix_for_reference("video") == "*"
    # Generic image authority (Image Generator "Other Image References")
    assert prefix_for_reference("generic_image") == "~"
    assert display_sheet_token("Anadriya", "character") == "@Anadriya"
    assert display_sheet_token("VentureCorridorScene", "environment") == "#VentureCorridorScene"
    assert display_sheet_token("CoffeeMug", "prop") == "%CoffeeMug"
    assert display_sheet_token("MoodBoardStill", "generic_image") == "~MoodBoardStill"


def test_generic_image_sigil_is_not_an_r2v_binding_prefix():
    from app.scene_references.sheet_tags import ALL_PREFIXES, R2V_BINDING_PREFIXES

    assert "~" in ALL_PREFIXES
    # The Timeline R2V grammar is frozen: ~ is an authority/provenance tag only.
    assert "~" not in R2V_BINDING_PREFIXES
    assert R2V_BINDING_PREFIXES == frozenset({"@", "#", "%", "*"})


def test_classify_crs_ers_prs():
    crs = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="character_sheet",
            filename="character_sheet_4c1c0bc8_c1_abcd.png",
            labels_json='["character_sheet"]',
            prompt_meta_json="",
        )
    )
    assert crs.kind == "crs"
    assert crs.prefix == "@"
    ers = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="Venture-Corridor-scene",
            filename="Venture Corridor scene.png",
            labels_json="[]",
            prompt_meta_json="",
        )
    )
    assert ers.kind == "ers"
    assert ers.prefix == "#"
    prs = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="prop_reference_sheet",
            filename="CoffeeMug PRS.png",
            labels_json='["prs"]',
            prompt_meta_json="",
        )
    )
    assert prs.kind == "prs"
    assert prs.prefix == "%"


def test_front_still_is_not_crs():
    front = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="character_reference",
            filename="Korri Front.png",
            labels_json='["characters"]',
            prompt_meta_json="",
        )
    )
    assert front.kind == "front_still"
    assert front.prefix == ""


def test_front_still_is_not_ers():
    front = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="character_reference",
            filename="Anadriya Front.png",
            labels_json="[]",
            prompt_meta_json='{"role":"hero_identity"}',
        )
    )
    assert front.kind == "front_still"


def test_prop_creator_still_and_prs_stay_props_when_prompt_says_no_environment():
    from app.prop_creator.prompt import IDENTITY_VIEW

    still = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="prop_schnickcoffeethermos_c1",
            filename="imagegen_edit.png",
            labels_json='["approved_prop","prop_view","primary"]',
            prompt_meta_json=(
                '{"prompt": "Prop: Schnick Coffee Thermos. ' + IDENTITY_VIEW + '", '
                '"purpose": "project prop"}'
            ),
        )
    )
    assert still.kind == "prs"
    assert still.reference_type == "prop"
    assert still.prefix == "%"

    sheet = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="prop_reference_sheet",
            filename="SchnickCoffeeThermos PRS.png",
            labels_json='["prop_reference_sheet","prs","SchnickCoffeeThermos"]',
            prompt_meta_json='{"role": "prop_reference_sheet", "prompt": "no environment scene"}',
        )
    )
    assert sheet.kind == "prs"
    assert sheet.reference_type == "prop"


def test_prop_sheet_is_not_environment_when_prompt_says_no_environment():
    thermos = classify_asset(
        SimpleNamespace(
            kind="image",
            tag="prop_schnick-coffee-thermos_c1",
            filename="imagegen_edit_a6a24fcb.png",
            labels_json='["approved_prop"]',
            prompt_meta_json='{"prompt": "No character holding the prop, no environment scene, no extra props."}',
        )
    )
    assert thermos.kind == "prs"
    assert thermos.reference_type == "prop"
    assert thermos.prefix == "%"


def test_minimax_knowledge_md_loads():
    kb = load_video_generator_knowledge("minimax-h3")
    assert kb.loaded
    assert "@Anadriya" in kb.spec_text
    assert "#VentureCorridorScene" in kb.spec_text
    assert "%CoffeeMug" in kb.spec_text
    assert "<Picture N>" in kb.spec_text
    assert "hero_identity" in kb.spec_text
