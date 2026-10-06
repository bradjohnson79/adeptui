"""J5/J6: style authority + prompt fidelity unit tests."""
from __future__ import annotations

from app.director_timeline_w46.generation.semantic_contract import (
    sanitize_action_text,
    build_contract,
    lift_style_from_text,
    resolve_style_key,
    allows_live_action_language,
)
from app.director_timeline_w46.generation.r2v import compile_h3_prompt, R2VSlot


LIVE_ACTION_BOILERPLATE = (
    "High quality anime characters interacting in a photorealistic environment. "
    "The final result should look like a scene from a premium live-action cinematic production "
    "in which exceptionally high-quality realistic anime characters physically inhabit "
    "and interact with a real photorealistic environment.\n\n"
    "@Korri40YearsOld and @Addex stand facing each other in a quiet sunlit room. "
    "They exchange a calm friendly greeting with natural restrained motion."
)

CREATOR_ACTION = (
    "@Korri40YearsOld and @Addex stand facing each other in a quiet sunlit room. "
    "They exchange a calm friendly greeting with natural restrained motion. "
    "Keep both character identities locked to their Character Reference Sheets."
)


def test_resolve_style_key_realistic_anime_display_name():
    assert resolve_style_key("Realistic Anime") == "realistic_anime"
    assert resolve_style_key("realistic_anime") == "realistic_anime"


def test_allows_live_action_only_for_photographic_styles():
    assert allows_live_action_language("live_action") is True
    assert allows_live_action_language("documentary_realism") is True
    assert allows_live_action_language("realistic_anime") is False
    assert allows_live_action_language("") is False


def test_sanitize_default_still_strips_live_action_on_realistic_anime_non_h3():
    """Non-H3 / default sanitize may still drop photo bias under realistic_anime."""
    cleaned = sanitize_action_text(LIVE_ACTION_BOILERPLATE, style_key="realistic_anime")
    low = cleaned.lower()
    assert "premium live-action" not in low
    assert "photorealistic environment" not in low
    assert "stand facing each other" in low
    assert "calm friendly greeting" in low


def test_sanitize_h3_path_preserves_live_action_under_realistic_anime():
    """Phase B: H3 Timed Prompt / creator text must keep live-action language."""
    cleaned = sanitize_action_text(
        LIVE_ACTION_BOILERPLATE,
        style_key="realistic_anime",
        strip_live_action_bias=False,
    )
    low = cleaned.lower()
    assert "premium live-action" in low
    assert "photorealistic environment" in low
    assert "stand facing each other" in low


def test_h3_compile_does_not_reinject_registry_style_without_prompt_line():
    slots = [
        R2VSlot(assetId="a42e77e0", role="character", label="Korri-40-years-old", pictureIndex=1),
        R2VSlot(assetId="91b82df6", role="character", label="Addex", pictureIndex=2),
    ]
    # Phase B: prefer never reinjecting registry style over authored Timed Prompt.
    prompt, _ = compile_h3_prompt(CREATOR_ACTION, slots, style_key="realistic_anime")
    assert "Hybrid realistic-anime illustration" not in prompt
    assert "stand facing each other" in prompt
    assert "Anadriya" not in prompt


def test_h3_compile_preserves_scene4_live_action_boilerplate():
    """Phase B invert: owner live-action preamble survives H3 compile."""
    slots = [
        R2VSlot(assetId="a42e77e0", role="character", label="Korri-40-years-old", pictureIndex=1),
    ]
    # No <subject N> → fallback compile with for_h3 (no live-action strip, no registry style).
    prompt, _ = compile_h3_prompt(LIVE_ACTION_BOILERPLATE, slots, style_key="realistic_anime")
    low = prompt.lower()
    assert "premium live-action" in low
    assert "photorealistic environment" in low
    assert "Hybrid realistic-anime illustration" not in prompt
    assert "stand facing each other" in prompt


def test_lift_style_from_text_still_works():
    key, cleaned = lift_style_from_text(CREATOR_ACTION + " Visual style: Realistic Anime.")
    assert key == "realistic_anime"
    assert "Visual style" not in cleaned


def test_lift_style_does_not_leave_a_leading_period():
    key, cleaned = lift_style_from_text(
        "Visual style: Realistic Anime with a photorealistic background.\n\nSci-fi living quarters."
    )
    assert key == "realistic_anime"
    assert not cleaned.startswith(".")
    assert "Sci-fi living quarters" in cleaned
    assert "photorealistic background" not in cleaned


def test_build_contract_action_preserves_creator_without_recast():
    contract = build_contract(slots=[], authored=CREATOR_ACTION, style_key="realistic_anime")
    assert contract.style_key == "realistic_anime"
    assert "stand facing each other" in contract.action
    assert "premium live-action" not in contract.action.lower()
