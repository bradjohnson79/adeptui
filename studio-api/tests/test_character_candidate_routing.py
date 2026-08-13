"""Character Candidate Diversity + Reference Fidelity tests (Amendment 3).

Verifies:
- Reference-locked candidates route to the Certified reference-capable
  workflow (zimage.ref_edit) with the reference asset as the source image so
  its PIXELS participate in conditioning — not merely a filename in the prompt.
- No-reference candidates route across distinct Certified txt2img families,
  each used once before any reuse (never fabricating distinctness).
- Per-candidate lineage records the correct model/generator/workflowKey/seed.
- full_body_casting composition intent is preserved on every candidate.
- Regeneration preserves reference conditioning (routing is driven from the
  character's attached references each run).
- The Character Profile cannot override visible reference identity fields
  (reference-first authority block is emitted when reference_locked).
- The reference sheet is handled as visual conditioning (source_asset_id),
  not filename-only prompt text.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.visual_sheet import (
    COMPOSITION_INTENT_FULL_BODY_CASTING,
    NO_REFERENCE_TXT2IMG_FAMILIES,
    REFERENCE_FIDELITY_MODE_LIMITED,
    REFERENCE_FIDELITY_DENOISE,
    REFERENCE_LOCKED_FAMILY,
    REFERENCE_LOCKED_WORKFLOW_KEY,
    _build_candidate_routing_plan,
    _candidate_seed,
    _low_reference_fidelity,
    _resolve_reference_asset_id,
    _workflow_lineage,
)
from app.image_prompting.qwen_2512 import compile_character_image_prompt
from app.image_prompting.qwen_2512.compiler import REFERENCE_REPRODUCTION_BLOCK


def _korri_canon() -> dict:
    root = Path(__file__).resolve().parents[2]
    import json

    return json.loads((root / "config" / "character-canon" / "korri.v1.json").read_text(encoding="utf-8"))


# --- Reference asset resolution ---


def test_resolve_reference_asset_id_returns_reference_image_role():
    refs = [
        {"reference_role": "hero_identity", "asset_id": "asset-hero"},
        {"reference_role": "reference_image", "asset_id": "asset-ref"},
    ]
    # hero_identity is canonical authority and counts as the reference lock.
    assert _resolve_reference_asset_id(refs) == "asset-hero"


def test_resolve_reference_asset_id_returns_reference_image_when_no_hero():
    refs = [{"reference_role": "reference_image", "asset_id": "sheet-123"}]
    assert _resolve_reference_asset_id(refs) == "sheet-123"


def test_resolve_reference_asset_id_returns_none_when_no_reference_attached():
    assert _resolve_reference_asset_id([]) is None
    assert _resolve_reference_asset_id([{"reference_role": "wardrobe_reference"}]) is None


# --- Reference-locked routing ---


def test_reference_locked_routing_uses_zimage_ref_edit_with_source_pixels():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-123")
    assert len(plan) == 4
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["modelFamilyPreference"] == REFERENCE_LOCKED_FAMILY
        assert stage1["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY
        # The reference asset ID is passed as source_asset_id so its PIXELS
        # participate in conditioning (img2img latent path), not prompt text.
        assert stage1["source_asset_id"] == "sheet-123"
        assert stage1["referenceAssetId"] == "sheet-123"
        assert stage1["referenceLocked"] is True
        assert stage1["referenceFidelityMode"] == REFERENCE_FIDELITY_MODE_LIMITED
        # Fidelity-first denoise is applied so the reference latent is preserved.
        assert stage1["denoise"] == REFERENCE_FIDELITY_DENOISE


def test_reference_locked_routing_records_honest_limited_mode():
    """Only one Certified reference-capable model exists today — record honestly."""
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-1")
    modes = {route["stage1"]["referenceFidelityMode"] for route in plan}
    assert REFERENCE_FIDELITY_MODE_LIMITED in modes
    # All candidates use the SAME reference-capable workflow (no fabrication).
    keys = {route["stage1"]["workflowKey"] for route in plan}
    assert keys == {REFERENCE_LOCKED_WORKFLOW_KEY}


# --- No-reference multi-model routing ---


def test_no_reference_routing_uses_distinct_certified_families_first():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    assert len(plan) == 4
    families = [route["stage1"]["modelFamilyPreference"] for route in plan]
    # Each distinct Certified family is used once before any reuse.
    distinct = list(NO_REFERENCE_TXT2IMG_FAMILIES)
    for i, fam in enumerate(distinct):
        assert families[i] == fam
    # Remaining slots reuse families (never fabricate a third distinct model).
    assert set(families) == set(distinct)


def test_no_reference_routing_never_fabricates_distinctness():
    """With only 2 Certified txt2img families, a 4-batch must not invent a 3rd/4th."""
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    families = {route["stage1"]["modelFamilyPreference"] for route in plan}
    assert families == set(NO_REFERENCE_TXT2IMG_FAMILIES)
    assert len(families) == len(NO_REFERENCE_TXT2IMG_FAMILIES)


def test_no_reference_routing_has_no_source_asset_or_fidelity_mode():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["source_asset_id"] is None
        assert stage1["referenceAssetId"] is None
        assert stage1["referenceLocked"] is False
        assert stage1["referenceFidelityMode"] is None
        assert stage1["denoise"] is None


def test_fewer_than_four_ready_models_exhausts_unique_before_reuse():
    """2 Certified families → candidates 0,1 distinct; 2,3 reuse with different seeds."""
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    seeds = [_candidate_seed("char-1", i) for i in range(4)]
    # Distinct models used once first.
    assert plan[0]["stage1"]["modelFamilyPreference"] != plan[1]["stage1"]["modelFamilyPreference"]
    # Reuse slots differ by seed (diversity from seed, not identity change).
    assert seeds[0] != seeds[2]
    assert seeds[1] != seeds[3]
    assert len(set(seeds)) == 4


# --- Per-candidate lineage ---


def test_workflow_lineage_resolves_zimage_ref_edit():
    lineage = _workflow_lineage("zimage.ref_edit")
    assert lineage["workflowKey"] == "zimage.ref_edit"
    assert lineage["model"] == "zimage"
    assert lineage["supportsReferences"] is True


def test_workflow_lineage_reports_no_reference_support_for_txt2img():
    lineage = _workflow_lineage("qwen2512.txt2img")
    assert lineage["supportsReferences"] is False


def test_candidate_seeds_are_distinct_within_batch():
    seeds = [_candidate_seed("char-x", i) for i in range(4)]
    assert len(set(seeds)) == 4


# --- Quality gate ---


def test_low_fidelity_flagged_when_reference_locked_but_workflow_cannot_consume_refs():
    lineage = {"supportsReferences": False}
    assert _low_reference_fidelity(reference_locked=True, lineage=lineage) is True


def test_low_fidelity_not_flagged_when_workflow_supports_references():
    lineage = {"supportsReferences": True}
    assert _low_reference_fidelity(reference_locked=True, lineage=lineage) is False


def test_low_fidelity_not_flagged_when_no_reference_attached():
    lineage = {"supportsReferences": False}
    assert _low_reference_fidelity(reference_locked=False, lineage=lineage) is False


# --- full_body_casting preserved ---


def test_composition_intent_constant_is_full_body_casting():
    assert COMPOSITION_INTENT_FULL_BODY_CASTING == "full_body_casting"


def test_reference_locked_prompt_still_emits_full_body_composition():
    """Reference-first authority does NOT remove the full-body requirement."""
    from app.character_identity.visual_sheet import FULL_BODY_CASTING_COMPOSITION, FULL_BODY_CASTING_NEGATIVE_RULES

    composition = dict(FULL_BODY_CASTING_COMPOSITION)
    composition["candidate_index"] = 0
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic full-body character casting reference",
        composition=composition,
        references=[{"reference_role": "reference_image", "asset_id": "sheet-1"}],
        extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
        reference_locked=True,
    )
    prompt = package.prompt.lower()
    assert "full body casting" in prompt
    assert "head to feet" in prompt
    assert "no close-up" in prompt


# --- Reference-first authority: Profile cannot override reference identity ---


def test_reference_locked_emits_reference_reproduction_block():
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic full-body character casting reference",
        references=[{"reference_role": "reference_image", "asset_id": "sheet-1"}],
        reference_locked=True,
    )
    assert "reference_reproduction" in package.block_map
    assert package.block_map["reference_reproduction"] == REFERENCE_REPRODUCTION_BLOCK
    assert package.metadata.get("referenceLocked") is True


def test_reference_reproduction_block_uses_strong_language_not_weak():
    text = REFERENCE_REPRODUCTION_BLOCK.lower()
    assert "reproduce the attached character reference as faithfully as possible" in text
    assert "do not redesign or reinterpret the character" in text
    # Weak reinterpretation language is forbidden.
    assert "inspired by" not in text
    assert "similar to" not in text
    assert "based on" not in text


def test_profile_cannot_override_reference_identity_when_reference_locked():
    """A conflicting profile field must not remove the reference-first directive."""
    canon = _korri_canon()
    canon["visual_description"] = "A tall warrior with blonde hair and silver armor."
    package = compile_character_image_prompt(
        canon,
        prompt_goal="a cinematic full-body character casting reference",
        references=[{"reference_role": "reference_image", "asset_id": "sheet-1"}],
        reference_locked=True,
    )
    # The reference-first directive is present and authoritative regardless of
    # the profile's conflicting "blonde hair" text.
    assert "reference_reproduction" in package.block_map
    assert "preserve the same face" in package.block_map["reference_reproduction"].lower()
    assert package.metadata.get("referenceLocked") is True


def test_no_reference_prompt_does_not_emit_reference_reproduction_block():
    """Without a reference, the Profile remains primary authority (legacy)."""
    package = compile_character_image_prompt(
        _korri_canon(),
        prompt_goal="a cinematic full-body character casting reference",
        reference_locked=False,
    )
    assert "reference_reproduction" not in package.block_map
    assert package.metadata.get("referenceLocked") is False


# --- Reference sheet handled as visual conditioning, not filename ---


def test_reference_sheet_is_passed_as_source_pixels_not_filename():
    """The routing plan carries the sheet asset id as source_asset_id (pixels)."""
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-abc")
    for route in plan:
        # source_asset_id drives the img2img latent path — the sheet's pixels
        # participate in conditioning. The prompt never relies on the filename.
        assert route["stage1"]["source_asset_id"] == "sheet-abc"
        assert route["stage1"]["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY


# --- Regeneration preserves reference + routing ---


def test_regeneration_preserves_reference_lock_and_routing():
    """Re-running the routing plan from the same references yields the same lock."""
    refs = [{"reference_role": "reference_image", "asset_id": "sheet-1"}]
    ref_id = _resolve_reference_asset_id(refs)
    plan_a = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=ref_id)
    plan_b = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=ref_id)
    assert plan_a == plan_b
    for route in plan_a:
        assert route["stage1"]["referenceLocked"] is True
        assert route["stage1"]["source_asset_id"] == "sheet-1"


def test_regeneration_after_reference_detached_drops_reference_lock():
    """If the creator detaches the reference, regeneration is no longer locked."""
    plan_with = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-1")
    plan_without = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    assert all(r["stage1"]["referenceLocked"] for r in plan_with)
    assert all(not r["stage1"]["referenceLocked"] for r in plan_without)
    assert all(r["stage1"]["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY for r in plan_with)
    assert all(r["stage1"]["workflowKey"] != REFERENCE_LOCKED_WORKFLOW_KEY for r in plan_without)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
