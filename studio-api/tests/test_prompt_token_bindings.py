"""Prompt Name tokens in prose must resolve to registered scene-reference IDs."""

from __future__ import annotations

from app.director_timeline import PromptSegment
from app.director_timeline_w46.generation.prompt_token_bindings import (
    extract_prompt_tokens,
    hydrate_segment_prompt_tokens,
    resolve_prompt_tokens_to_bindings,
)


def test_extract_prompt_tokens_unique_order() -> None:
    tokens = extract_prompt_tokens(
        "@Korri and @Anadriya walk down the #VentureCorridorScene. @Korri smiles."
    )
    assert [t["tag"] for t in tokens] == ["@Korri", "@Anadriya", "#VentureCorridorScene"]


def test_resolve_tokens_to_catalog_ids() -> None:
    catalog = [
        {
            "id": "bind-korri",
            "alias": "Korri",
            "asset_name": "Korri",
            "display_token": "@Korri",
            "reference_type": "character",
            "media_kind": "entity",
        },
        {
            "id": "bind-ana",
            "alias": "Anadriya",
            "asset_name": "Anadriya",
            "display_token": "@Anadriya",
            "reference_type": "character",
            "media_kind": "entity",
        },
        {
            "id": "bind-ers",
            "alias": "VentureCorridorScene",
            "asset_name": "Venture corridor",
            "display_token": "#VentureCorridorScene",
            "reference_type": "environment",
            "media_kind": "environment",
        },
    ]
    rows = resolve_prompt_tokens_to_bindings(
        "@Korri and @Anadriya walk the #VentureCorridorScene",
        catalog,
    )
    ids = [r.binding_id for r in rows]
    assert ids == ["bind-korri", "bind-ana", "bind-ers"]
    assert rows[2].type == "environment"


def test_unmatched_token_does_not_invent_binding() -> None:
    rows = resolve_prompt_tokens_to_bindings("@Nobody", [])
    assert rows == []


def test_hydrate_segment_fills_empty_arrays() -> None:
    seg = PromptSegment(text="@Korri waits", reference_binding_ids=[], reference_name_bindings=[])
    changed = hydrate_segment_prompt_tokens(
        seg,
        [
            {
                "id": "bind-korri",
                "alias": "Korri",
                "asset_name": "Korri",
                "display_token": "@Korri",
                "reference_type": "character",
                "media_kind": "entity",
            }
        ],
    )
    assert changed is True
    assert seg.reference_binding_ids == ["bind-korri"]
    assert seg.reference_name_bindings[0].tag == "@Korri"


def test_same_binding_id_is_not_ambiguous() -> None:
    catalog = [
        {
            "id": "bind-korri",
            "alias": "CharacterSheet2",
            "asset_name": "character_sheet",
            "display_token": "@CharacterSheet2",
            "reference_type": "character",
            "media_kind": "entity",
        },
        {
            "id": "bind-korri",
            "alias": "Korri",
            "asset_name": "Korri",
            "display_token": "@Korri",
            "reference_type": "character",
            "media_kind": "entity",
        },
    ]
    rows = resolve_prompt_tokens_to_bindings("@Korri waits", catalog)
    assert [r.binding_id for r in rows] == ["bind-korri"]


def test_backfill_fills_empty_tag_and_asset_from_binding_id(monkeypatch) -> None:
    from app.director_timeline_w46.generation import prompt_token_bindings as mod

    def fake_resolve(db, project_id, binding_id, **kwargs):
        return {
            "bindingId": binding_id,
            "assetId": "asset-earth",
            "identityId": None,
            "alias": "EarthHorizon",
            "referenceType": "environment",
            "broken": False,
            "approvedSheetAssetId": None,
        }

    monkeypatch.setattr(
        "app.director_timeline_w46.generation.reference_compile.resolve_binding_id",
        fake_resolve,
    )
    filled = mod.backfill_name_binding_identities(
        [
            {
                "binding_id": "bind-earth",
                "prompt_name": "Earth Horizon",
                "type": "environment",
                "tag": "",
            }
        ],
        db=object(),
        project_id="proj",
    )
    assert filled[0].tag == "#EarthHorizon"
    assert filled[0].asset_id == "asset-earth"
    assert filled[0].binding_id == "bind-earth"


def test_hydrate_does_not_drop_existing_ids() -> None:
    seg = PromptSegment(
        text="plain prose",
        reference_binding_ids=["already-bound"],
        reference_name_bindings=[],
    )
    changed = hydrate_segment_prompt_tokens(seg, [])
    assert changed is False
    assert seg.reference_binding_ids == ["already-bound"]
