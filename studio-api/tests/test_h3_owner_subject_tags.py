"""Timeline MiniMax H3 owner dialect: lowercase <subject N> is Name.

Owner authority (2026-09-09): Timed Prompt = Comfy Input Text; refs = LoadImage
→ ref_image_0..; compiled prompt emits <subject N> is Name. matching socket order.
No wardrobe essays; no trailing orphan <Picture N> as the binding.
"""

from __future__ import annotations

from app.codirector.generator_knowledge.compiler import bind_minimax_subject_tags
from app.director_timeline_w46.generation.r2v import R2VSlot, compile_h3_prompt
from app.director_timeline_w46.generation.semantic_contract import (
    sanitize_action_text,
    subject_definition_line,
    CharacterIdentityLayer,
)


def test_subject_definition_line_is_owner_dialect():
    line = subject_definition_line(
        CharacterIdentityLayer(tag="@Korri", label="Korri", picture_index=1, asset_id="a")
    )
    assert line == "<subject 1> is Korri."
    assert "<Picture" not in line
    assert "<Subject" not in line


def test_compile_h3_emits_lowercase_subject_bindings_for_two_refs():
    authored = "Addex is seated on the couch. Korri sits beside him. They hold hands."
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert prompt == authored
    assert "CHARACTER IDENTITY" not in prompt
    assert "subject_definitions:" not in prompt
    assert "the person defined by <Picture" not in prompt
    assert not prompt.rstrip().endswith("<Picture 1> <Picture 2>")
    assert not prompt.rstrip().endswith("<Picture 2>")


def test_subject_index_matches_ref_image_order():
    """Phase N: compile is verbatim; socket order is pictureIndex, not prompt rewrite."""
    authored = "They sit together."
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=1),
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=2),
        ],
    )
    assert prompt == authored
    reversed_prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
    )
    assert reversed_prompt == authored


def test_h3_path_does_not_strip_lowercase_subject_tags():
    preserved = bind_minimax_subject_tags(
        "Sci-fi quarters.\n\n<subject 1> is Korri.\n\n<subject 2> is Addex.",
        dialect="h3_frame_roles",
        slots=[
            {"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True},
            {"entityId": "e2", "assetId": "a2", "routeASlot": "ref_images", "wired": True},
        ],
    )
    assert "<subject 1> is Korri." in preserved[0]
    assert "<subject 2> is Addex." in preserved[0]
    assert preserved[2] is True
    # Must not append orphan trailing Pictures as the binding substitute
    assert not preserved[0].rstrip().endswith("<Picture 1> <Picture 2>")


def test_non_h3_dialect_still_strips_subject_tags():
    cleaned, _, emitted = bind_minimax_subject_tags(
        "Korri <subject 1> walks",
        dialect="pack_rules",
        slots=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True}],
    )
    assert emitted is False
    assert "<subject" not in cleaned.lower()


def test_sanitize_still_drops_creator_identity_redescribe_essays():
    text = (
        "High quality anime characters interacting in a photorealistic environment.\n\n"
        "<subject 1> is @Korri40YearsOld (Korri).\n"
        "Use <subject 1> as the absolute character identity and appearance reference for Korri. "
        "Preserve her exact face, facial proportions, purple eyes.\n\n"
        "Addex is seated on the couch."
    )
    cleaned = sanitize_action_text(text, style_key="realistic_anime")
    assert "absolute character identity" not in cleaned.lower()
    assert "photorealistic environment" not in cleaned.lower()
    assert "couch" in cleaned.lower()


def test_compile_h3_passthrough_owner_subject_bindings():
    """Phase B: creator <subject N> lines are not mutated by compile_h3_prompt."""
    authored = (
        "<subject 1> is Korri.\n"
        "<subject 2> is Addex.\n\n"
        "Visual style: Realistic Anime with a photorealistic background.\n\n"
        "They sit on the couch."
    )
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert prompt == authored
    assert "<subject 1> is Korri." in prompt
    assert "photorealistic background" in prompt
    assert "Hybrid realistic-anime illustration" not in prompt


def test_sanitize_preserves_owner_subject_lines_even_with_live_action():
    text = (
        "High quality anime characters interacting in a photorealistic environment.\n\n"
        "<subject 1> is Korri.\n"
        "<subject 2> is Addex.\n\n"
        "Addex is seated on the couch."
    )
    cleaned = sanitize_action_text(
        text, style_key="realistic_anime", strip_live_action_bias=False
    )
    assert "<subject 1> is Korri." in cleaned
    assert "<subject 2> is Addex." in cleaned
    assert "photorealistic environment" in cleaned.lower()
    assert "couch" in cleaned.lower()

