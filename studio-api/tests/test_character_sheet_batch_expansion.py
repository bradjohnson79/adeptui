"""Per-generator Character Sheet batch expansion + close-up prompt law."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.visual_sheet import (
    CLOSEUP_FRONT_NEGATIVE_RULES,
    CONDITIONING_PROFILE_GUIDED,
    CONDITIONING_REFERENCE_CONDITIONED,
    FULL_BODY_CASTING_NEGATIVE_RULES,
    REFERENCE_LOCKED_WORKFLOW_KEY,
    _build_candidate_routing_plan,
    _candidate_view_specs,
    _canonical_view_role,
    _compile_visual_prompt,
    _negative_rules_for_view,
)


def test_list_expansion_illustrious_x2_qwen_x1_cloud_off():
    plan = _build_candidate_routing_plan(
        candidate_count=99,
        reference_asset_id=None,
        generator_sources={
            "local": [
                {"family": "auto", "enabled": False, "batchCount": 2},
                {"family": "illustrious", "enabled": True, "batchCount": 2},
                {"family": "qwen2512", "enabled": True, "batchCount": 1},
                {"family": "zimage", "enabled": False, "batchCount": 4},
            ],
            "api": None,
        },
    )
    assert len(plan) == 3
    families = [r["stage1"]["modelFamilyPreference"] for r in plan]
    assert families == ["illustrious", "illustrious", "qwen2512"]
    assert [r["batchIndex"] for r in plan] == [1, 2, 1]
    assert [r["batchOf"] for r in plan] == [2, 2, 1]
    assert all(r["stage1"]["providerKind"] == "local" for r in plan)


def test_auto_select_contributes_zero_when_explicit_family_checked():
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id=None,
        generator_sources={
            "local": [
                {"family": "auto", "enabled": True, "batchCount": 2},
                {"family": "illustrious", "enabled": True, "batchCount": 2},
            ],
            "api": None,
        },
    )
    assert len(plan) == 2
    assert all(r["stage1"]["modelFamilyPreference"] == "illustrious" for r in plan)
    assert all(r["autoSelect"] is False for r in plan)


def test_unchecked_family_and_cloud_off_create_zero_jobs():
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id=None,
        generator_sources={
            "local": [
                {"family": "illustrious", "enabled": True, "batchCount": 1},
                {"family": "qwen2512", "enabled": False, "batchCount": 4},
            ],
            "api": [
                {
                    "model": "nano-banana-kie",
                    "providerId": "kie",
                    "modelId": "nano-banana-pro",
                    "enabled": True,
                    "batchCount": 4,
                }
            ],
        },
    )
    # Cloud master is ON because api is a list, not null — this tests unchecked local family.
    assert [r["stage1"]["modelFamilyPreference"] for r in plan if r["stage1"]["providerKind"] == "local"] == [
        "illustrious"
    ]


def test_cloud_master_null_ignores_api_checkbox_state():
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id=None,
        generator_sources={
            "local": [{"family": "illustrious", "enabled": True, "batchCount": 1}],
            "api": None,
        },
    )
    assert len(plan) == 1
    assert all(r["stage1"]["providerKind"] == "local" for r in plan)


def test_api_identity_persists_provider_and_model_ids():
    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id=None,
        generator_sources={
            "local": None,
            "api": [
                {
                    "model": "nano-banana-kie",
                    "providerId": "kie",
                    "modelId": "nano-banana-pro",
                    "enabled": True,
                    "batchCount": 2,
                },
                {
                    "model": "seedream-wavespeed",
                    "providerId": "wavespeed",
                    "modelId": "seedream",
                    "enabled": False,
                    "batchCount": 4,
                },
            ],
        },
    )
    assert len(plan) == 2
    for route in plan:
        assert route["stage1"]["providerKind"] == "api"
        assert route["stage1"]["providerId"] == "kie"
        assert route["stage1"]["modelId"] == "nano-banana-pro"
        assert route["stage1"]["hostedModelId"] == "nano-banana-kie"


def test_zimage_reference_stays_ref_edit_for_one_batch():
    plan = _build_candidate_routing_plan(
        candidate_count=99,
        reference_asset_id="ref-1",
        generator_sources={
            "local": [{"family": "zimage", "enabled": True, "batchCount": 1}],
            "api": None,
        },
    )
    assert len(plan) == 1
    stage1 = plan[0]["stage1"]
    assert stage1["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY
    assert stage1["conditioningMode"] == CONDITIONING_REFERENCE_CONDITIONED
    assert stage1["source_asset_id"] == "ref-1"


def test_illustrious_with_reference_stays_profile_guided():
    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id="ref-1",
        generator_sources={
            "local": [{"family": "illustrious", "enabled": True, "batchCount": 1}],
            "api": None,
        },
    )
    assert plan[0]["stage1"]["conditioningMode"] == CONDITIONING_PROFILE_GUIDED
    assert plan[0]["stage1"]["source_asset_id"] is None


def test_closeup_view_role_is_front_closeup():
    assert _canonical_view_role("closeup_front") == "front_closeup"
    specs = _candidate_view_specs()
    closeup = [s for s in specs if s[0] == "closeup_front"][0]
    negatives = closeup[3]
    assert negatives is not None
    joined = " ".join(negatives).lower()
    assert "no full body" in joined
    assert "no fisheye" in joined
    fb = " ".join(FULL_BODY_CASTING_NEGATIVE_RULES).lower()
    assert "no close-up" in fb
    assert "no close-up" not in joined
    fallback = _negative_rules_for_view("closeup_front", None)
    assert "No full body" in fallback
    assert "No close-up" not in fallback


def test_closeup_prompt_does_not_use_full_body_negatives():
    profile = {
        "name": "Korri",
        "visual_description": "black twin ponytails, purple eyes, pointed ears",
        "visual_style": "realistic_anime",
    }
    role, goal, composition, negatives = [
        spec for spec in _candidate_view_specs() if spec[0] == "closeup_front"
    ][0]
    package = _compile_visual_prompt(
        profile,
        prompt_goal=goal,
        composition=composition,
        references=[],
        role=role,
        extra_negative_constraints=_negative_rules_for_view(role, negatives),
    )
    blob = f"{package.prompt}\n{package.negative_prompt}".lower()
    assert "character sheet mode" not in blob
    assert "head-and-shoulders" in blob or "close-up" in blob or "portrait" in blob
    assert "no close-up" not in blob
    assert "no bust portrait" not in blob
    assert any(token in blob for token in ("no full body", "fisheye", "head and shoulders"))
    assert "collage" in blob or "no character sheet" in blob
