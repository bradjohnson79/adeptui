"""Typed CIS-shaped authority compile for Co-Director image.generate."""

from __future__ import annotations

from app.image_product.prompt_tokens import (
    apply_typed_authority_to_body,
    compile_typed_image_authority,
    partition_authority_refs,
)
from app.codirector.routing.ig_live_queries import normalize_image_generator_planning


def test_partition_matches_cis_selected_shape() -> None:
    pack = partition_authority_refs(
        [
            {"kind": "character", "assetId": "char-1", "name": "Cami", "chip": "@Cami"},
            {"kind": "environment", "assetId": "env-1", "name": "VentureCorridor", "chip": "#VentureCorridor"},
            {"kind": "prop", "assetId": "prop-1", "name": "Badge", "chip": "%Badge"},
        ]
    )
    assert [r["assetId"] for r in pack["selectedCharacters"]] == ["char-1"]
    assert pack["selectedEnvironment"]["assetId"] == "env-1"
    assert [r["assetId"] for r in pack["selectedProps"]] == ["prop-1"]
    assert pack["referenceAssetIds"] == ["char-1", "env-1", "prop-1"]
    assert [r["kind"] for r in pack["authorityRefs"]] == ["character", "environment", "prop"]
    assert all(r["assetId"] for r in pack["references"])


def test_compile_preserves_typed_ids_from_planning_not_prose() -> None:
    planning = {
        "prompt": "Cami standing in Venture Corridor",
        "authorityRefs": [
            {
                "key": "character:char-cami",
                "kind": "character",
                "assetId": "char-cami",
                "name": "Cami",
                "chip": "@Cami",
            },
            {
                "key": "environment:env-venture",
                "kind": "environment",
                "assetId": "env-venture",
                "name": "VentureCorridor",
                "chip": "#VentureCorridor",
            },
        ],
        "referenceAssetIds": ["char-cami", "env-venture"],
    }
    pack = compile_typed_image_authority(planning=planning)
    assert pack["referenceAssetIds"] == ["char-cami", "env-venture"]
    assert pack["selectedCharacters"][0]["assetId"] == "char-cami"
    assert pack["selectedEnvironment"]["assetId"] == "env-venture"
    # Must not invent identity from display names alone
    bare = compile_typed_image_authority(
        planning={"prompt": "Cami in Venture Corridor", "authorityRefs": []}
    )
    assert bare["authorityRefs"] == []
    assert bare["referenceAssetIds"] == []


def test_token_kinds_survive_into_authority_pack() -> None:
    token_pack = {
        "tokens": [
            {
                "tag": "@",
                "name": "Cami",
                "token": "@Cami",
                "kind": "character",
                "assetId": "char-cami",
                "source": "character_approved",
            },
            {
                "tag": "#",
                "name": "VentureCorridor",
                "token": "#VentureCorridor",
                "kind": "environment",
                "assetId": "env-venture",
                "source": "approved_ers_alias",
            },
        ],
        "reference_asset_ids": ["char-cami", "env-venture"],
    }
    pack = compile_typed_image_authority(token_pack=token_pack)
    kinds = {r["kind"] for r in pack["authorityRefs"]}
    assert kinds == {"character", "environment"}
    assert set(pack["referenceAssetIds"]) == {"char-cami", "env-venture"}


def test_apply_typed_authority_stamps_body_without_workflow_force() -> None:
    body = {
        "prompt": "test",
        "creativeContext": {"objective": "image_generate"},
    }
    pack = compile_typed_image_authority(
        planning={
            "authorityRefs": [
                {"kind": "character", "assetId": "c1", "name": "Cami", "chip": "@Cami"},
                {"kind": "environment", "assetId": "e1", "name": "Venture", "chip": "#Venture"},
            ]
        }
    )
    apply_typed_authority_to_body(body, pack)
    assert body["referenceAssetIds"] == ["c1", "e1"]
    assert body["authorityRefs"][0]["kind"] == "character"
    assert body["selectedEnvironment"]["assetId"] == "e1"
    assert body["creativeContext"]["authorityRefs"][1]["assetId"] == "e1"
    assert "forceWorkflowKey" not in body
    assert "workflowKey" not in body["creativeContext"]


def test_normalize_planning_fills_cis_partitions() -> None:
    out = normalize_image_generator_planning(
        {
            "authorityRefs": [
                {"kind": "character", "assetId": "c1", "name": "Cami", "chip": "@Cami"},
                {"kind": "environment", "assetId": "e1", "name": "Venture", "chip": "#Venture"},
            ]
        }
    )
    assert out["selectedCharacters"][0]["assetId"] == "c1"
    assert out["selectedEnvironment"]["assetId"] == "e1"
    assert out["referenceAssetIds"] == ["c1", "e1"]
    assert len(out["references"]) == 2
