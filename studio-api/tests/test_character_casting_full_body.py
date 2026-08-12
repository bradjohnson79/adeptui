"""Full-body casting composition rule tests (Amendment 2).

Verifies the Character Creator candidate-generation prompt pipeline emits
full-body framing, rejects close-up/headshot/bust framing, preserves the
requirement across regeneration, and records compositionIntent lineage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.visual_sheet import (
    COMPOSITION_INTENT_FULL_BODY_CASTING,
    FULL_BODY_CASTING_COMPOSITION,
    FULL_BODY_CASTING_NEGATIVE_RULES,
)
from app.image_prompting.qwen_2512 import compile_character_image_prompt


def _korri_canon() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "config" / "character-canon" / "korri.v1.json").read_text(encoding="utf-8"))


def test_full_body_composition_constant_present():
    """The full-body composition constant is defined and structural."""
    assert FULL_BODY_CASTING_COMPOSITION.get("full_body") is True
    assert "head to feet" in FULL_BODY_CASTING_COMPOSITION.get("framing", "")
    assert FULL_BODY_CASTING_COMPOSITION.get("shot_type") == "full body casting reference"


def test_full_body_negative_rules_reject_close_ups():
    """Negative rules explicitly reject close-up/headshot/bust framing."""
    joined = " ".join(FULL_BODY_CASTING_NEGATIVE_RULES).lower()
    assert "no close-up" in joined
    assert "no headshot" in joined
    assert "no bust" in joined
    assert "no waist-up" in joined
    assert "do not crop head" in joined


def test_compile_character_image_prompt_with_full_body_emits_full_body_block():
    """compile_character_image_prompt with full_body=True emits canonical full-body block."""
    composition = dict(FULL_BODY_CASTING_COMPOSITION)
    composition["candidate_index"] = 0
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic full-body character casting reference",
        composition=composition,
        extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
    )
    prompt = package.prompt.lower()
    # Full-body requirement present
    assert "full body casting" in prompt
    assert "head to feet" in prompt
    assert "entire body visible" in prompt
    # Close-up framing explicitly rejected
    assert "no close-up" in prompt
    assert "no headshot" in prompt
    assert "no bust portrait" in prompt
    assert "no waist-up" in prompt
    # Legacy portrait framing NOT present
    assert "face and shoulders" not in prompt
    assert "hero portrait" not in prompt


def test_compile_character_image_prompt_without_full_body_does_not_emit_block():
    """Without full_body flag, the canonical full-body block is not injected."""
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic hero portrait reference",
        composition={
            "shot_type": "hero portrait",
            "framing": "face and shoulders",
            "camera_angle": "eye level",
            "lens": "50mm",
        },
    )
    prompt = package.prompt.lower()
    assert "full body casting composition" not in prompt


def test_composition_intent_lineage_constant_defined():
    """compositionIntent lineage metadata constant is defined for prompt_metadata."""
    assert COMPOSITION_INTENT_FULL_BODY_CASTING == "full_body_casting"


def test_reference_conditioning_preserves_full_body_requirement():
    """When references are supplied, full-body instruction is still present."""
    composition = dict(FULL_BODY_CASTING_COMPOSITION)
    composition["candidate_index"] = 0
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic full-body character casting reference",
        composition=composition,
        references=[
            {"reference_role": "hero_identity"},
            {"reference_role": "reference_image"},
        ],
        extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
    )
    prompt = package.prompt.lower()
    assert "full body casting" in prompt
    assert "no close-up" in prompt
    # Reference roles considered
    assert "hero_identity" in package.prompt or "hero identity" in package.prompt.lower()


def test_all_candidates_in_batch_share_full_body_composition():
    """Simulate a 4-candidate batch — each uses the same full-body composition."""
    for i in range(4):
        composition = dict(FULL_BODY_CASTING_COMPOSITION)
        composition["candidate_index"] = i
        package = compile_character_image_prompt(
            _korri_canon(),
            prompt_goal="a cinematic full-body character casting reference",
            composition=composition,
            extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
        )
        assert "full body casting" in package.prompt.lower()
        assert "no close-up" in package.prompt.lower()


def test_profile_edits_do_not_remove_full_body_requirement():
    """Editing the Character Profile (visual_description) doesn't remove the rule.

    The full-body rule is structural (composition block), not derived from
    profile text, so profile edits cannot remove it.
    """
    canon = _korri_canon()
    canon["visual_description"] = "A tall warrior with silver armor and a red cape."
    composition = dict(FULL_BODY_CASTING_COMPOSITION)
    composition["candidate_index"] = 0
    package = compile_character_image_prompt(
        canon,
        prompt_goal="a cinematic full-body character casting reference",
        composition=composition,
        extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
    )
    prompt = package.prompt.lower()
    assert "full body casting" in prompt
    assert "no close-up" in prompt
    # Profile text preserved (supplemented, not rewritten)
    assert "silver armor" in prompt or "red cape" in prompt


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
