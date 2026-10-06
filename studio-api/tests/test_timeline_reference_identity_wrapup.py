"""Wrap-up: bound @/%/# reach H3 slots without substitution."""

from __future__ import annotations

from app.director_timeline_w46.contracts import BatchBlock, DurationState
import pytest

from app.director_timeline_w46.generation.character_identity_bind import (
    _bound_characters_missing_from_shot,
    _restrict_to_creator_bound_cast,
    _union_bound_crs_into_shot,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.r2v import (
    CanonicalR2VRequest,
    R2VSlot,
    _is_bound_visual_reference,
    _refuse_dropped_bound_visuals,
    collect_slots_from_batch,
)
from app.director_timeline_w46.generation.semantic_contract import apply_bound_reference_tokens


def test_union_keeps_bound_second_character_without_name_match():
    shot = {
        "characters": [
            {"characterId": "char-korri", "name": "Korri", "assetId": "asset-korri"},
        ],
        "missing": [],
    }
    bound = [
        {
            "kind": "entity",
            "role": "entity_reference",
            "referenceType": "character",
            "identityId": "char-korri",
            "assetId": "asset-korri",
            "tag": "@Korri",
            "consumed": False,
        },
        {
            "kind": "entity",
            "role": "entity_reference",
            "referenceType": "character",
            "identityId": "char-cade",
            "assetId": "asset-cade",
            "tag": "@Cade",
            "consumed": False,
        },
    ]
    out = _union_bound_crs_into_shot(shot, bound)
    ids = {row["characterId"] for row in out["characters"]}
    assets = {row["assetId"] for row in out["characters"]}
    assert ids == {"char-korri", "char-cade"}
    assert assets == {"asset-korri", "asset-cade"}
    assert _bound_characters_missing_from_shot(bound, out) == []


def test_bound_visual_includes_unconsumed_entity():
    ref = {
        "kind": "entity",
        "role": "entity_reference",
        "referenceType": "character",
        "identityId": "char-cade",
        "assetId": "asset-cade",
        "tag": "@Cade",
        "consumed": False,
    }
    assert _is_bound_visual_reference(ref) is True


def test_collect_slots_includes_unconsumed_character_prop_environment():
    batch = BatchBlock(
        id="bb1",
        sceneId="s",
        label="W1",
        generatorId="minimax-h3-local",
        duration=DurationState(plannedDuration=15.0),
        references=[
            {
                "kind": "entity",
                "role": "entity_reference",
                "referenceType": "character",
                "identityId": "char-korri",
                "assetId": "asset-korri",
                "tag": "@Korri",
                "label": "Korri",
                "consumed": False,
            },
            {
                "kind": "entity",
                "role": "entity_reference",
                "referenceType": "character",
                "identityId": "char-cade",
                "assetId": "asset-cade",
                "tag": "@Cade",
                "label": "Cade",
                "consumed": False,
            },
            {
                "kind": "entity",
                "role": "entity_reference",
                "referenceType": "prop",
                "assetId": "asset-venture",
                "tag": "%Venture",
                "label": "Venture",
                "consumed": False,
            },
            {
                "kind": "entity",
                "role": "entity_reference",
                "referenceType": "environment",
                "assetId": "asset-coffee",
                "tag": "#SchnickCoffee",
                "label": "Schnick Coffee",
                "consumed": False,
            },
        ],
    )
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="bb1",
        executionSnapshotId="snap",
        generatorId="minimax-h3-local",
        generationMode="reference",
        prompt="@Korri and @Cade sit at #SchnickCoffee with %Venture.",
        duration=15.0,
    )
    slots = collect_slots_from_batch(batch, req, db=None, auto_continuity_slots=False)
    by_asset = {s.assetId: s for s in slots}
    assert by_asset["asset-korri"].role == "character"
    assert by_asset["asset-cade"].role == "character"
    assert by_asset["asset-venture"].role == "prop"
    assert by_asset["asset-coffee"].role == "place"
    assert by_asset["asset-korri"].label
    assert "@CadeCRS" not in (by_asset["asset-cade"].label or "")


def test_apply_bound_reference_tokens_prepends_without_overwriting_action():
    slots = [
        R2VSlot(role="character", assetId="asset-korri", label="Korri", pictureIndex=1),
        R2VSlot(role="character", assetId="asset-cade", label="Cade", pictureIndex=2),
        R2VSlot(role="place", assetId="asset-coffee", label="Schnick Coffee", pictureIndex=3),
        R2VSlot(role="prop", assetId="asset-venture", label="Venture", pictureIndex=4),
    ]
    authored = "@Korri and @Cade sit at the counter. The coffee is hot."
    out = apply_bound_reference_tokens(authored, slots)
    assert "<subject 1> is Korri." in out
    assert "<subject 2> is Cade." in out
    assert "<Picture 3> is Schnick Coffee (environment)." in out
    assert "<Picture 4> is Venture (prop)." in out
    assert "The coffee is hot." in out
    assert out.index("<subject 1>") < out.index("The coffee is hot.")


def test_apply_bound_reference_tokens_keeps_owner_subject_prompt():
    authored = "<subject 1> is Korri.\n\nKorri waves."
    slots = [R2VSlot(role="character", assetId="asset-korri", label="Korri", pictureIndex=1)]
    out = apply_bound_reference_tokens(authored, slots)
    assert out == authored


def test_missing_bound_character_is_reported():
    shot = {"characters": [{"characterId": "char-korri", "name": "Korri", "assetId": "asset-korri"}]}
    bound = [
        {"kind": "entity", "role": "character", "identityId": "char-korri", "assetId": "asset-korri", "tag": "@Korri"},
        {"kind": "entity", "role": "character", "identityId": "char-cade", "assetId": "asset-cade", "tag": "@Cade"},
    ]
    assert _bound_characters_missing_from_shot(bound, shot) == ["@Cade"]


def test_restrict_keeps_unioned_bound_second_character_and_drops_unbound():
    shot = {
        "characters": [
            {"characterId": "char-korri", "name": "Korri", "assetId": "asset-korri"},
            {"characterId": "char-cade", "name": "Cade", "assetId": "asset-cade"},
            {"characterId": "char-spatial", "name": "MapExtra", "assetId": "asset-spatial"},
        ]
    }
    bound = [
        {
            "kind": "entity",
            "role": "entity_reference",
            "referenceType": "character",
            "identityId": "char-korri",
            "assetId": "asset-korri",
            "tag": "@Korri",
        },
        {
            "kind": "entity",
            "role": "entity_reference",
            "referenceType": "character",
            "identityId": "char-cade",
            "assetId": "asset-cade",
            "tag": "@Cade",
        },
    ]
    out = _restrict_to_creator_bound_cast(shot, bound, ["@Korri sits."])
    ids = {row["characterId"] for row in out["characters"]}
    assert ids == {"char-korri", "char-cade"}
    assert _bound_characters_missing_from_shot(bound, out) == []


def test_refuse_dropped_bound_visual_fail_closed():
    batch = BatchBlock(
        id="bb1",
        sceneId="s",
        label="W1",
        generatorId="minimax-h3-local",
        duration=DurationState(plannedDuration=15.0),
        references=[
            {
                "kind": "entity",
                "role": "entity_reference",
                "referenceType": "character",
                "identityId": "char-cade",
                "assetId": "asset-cade",
                "tag": "@Cade",
                "consumed": False,
            }
        ],
    )
    payload = CanonicalR2VRequest(
        slots=[R2VSlot(role="character", assetId="asset-korri", label="Korri", pictureIndex=1)],
        mappedStartAssetId=None,
        mechanism="h3_ref2va",
        promptPrefix="",
        disclosures=[],
        tensorSlotCount=1,
        promptOnlyCount=0,
    )
    with pytest.raises(ValueError, match="BOUND_REFERENCE_DROPPED"):
        _refuse_dropped_bound_visuals(batch, payload)


def test_window_two_keeps_the_creator_prompt():
    from types import SimpleNamespace

    from app.director_timeline_w46.contracts import ExecutionSnapshot, TimelinePromptSegment
    from app.director_timeline_w46.generation import request_builder as rb
    from app.director_timeline_w46.generation.window_script import assign_later_window_scripts

    cloned = (
        "Duration:\nSeconds: 0-45. This segment is a 45 second scene.\n"
        "Korri and Cade sit at the counter."
    )
    root = BatchBlock(
        id="bb1",
        sceneId="s",
        order=0,
        label="W1",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[TimelinePromptSegment(text=cloned, start=0, length=45)],
    )
    batch = BatchBlock(
        id="bb2",
        sceneId="s",
        order=1,
        label="W2",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[TimelinePromptSegment(text=cloned, start=15, length=15)],
    )
    assign_later_window_scripts(SimpleNamespace(batchBlocks=[root, batch]))
    stored = batch.promptSegments[0].text
    assert stored == cloned
    assert "CONTINUATION" not in stored
    req = rb.build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId="bb2", selectedGenerator="minimax-h3"),
        draft_mode=False,
    )
    assert "Korri and Cade sit at the counter." in req.prompt
    assert "[CONTINUATION window" not in req.prompt
    assert "WINDOW SCOPE" not in req.prompt
