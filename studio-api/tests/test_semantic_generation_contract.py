"""Identity authority vs style authority — video prompt contract."""

from __future__ import annotations

from app.director_timeline_w46.generation.r2v import (
    LTX25_MECHANISM,
    R2VSlot,
    compile_h3_prompt,
    compile_single_cond_prompt,
    sanitize_ltx_creative_prompt,
)
from app.director_timeline_w46.generation.semantic_contract import (
    IDENTITY_PRESERVE,
    STYLE_PRESERVE,
    build_contract,
    sanitize_action_text,
    style_rendering_phrase,
)


DANGEROUS = (
    "High quality anime characters interacting in a photorealistic environment. "
    "The final result should look like a scene from a premium live-action cinematic production "
    "in which exceptionally high-quality realistic anime characters physically inhabit "
    "and interact with a real photorealistic environment.\n\n"
    "<subject 1> is @Korri40YearsOld (Korri).\n"
    "Use <subject 1> as the absolute character identity and appearance reference for Korri. "
    "Preserve her exact face, facial proportions, purple eyes, pointed Sun Sprite Elf ears, "
    "blonde hairstyle, petite slim athletic physique, Light Circuitry markings, clothing, "
    "earrings, footwear, and all other established character details.\n\n"
    "Addex is seated on the two seater couch. Korri sits down on his lap."
)


def test_sanitize_drops_identity_redescribe_and_live_action_bias():
    cleaned = sanitize_action_text(DANGEROUS, style_key="realistic_anime")
    assert "premium live-action" not in cleaned.lower()
    assert "photorealistic environment" not in cleaned.lower()
    assert "absolute character identity" not in cleaned.lower()
    assert "<subject 1>" not in cleaned.lower()
    assert "blonde hairstyle" not in cleaned
    assert "couch" in cleaned.lower()


def test_sanitize_keeps_live_action_language_when_style_is_live_action():
    text = "Cinematic live-action photography. They walk into the room."
    cleaned = sanitize_action_text(text, style_key="live_action")
    assert "walk" in cleaned.lower()


def test_h3_layers_passthrough_when_owner_subjects_present():
    """Phase B: authored Timed Prompt with <subject N> is not rewritten."""
    prompt, _ = compile_h3_prompt(
        DANGEROUS,
        [
            R2VSlot(role="character", assetId="a", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="b", label="Addex", pictureIndex=2),
            R2VSlot(role="place", assetId="c", label="Crew quarters", pictureIndex=3),
        ],
        style_key="realistic_anime",
    )
    assert prompt == DANGEROUS
    assert "<subject 1>" in prompt
    assert "couch" in prompt.lower()
    assert "CHARACTER IDENTITY" not in prompt
    assert "subject_definitions:" not in prompt
    assert not prompt.rstrip().endswith("<Picture 1> <Picture 2>")


def test_h3_fallback_synth_without_owner_subjects_keeps_action():
    """Phase N: non-empty Timed Prompt is verbatim — no subject synthesis."""
    authored = "Addex is seated on the two seater couch. Korri sits down on his lap."
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="a", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="b", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert prompt == authored
    assert "Hybrid realistic-anime illustration" not in prompt


def test_style_change_does_not_change_identity_clause():
    slots = [R2VSlot(role="character", assetId="a", label="Hero", pictureIndex=1)]
    anime, _ = compile_h3_prompt("Hero walks in.", slots, style_key="realistic_anime")
    clay, _ = compile_h3_prompt("Hero walks in.", slots, style_key="claymation")
    assert anime == "Hero walks in."
    assert clay == "Hero walks in."
    assert "Hybrid realistic-anime illustration" not in anime


def test_ltx_adapter_uses_same_semantic_layers():
    prompt, disclosures = compile_single_cond_prompt(
        "They sit on the couch.",
        [
            R2VSlot(role="character", assetId="start", label="Korri"),
            R2VSlot(role="character", assetId="extra", label="Addex"),
        ],
        start_id="start",
        mechanism="ltx25_single_cond",
        style_key="realistic_anime",
    )
    assert "CHARACTER IDENTITY" in prompt
    assert "VISUAL STYLE" in prompt
    assert "ACTION" in prompt
    assert "Korri" in prompt
    assert "Addex" in prompt
    assert any("start" in note.lower() and "Korri" in note for note in disclosures)
    assert any("LTX 2.5" in note for note in disclosures)


def test_style_registry_is_wired_not_dead_import():
    phrase = style_rendering_phrase("claymation")
    assert "clay" in phrase.lower()
    assert style_rendering_phrase("nonexistent_style") == ""


def test_sanitize_drops_planning_scaffolding_keeps_action():
    text = (
        "UNCHANGED FACTS: environment, cameras, ERS\n"
        "STARTING STATE (M1): beat PRIMARY Beat 1788913033559\n"
        "ACTION / DIRECTION: PRIMARY Direction 1788913033559 - Anadriya keeps walking.\n"
        "TIMED PROMPT: They stand facing each other and exchange a greeting. "
        "Visual style: Realistic Anime."
    )
    cleaned = sanitize_action_text(text, style_key="realistic_anime")
    assert "UNCHANGED FACTS" not in cleaned
    assert "PRIMARY Beat" not in cleaned
    assert "1788913033559" not in cleaned
    assert "facing" in cleaned.lower()
    assert "greeting" in cleaned.lower()


SCENE5_TIMED = (
    "<subject 1> is Korri (@Korri40YearsOld).\n"
    "<subject 2> is Addex (@Addex).\n\n"
    "In a sci-fi living quarters. Addex is sitting on the couch contemplating. "
    "Korri is standing beside him and sits on the couch next to him. "
    "The two of them hold each other's hands.\n\n"
    "KORRI: Hey babe, are you ready for some fun?\n\n"
    "Addex smiles.\n\n"
    "ADDEX: You know I am."
)


def test_scene5_subject_lines_do_not_replace_reference_pictures():
    """Phase B: owner subject bindings + dialogue stay verbatim on H3 compile."""
    prompt, _ = compile_h3_prompt(
        SCENE5_TIMED,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert prompt == SCENE5_TIMED
    assert "<subject 1> is Korri (@Korri40YearsOld)." in prompt
    assert "<subject 2> is Addex (@Addex)." in prompt
    assert "KORRI:" in prompt
    assert "ADDEX:" in prompt
    assert "Hey babe" in prompt
    assert "You know I am" in prompt
    assert "couch" in prompt.lower()
    assert "CHARACTER IDENTITY" not in prompt
    assert "the person defined by <Picture" not in prompt
    assert "Hybrid realistic-anime illustration" not in prompt


def test_style_line_preserved_on_h3_compile_path():
    """Phase B: H3 keeps creator Visual style line; does not lift it out of Input Text."""
    authored = "They sit on the couch. Visual style: Claymation."
    prompt, _ = compile_h3_prompt(
        authored,
        [R2VSlot(role="character", assetId="a", label="Hero", pictureIndex=1)],
        style_key="",
    )
    assert prompt == authored
    assert "Visual style: Claymation" in prompt
    assert "couch" in prompt.lower()


def test_h3_subject_index_follows_picture_order_not_name_assumptions():
    authored = (
        "Addex is sitting on the couch. Korri sits beside him. They hold hands.\nADDEX: You know I am."
    )
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=1),
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert prompt == authored
    assert "ADDEX:" in prompt

    reversed_authored = "Addex is sitting on the couch. Korri sits beside him."
    reversed_prompt, _ = compile_h3_prompt(
        reversed_authored,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert reversed_prompt == reversed_authored


def test_h3_subject_bind_is_generic_for_any_two_characters():
    authored = "Mira waves. Theo answers."
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="a", label="Mira", pictureIndex=1),
            R2VSlot(role="character", assetId="b", label="Theo", pictureIndex=2),
        ],
    )
    assert prompt == authored
    assert "Korri" not in prompt
    assert "Addex" not in prompt


def test_ltx_adapter_never_emits_minimax_subject_syntax():
    prompt, _ = compile_single_cond_prompt(
        "Mira sits on the couch.",
        [R2VSlot(role="character", assetId="start", label="Mira")],
        start_id="start",
        mechanism="ltx25_single_cond",
        style_key="realistic_anime",
    )
    assert "<Subject" not in prompt
    assert "<Picture" not in prompt
    assert "Mira" in prompt


def test_contract_ledger_marks_image_as_identity_authority():
    contract = build_contract(
        slots=[R2VSlot(role="character", assetId="sheet-1", label="Hero", pictureIndex=1)],
        authored="Hero waves.",
        style_key="anime",
    )
    ledger = contract.to_ledger()
    assert ledger["identityAuthority"] == "reference_image"
    assert ledger["characters"][0]["asset_id"] == "sheet-1"
    assert ledger["style"]["key"] == "anime"


def test_sanitize_ltx_creative_prompt_strips_r2v_impl_prose():
    dirty = (
        "[R2V] Opening picture is the Brad-approved start frame.\n"
        "LTX conditioning: start frame only for Batch 1 (no MiniMax multi-reference pack).\n\n"
        "High-quality cinematic anime characters.\n"
        "Anadriya: \"Hello.\""
    )
    clean = sanitize_ltx_creative_prompt(dirty)
    assert "[R2V]" not in clean
    assert "Opening picture is" not in clean
    assert "LTX conditioning" not in clean
    assert "MiniMax" not in clean
    assert "High-quality cinematic anime characters." in clean
    assert "Anadriya" in clean


def test_ltx25_compile_single_cond_does_not_inject_r2v():
    prompt, disclosures = compile_single_cond_prompt(
        "[R2V] Opening picture is place (place).\nThey walk the corridor.",
        [
            R2VSlot(role="place", assetId="start", label="Venture Corridor"),
            R2VSlot(role="character", assetId="hero", label="Anadriya"),
        ],
        start_id="start",
        mechanism=LTX25_MECHANISM,
    )
    assert "[R2V]" not in prompt
    assert "Opening picture is" not in prompt
    assert "They walk the corridor." in prompt or "walk" in prompt.lower()
    assert any("Structural start frame" in d for d in disclosures)
