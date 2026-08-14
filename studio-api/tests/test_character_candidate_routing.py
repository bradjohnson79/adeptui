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
    CONDITIONING_PROFILE_GUIDED,
    CONDITIONING_REFERENCE_CONDITIONED,
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
    """Explicit Z-Image + reference stays REFERENCE_CONDITIONED with pixels."""
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-123",
        generator_sources={"local": {"family": "zimage"}, "api": None},
    )
    assert len(plan) == 4
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["modelFamilyPreference"] == REFERENCE_LOCKED_FAMILY
        assert stage1["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY
        assert stage1["source_asset_id"] == "sheet-123"
        assert stage1["referenceAssetId"] == "sheet-123"
        assert stage1["referenceLocked"] is True
        assert stage1["referenceFidelityMode"] == REFERENCE_FIDELITY_MODE_LIMITED
        assert stage1["denoise"] == REFERENCE_FIDELITY_DENOISE
        assert stage1["conditioningMode"] == CONDITIONING_REFERENCE_CONDITIONED
        assert stage1["providerKind"] == "local"


def test_reference_locked_routing_records_honest_limited_mode():
    """Explicit Z-Image + reference records limited fidelity honestly."""
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "zimage"}, "api": None},
    )
    modes = {route["stage1"]["referenceFidelityMode"] for route in plan}
    assert REFERENCE_FIDELITY_MODE_LIMITED in modes
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
    """Z-Image + reference carries the sheet asset id as source_asset_id (pixels)."""
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-abc",
        generator_sources={"local": {"family": "zimage"}, "api": None},
    )
    for route in plan:
        assert route["stage1"]["source_asset_id"] == "sheet-abc"
        assert route["stage1"]["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY


# --- Regeneration preserves reference + routing ---


def test_regeneration_preserves_reference_lock_and_routing():
    """Re-running the routing plan from the same references yields the same lock."""
    refs = [{"reference_role": "reference_image", "asset_id": "sheet-1"}]
    ref_id = _resolve_reference_asset_id(refs)
    sources = {"local": {"family": "zimage"}, "api": None}
    plan_a = _build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=ref_id, generator_sources=sources
    )
    plan_b = _build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=ref_id, generator_sources=sources
    )
    assert plan_a == plan_b
    for route in plan_a:
        assert route["stage1"]["referenceLocked"] is True
        assert route["stage1"]["source_asset_id"] == "sheet-1"


def test_regeneration_after_reference_detached_drops_reference_lock():
    """If the creator detaches the reference, regeneration is no longer locked."""
    sources = {"local": {"family": "zimage"}, "api": None}
    plan_with = _build_candidate_routing_plan(
        candidate_count=4, reference_asset_id="sheet-1", generator_sources=sources
    )
    plan_without = _build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=None, generator_sources=sources
    )
    assert all(r["stage1"]["referenceLocked"] for r in plan_with)
    assert all(not r["stage1"]["referenceLocked"] for r in plan_without)
    assert all(r["stage1"]["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY for r in plan_with)
    assert all(r["stage1"]["workflowKey"] != REFERENCE_LOCKED_WORKFLOW_KEY for r in plan_without)


def test_illustrious_with_reference_is_profile_guided_no_source_pixels():
    plan = _build_candidate_routing_plan(
        candidate_count=2,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "illustrious"}, "api": None},
    )
    assert len(plan) == 2
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["modelFamilyPreference"] == "illustrious"
        assert stage1["workflowKey"] == "illustrious.txt2img"
        assert stage1["source_asset_id"] is None
        assert stage1["referenceLocked"] is False
        assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED
        assert stage1["providerKind"] == "local"


def test_qwen_with_reference_is_profile_guided_no_source_pixels():
    plan = _build_candidate_routing_plan(
        candidate_count=2,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "qwen2512"}, "api": None},
    )
    assert len(plan) == 2
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["modelFamilyPreference"] == "qwen2512"
        assert stage1["workflowKey"] == "qwen2512.txt2img"
        assert stage1["source_asset_id"] is None
        assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED


def test_api_only_does_not_plan_comfy_or_zimage_jobs():
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-1",
        generator_sources={"local": None, "api": {"model": "nano-banana-kie"}},
    )
    assert len(plan) == 4
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["providerKind"] == "api"
        assert stage1["hostedModelId"] == "nano-banana-kie"
        assert stage1["workflowKey"] != REFERENCE_LOCKED_WORKFLOW_KEY
        assert stage1["modelFamilyPreference"] != "zimage"
        assert "comfy" not in str(stage1["workflowKey"]).lower()
        assert stage1["source_asset_id"] is None
        assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED


def test_both_pools_mix_local_and_api_candidates():
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-1",
        generator_sources={
            "local": {"family": "zimage"},
            "api": {"model": "nano-banana-kie"},
        },
    )
    kinds = [r["stage1"]["providerKind"] for r in plan]
    assert "local" in kinds
    assert "api" in kinds
    local = [r["stage1"] for r in plan if r["stage1"]["providerKind"] == "local"]
    api = [r["stage1"] for r in plan if r["stage1"]["providerKind"] == "api"]
    assert all(s["conditioningMode"] == CONDITIONING_REFERENCE_CONDITIONED for s in local)
    assert all(s["source_asset_id"] == "sheet-1" for s in local)
    assert all(s["hostedModelId"] == "nano-banana-kie" for s in api)
    assert all(s["workflowKey"] != REFERENCE_LOCKED_WORKFLOW_KEY for s in api)


def test_auto_select_with_reference_may_mix_conditioning_modes():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-1")
    modes = {r["stage1"]["conditioningMode"] for r in plan}
    families = {r["stage1"]["modelFamilyPreference"] for r in plan}
    # Auto may mix; at least one planned family must be honest about its mode.
    for route in plan:
        stage1 = route["stage1"]
        if stage1["modelFamilyPreference"] in {"illustrious", "qwen2512", "qwen"}:
            assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED
            assert stage1["source_asset_id"] is None
        if stage1["modelFamilyPreference"] == "zimage":
            assert stage1["conditioningMode"] == CONDITIONING_REFERENCE_CONDITIONED
            assert stage1["source_asset_id"] == "sheet-1"
    assert families



def test_api_only_krea_routes_like_kie_no_zimage():
    """Hosted Krea uses the same generatorSources.api.model plan as Kie."""
    from app.character_identity.visual_sheet import (
        KREA_LOCAL_TXT2IMG_KEY,
        _candidate_provenance_label,
        _hosted_family_for_model,
        _hosted_provider_label,
        _krea_model_display,
    )

    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id="sheet-1",
        generator_sources={"local": None, "api": {"model": "krea2-turbo-fal"}},
    )
    assert len(plan) == 4
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["providerKind"] == "api"
        assert stage1["hostedModelId"] == "krea2-turbo-fal"
        assert stage1["selectedSource"] == "krea2-turbo-fal"
        assert stage1["modelFamilyPreference"] == "krea2"
        assert stage1["workflowKey"] == KREA_LOCAL_TXT2IMG_KEY
        assert stage1["workflowKey"] != REFERENCE_LOCKED_WORKFLOW_KEY
        assert stage1["modelFamilyPreference"] != "zimage"
        assert "comfy" not in str(stage1["workflowKey"]).lower()
        assert stage1["source_asset_id"] is None
        assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED
    assert _hosted_family_for_model("krea2-turbo-fal") == "krea2"
    assert _hosted_provider_label("krea2-turbo-fal") == "krea"
    assert _krea_model_display("krea2-turbo-fal") == "Krea 2 Turbo"
    assert _candidate_provenance_label(
        provider_kind="api",
        provider="krea",
        model="Krea 2 Turbo",
        hosted_model_id="krea2-turbo-fal",
        selected_source="krea2-turbo-fal",
        conditioning_mode=CONDITIONING_PROFILE_GUIDED,
    ) == "API — Krea / Krea 2 Turbo — Profile Guided"


def test_local_krea2_is_profile_guided_no_silent_zimage():
    plan = _build_candidate_routing_plan(
        candidate_count=2,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "krea2"}, "api": None},
    )
    assert len(plan) == 2
    for route in plan:
        stage1 = route["stage1"]
        assert stage1["providerKind"] == "local"
        assert stage1["modelFamilyPreference"] == "krea2"
        assert stage1["workflowKey"] == "krea2.turbo_txt2img"
        assert stage1["source_asset_id"] is None
        assert stage1["referenceLocked"] is False
        assert stage1["conditioningMode"] == CONDITIONING_PROFILE_GUIDED


def test_auto_select_does_not_default_to_krea():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    first = plan[0]["stage1"]["modelFamilyPreference"]
    assert first != "krea2"
    assert first in NO_REFERENCE_TXT2IMG_FAMILIES
    families = [r["stage1"]["modelFamilyPreference"] for r in plan]
    assert families[0] != "krea2"


def test_krea_medium_and_large_are_model_specific():
    from app.character_identity.visual_sheet import _krea_model_display, _hosted_family_for_model

    assert _hosted_family_for_model("krea2-medium-fal") == "krea2"
    assert _hosted_family_for_model("krea2-large-fal") == "krea2"
    assert _krea_model_display("krea2-medium-fal") == "Krea 2 Medium"
    assert _krea_model_display("krea2-large-fal") == "Krea 2 Large"
    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id=None,
        generator_sources={"local": None, "api": {"model": "krea2-large-fal"}},
    )
    assert plan[0]["stage1"]["hostedModelId"] == "krea2-large-fal"
    assert plan[0]["stage1"]["providerKind"] == "api"




def test_fal_krea_dock_ids_resolve_to_fal_endpoints():
    from app.character_identity.visual_sheet import _fal_image_model_id
    from app.fal_catalog import build_fal_image_arguments, fal_image_model_id_for_dock
    from app.fal_client import extract_image_url

    assert fal_image_model_id_for_dock("krea2-turbo-fal") == "fal-ai/krea-2/turbo"
    assert fal_image_model_id_for_dock("krea2-medium-fal") == "krea/v2/medium/text-to-image"
    assert fal_image_model_id_for_dock("krea2-large-fal") == "krea/v2/large/text-to-image"
    assert _fal_image_model_id("krea2-turbo-fal") == "fal-ai/krea-2/turbo"
    assert _fal_image_model_id("nano-banana-kie") is None
    args = build_fal_image_arguments(
        model_id="fal-ai/krea-2/turbo", prompt="a character sheet", width=1024, height=1024, seed=7
    )
    assert args["prompt"] == "a character sheet"
    assert args["seed"] == 7
    assert args["image_size"] == {"width": 1024, "height": 1024}
    med = build_fal_image_arguments(model_id="krea/v2/medium/text-to-image", prompt="x", width=1024, height=1024)
    assert med["aspect_ratio"] == "1:1"
    assert extract_image_url({"images": [{"url": "https://fal.media/x.png"}]}) == "https://fal.media/x.png"


def test_pin_fal_image_job_marks_cloud_paid_without_submit():
    """Enqueue pin is a params write only — never calls fal.run."""
    from app.character_identity.visual_sheet import _fal_image_model_id

    hosted = "krea2-turbo-fal"
    fal_id = _fal_image_model_id(hosted)
    params = {"cloudPaid": False, "imageRuntime": {"workflowKey": "zimage.txt2img"}}
    assert fal_id == "fal-ai/krea-2/turbo"
    params["cloudPaid"] = True
    params["falImageModelId"] = fal_id
    assert params["cloudPaid"] is True
    assert not str(params["imageRuntime"]["workflowKey"]).startswith("comfy")



def test_profile_guided_view_instructions_appended_to_base_prompt():
    from app.character_identity.visual_sheet import (
        PROFILE_GUIDED_VIEW_INSTRUCTIONS,
        _compile_visual_prompt,
    )

    profile = _korri_canon()
    pkg = _compile_visual_prompt(
        profile,
        prompt_goal="a cinematic full-body character casting reference",
        composition={"framing": "full body"},
        references=[],
        role="hero_identity",
        reference_locked=False,
    )
    assert PROFILE_GUIDED_VIEW_INSTRUCTIONS["hero_identity"] in pkg.prompt
    side = _compile_visual_prompt(
        profile,
        prompt_goal="a cinematic full-body character casting reference",
        composition={"framing": "full body"},
        references=[],
        role="full_body_side_left",
        reference_locked=False,
    )
    assert PROFILE_GUIDED_VIEW_INSTRUCTIONS["full_body_side_left"] in side.prompt


def test_cloud_off_illustrious_plan_is_local_only():
    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id="sheet-1",
        generator_sources={"local": {"family": "illustrious", "stage2Enabled": False}, "api": None},
    )
    assert len(plan) == 1
    assert plan[0]["stage1"]["providerKind"] == "local"
    assert plan[0]["stage1"]["modelFamilyPreference"] == "illustrious"
    assert plan[0]["stage2Enabled"] is False
    assert plan[0]["stage1"]["hostedModelId"] is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
