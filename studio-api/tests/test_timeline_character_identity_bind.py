"""Timeline LTX must receive canonical character pictures, not names only."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.director_timeline_w46.contracts import BatchBlock, TimelineVisualAnchor
from app.director_timeline_w46.generation.character_identity_bind import (
    _identity_layout,
    apply_character_identity,
    mentioned_character_names,
    prior_identity_ids,
    resolve_shot_characters,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest


def _image_asset(asset_id: str = "img", project_id: str = "proj"):
    asset = MagicMock()
    asset.id = asset_id
    asset.kind = "image"
    asset.project_id = project_id
    return asset


def _db_with_images(*asset_ids: str, project_id: str = "proj"):
    """Session mock whose Asset rows are kind=image (fail-closed gate)."""
    db = MagicMock()
    catalog = {aid: _image_asset(aid, project_id) for aid in asset_ids}

    def _get(_model, key):
        return catalog.get(str(key))

    db.get.side_effect = _get
    return db



def _request(**kwargs) -> TimelineGenerationRequest:
    body = {
        "projectId": "proj",
        "sceneId": "scene",
        "batchBlockId": "bb_1",
        "executionSnapshotId": "snap",
        "generatorId": "ltx-local",
        "prompt": "Korri walks the Venture corridor.",
        "startImageAssetId": "corridor",
    }
    body.update(kwargs)
    return TimelineGenerationRequest(**body)


def _batch(**kwargs) -> BatchBlock:
    return BatchBlock(id="bb_1", sceneId="scene", **kwargs)


def test_identity_layout_keeps_hero_dominant_for_one_character():
    assert _identity_layout(1, True) == "character_focus"
    assert _identity_layout(1, False) == "character_focus"
    assert _identity_layout(2, True) == "two_heroes_place"
    assert _identity_layout(2, False) == "two_heroes_place"


def test_mentioned_names_resolve_at_tags_and_whole_words():
    names = mentioned_character_names(
        "@Korri walks toward Anadriya.",
        ["Korri", "Anadriya"],
    )
    assert names == ["Korri", "Anadriya"]


def test_mentioned_names_do_not_invent_unknown_people():
    names = mentioned_character_names("A stranger walks the hall.", ["Korri", "Anadriya"])
    assert names == []


def test_mentioned_names_require_whole_word():
    names = mentioned_character_names("Korrielle waits.", ["Korri"])
    assert names == []


def test_mentioned_names_strip_sheet_suffix_from_at_tags():
    """@KorriCRS is a reference token, not a character named "KorriCRS".

    When the suffix-stripped token matches a known character name, the full
    token must NOT appear as a separate name — the known name resolves it.
    """
    names = mentioned_character_names(
        "<subject 1> is @KorriCRS (Korri).\n<subject 2> is @AddexCRS.",
        ["Korri", "Addex"],
    )
    assert "KorriCRS" not in names
    assert "AddexCRS" not in names
    assert "Korri" in names
    assert "Addex" in names


def test_mentioned_names_keep_unknown_at_tag_without_suffix_match():
    """An @tag that does not suffix-strip to a known name is still reported."""
    names = mentioned_character_names("@MysteryCRS appears.", ["Korri"])
    assert names == ["MysteryCRS"]


def test_mentioned_names_strip_ers_prs_suffixes():
    names = mentioned_character_names(
        "@ForestERS and @MugPRS appear.",
        ["Forest", "Mug"],
    )
    assert "ForestERS" not in names
    assert "MugPRS" not in names
    assert "Forest" in names
    assert "Mug" in names


def test_resolve_shot_r2v_prefers_character_sheet_not_front():
    db = _db_with_images("crs_korri", "hero_front")
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            return_value={
                "character_id": "char_korri",
                "name": "Korri",
                "approved_sheet_asset_id": "crs_korri",
            },
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "hero_front" if role == "hero_identity" else None,
        ),
    ):
        shot = resolve_shot_characters(db, "proj", ["Korri walks the corridor."], prefer_sheet=True)
    assert shot["missing"] == []
    assert shot["characters"][0]["assetId"] == "crs_korri"


def test_resolve_shot_orders_crs_by_typed_bindings():
    db = _db_with_images("crs_ana", "crs_korri")
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri", "Anadriya"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            side_effect=lambda _db, _pid, name: {
                "Korri": {
                    "character_id": "char_korri",
                    "name": "Korri",
                    "approved_sheet_asset_id": "crs_korri",
                },
                "Anadriya": {
                    "character_id": "char_ana",
                    "name": "Anadriya",
                    "approved_sheet_asset_id": "crs_ana",
                },
            }.get(name),
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
    ):
        shot = resolve_shot_characters(
            db,
            "proj",
            ["Korri meets Anadriya."],
            prefer_sheet=True,
            bound_assets=[
                {"identityId": "char_ana", "role": "character", "assetId": "crs_ana"},
                {"identityId": "char_korri", "role": "character", "assetId": "crs_korri"},
            ],
        )
    assert [c["name"] for c in shot["characters"]] == ["Anadriya", "Korri"]


def test_resolve_shot_prefers_approved_hero_identity():
    db = _db_with_images("hero_identity_asset", "cc_front_other")
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            return_value={
                "character_id": "char_korri",
                "name": "Korri",
                "visual_reference": "cc_front_other",
                "approved_casting_asset_id": "cc_front_other",
            },
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value="hero_identity_asset",
        ),
    ):
        shot = resolve_shot_characters(db, "proj", ["Korri walks the corridor."])
    assert shot["missing"] == []
    assert shot["characters"][0]["assetId"] == "hero_identity_asset"
    assert shot["characters"][0]["characterId"] == "char_korri"


def test_apply_fails_closed_when_named_character_has_no_picture():
    request = _request()
    with patch(
        "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
        return_value={"characters": [], "missing": ["Korri"], "mentioned": ["Korri"]},
    ):
        result = apply_character_identity(
            MagicMock(),
            request,
            _batch(),
            adapter_id="ltx-local",
        )
    assert result["ok"] is False
    assert result["error"] == "CHARACTER_IDENTITY_MISSING"
    assert request.providerOptions.get("ingredients_ic_lora") is not True


def test_apply_fails_closed_when_ingredients_not_ready():
    request = _request()
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
            return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ingredients_status",
            return_value={"ready": False, "message": "Ingredients identity is not ready."},
        ),
    ):
        result = apply_character_identity(
            MagicMock(),
            request,
            _batch(),
            adapter_id="ltx-local",
        )
    assert result["ok"] is False
    assert result["error"] == "CHARACTER_IDENTITY_RUNTIME_UNAVAILABLE"


def test_apply_binds_ingredients_sheet_for_named_ltx_shot():
    request = _request()
    batch = _batch(references=[{"kind": "timelineGenerationLineage", "assetId": "old"}])
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
            return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ingredients_status",
            return_value={"ready": True},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ensure_identity_sheet",
            return_value={
                "id": "sheet_1",
                "source_asset_ids": ["hero", "corridor"],
                "image_asset_id": "sheet_img",
            },
        ) as ensure,
    ):
        result = apply_character_identity(
            MagicMock(),
            request,
            batch,
            adapter_id="ltx-local",
        )
    assert result["ok"] is True
    assert result["applied"] is True
    assert request.providerOptions["ingredients_ic_lora"] is True
    assert request.providerOptions["sheet_id"] == "sheet_1"
    assert request.providerOptions["image_asset_id"] == "sheet_img"
    assert request.providerOptions["characterIdentity"]["characters"] == characters
    identity_refs = [r for r in batch.references if r.get("kind") == "characterIdentity"]
    assert len(identity_refs) == 1
    assert identity_refs[0]["identityIds"] == ["c1"]
    assert identity_refs[0].get("assetId") in (None, "")
    ensure.assert_called_once()
    assert ensure.call_args.kwargs["environment_asset_id"] == "corridor"


def test_apply_skips_ingredients_on_same_cast_last_frame_extension():
    request = _request(
        continuityStrategy="last_frame_i2v",
        lastFrameAssetId="last_frame",
        startImageAssetId="last_frame",
    )
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with patch(
        "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
        return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
    ):
        result = apply_character_identity(
            MagicMock(),
            request,
            _batch(),
            adapter_id="ltx-local",
            prior_identity={"c1"},
        )
    assert result["ok"] is True
    assert result["applied"] is False
    assert result["reason"] == "continuity_already_has_identity"
    assert request.providerOptions.get("ingredients_ic_lora") is not True


def test_apply_rebuilds_sheet_when_new_character_joins():
    request = _request(
        prompt="Korri and Anadriya meet.",
        continuityStrategy="last_frame_i2v",
        lastFrameAssetId="korri_last",
        startImageAssetId="korri_last",
    )
    characters = [
        {"characterId": "c1", "name": "Korri", "assetId": "hero_k"},
        {"characterId": "c2", "name": "Anadriya", "assetId": "hero_a"},
    ]
    scene = MagicMock()
    scene.start_asset_id = "corridor_plate"
    last = MagicMock()
    last.tag = "continuity_last_frame"
    last.kind = "image"
    plate = MagicMock()
    plate.tag = "start_frame"
    plate.kind = "image"
    hero_k = _image_asset("hero_k")
    hero_a = _image_asset("hero_a")
    db = MagicMock()

    def _get(model, key):
        if key == "korri_last":
            return last
        if key == "scene":
            return scene
        if key == "corridor_plate":
            return plate
        if key == "hero_k":
            return hero_k
        if key == "hero_a":
            return hero_a
        return None

    db.get.side_effect = _get
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
            return_value={
                "characters": characters,
                "missing": [],
                "mentioned": ["Korri", "Anadriya"],
            },
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ingredients_status",
            return_value={"ready": True},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ensure_identity_sheet",
            return_value={
                "id": "sheet_2",
                "source_asset_ids": ["hero_k", "hero_a", "corridor_plate"],
                "image_asset_id": "sheet_img_2",
            },
        ) as ensure,
    ):
        earlier = BatchBlock(
            id="bb_0",
            sceneId="scene",
            sourceAnchors=[
                TimelineVisualAnchor(kind="image", assetId="corridor_plate", label="Start frame")
            ],
        )
        result = apply_character_identity(
            db,
            request,
            _batch(),
            adapter_id="ltx-local",
            prior_identity={"c1"},
            batches=[earlier, _batch()],
        )
    assert result["applied"] is True
    assert result["ok"] is True
    ensure.assert_called_once()
    assert ensure.call_args.kwargs["environment_asset_id"] == "corridor_plate"


def test_apply_replaces_previous_identity_binding():
    request = _request()
    batch = _batch(
        references=[
            {
                "kind": "characterIdentity",
                "identityIds": ["old"],
                "sheetId": "old_sheet",
            }
        ]
    )
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
            return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ingredients_status",
            return_value={"ready": True},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ensure_identity_sheet",
            return_value={"id": "sheet_new", "source_asset_ids": ["hero"], "image_asset_id": "img"},
        ),
    ):
        apply_character_identity(MagicMock(), request, batch, adapter_id="ltx-local")
    identity_refs = [r for r in batch.references if r.get("kind") == "characterIdentity"]
    assert len(identity_refs) == 1
    assert identity_refs[0]["sheetId"] == "sheet_new"


def test_prior_identity_includes_earlier_batches_only_through_current():
    first = _batch(
        references=[{"kind": "characterIdentity", "identityIds": ["c1"]}],
    )
    second = BatchBlock(
        id="bb_2",
        sceneId="scene",
        references=[{"kind": "characterIdentity", "identityIds": ["c1", "c2"]}],
    )
    third = BatchBlock(id="bb_3", sceneId="scene", references=[])
    assert prior_identity_ids([first, second, third], "bb_2") == {"c1"}
    assert prior_identity_ids([first, second, third], "bb_1") == set()
    assert prior_identity_ids([first, second, third], "bb_3") == {"c1", "c2"}


def test_apply_ignores_non_ltx_generators():
    request = _request(generatorId="seedance-api")
    result = apply_character_identity(
        MagicMock(),
        request,
        _batch(),
        adapter_id="seedance-api",
    )
    assert result == {"ok": True, "applied": False, "reason": "not_ltx"}


def test_apply_ltx_25_uses_start_frame_not_ingredients():
    request = _request(
        generatorId="ltx-local",
        providerOptions={"originalGeneratorId": "ltx-2.5-distilled"},
        startImageAssetId="corridor",
    )
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
            return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ingredients_status",
        ) as ingredients,
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.ensure_identity_sheet",
        ) as ensure,
    ):
        result = apply_character_identity(
            _db_with_images("hero", "corridor"),
            request,
            _batch(),
            adapter_id="ltx-local",
        )
    assert result["ok"] is True
    assert result["applied"] is True
    assert result["method"] == "ltx25_r2v_single_cond"
    assert request.startImageAssetId == "corridor"
    assert request.generationMode == "reference"
    assert request.providerOptions.get("ingredients_ic_lora") is False
    assert request.providerOptions["characterIdentity"]["method"] == "ltx25_r2v_single_cond"
    ingredients.assert_not_called()
    ensure.assert_not_called()


def test_apply_ltx_25_joining_uses_place_not_last_frame():
    request = _request(
        prompt="Korri and Anadriya meet.",
        generatorId="ltx-local",
        providerOptions={"originalGeneratorId": "ltx-2.5-distilled"},
        continuityStrategy="last_frame_i2v",
        lastFrameAssetId="korri_last",
        startImageAssetId="korri_last",
    )
    characters = [
        {"characterId": "c1", "name": "Korri", "assetId": "hero_k"},
        {"characterId": "c2", "name": "Anadriya", "assetId": "hero_a"},
    ]
    scene = MagicMock()
    scene.start_asset_id = "corridor_plate"
    last = MagicMock()
    last.tag = "continuity_last_frame"
    last.kind = "image"
    plate = MagicMock()
    plate.tag = "start_frame"
    plate.kind = "image"
    hero_k = _image_asset("hero_k")
    hero_a = _image_asset("hero_a")
    db = MagicMock()

    def _get(model, key):
        if key == "korri_last":
            return last
        if key == "scene":
            return scene
        if key == "corridor_plate":
            return plate
        if key == "hero_k":
            return hero_k
        if key == "hero_a":
            return hero_a
        return None

    db.get.side_effect = _get
    earlier = BatchBlock(
        id="bb_0",
        sceneId="scene",
        sourceAnchors=[
            TimelineVisualAnchor(kind="image", assetId="corridor_plate", label="Start frame")
        ],
    )
    with patch(
        "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
        return_value={
            "characters": characters,
            "missing": [],
            "mentioned": ["Korri", "Anadriya"],
        },
    ):
        result = apply_character_identity(
            db,
            request,
            _batch(),
            adapter_id="ltx-local",
            prior_identity={"c1"},
            batches=[earlier, _batch()],
        )
    assert result["applied"] is True
    assert request.startImageAssetId == "corridor_plate"
    assert request.continuityStrategy == "prompt_context"
    assert request.providerOptions.get("ingredients_ic_lora") is False


def test_apply_h3_i2v_binds_start_from_hero():
    request = _request(
        generatorId="minimax-h3-i2v-local",
        startImageAssetId=None,
        providerOptions={"originalGeneratorId": "minimax-h3-i2v-local"},
    )
    characters = [{"characterId": "c1", "name": "Korri", "assetId": "hero"}]
    with patch(
        "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
        return_value={"characters": characters, "missing": [], "mentioned": ["Korri"]},
    ):
        result = apply_character_identity(
            _db_with_images("hero"),
            request,
            _batch(),
            adapter_id="minimax-h3-i2v-local",
        )
    assert result["ok"] is True
    assert result["method"] == "h3_ref2va"
    assert request.startImageAssetId == "hero"
    assert request.generationMode == "reference"


def test_apply_h3_same_cast_does_not_treat_last_frame_as_place():
    request = _request(
        prompt="Korri and Anadriya keep walking.",
        generatorId="minimax-h3",
        providerOptions={"originalGeneratorId": "minimax-h3"},
        lastFrameAssetId="cbr_last",
        startImageAssetId="cbr_last",
    )
    characters = [
        {"characterId": "c1", "name": "Korri", "assetId": "hero_k"},
        {"characterId": "c2", "name": "Anadriya", "assetId": "hero_a"},
    ]
    last = MagicMock()
    last.tag = "continuity_last_frame"
    last.kind = "image"
    plate = MagicMock()
    plate.tag = "start_frame"
    plate.kind = "image"
    hero_k = _image_asset("hero_k")
    hero_a = _image_asset("hero_a")
    db = MagicMock()

    def _get(model, key):
        if key == "cbr_last":
            return last
        if key == "corridor":
            return plate
        if key == "hero_k":
            return hero_k
        if key == "hero_a":
            return hero_a
        return None

    db.get.side_effect = _get
    batch = _batch(
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="corridor", label="Place")]
    )
    with patch(
        "app.director_timeline_w46.generation.character_identity_bind.resolve_shot_characters",
        return_value={
            "characters": characters,
            "missing": [],
            "mentioned": ["Korri", "Anadriya"],
        },
    ):
        result = apply_character_identity(
            db,
            request,
            batch,
            adapter_id="minimax-h3-t2v-local",
            prior_identity={"c1", "c2"},
            batches=[batch],
        )
    assert result["ok"] is True
    assert result["applied"] is True
    assert request.startImageAssetId == "corridor"
    assert request.lastFrameAssetId == "cbr_last"
    slots = ((request.providerOptions or {}).get("r2v") or {}).get("slots") or []
    prior = next(slot for slot in slots if slot.get("assetId") == "cbr_last")
    assert prior.get("role") == "prior_frame"
    assert prior.get("pictureIndex") is not None
    assert not any(slot.get("role") == "place" and slot.get("assetId") == "cbr_last" for slot in slots)

def test_resolve_shot_h3_prefers_front_over_crs():
    """J10: MiniMax H3 prefer_front uses hero_identity, not multi-panel CRS."""
    db = _db_with_images("crs_korri", "hero_front")
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            return_value={
                "character_id": "char_korri",
                "name": "Korri",
                "approved_sheet_asset_id": "crs_korri",
            },
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "hero_front" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "hero_front" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
    ):
        shot = resolve_shot_characters(
            db, "proj", ["Korri walks the corridor."], prefer_front=True
        )
    assert shot["missing"] == []
    assert shot["characters"][0]["assetId"] == "hero_front"
    assert shot["characters"][0].get("identityForm") == "front"


def test_resolve_shot_h3_crs_only_warns_not_blocks():
    """J10: CRS-only keeps sheet for experiments but marks crs_only warning."""
    db = _db_with_images("crs_korri")
    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            return_value={
                "character_id": "char_korri",
                "name": "Korri",
                "approved_sheet_asset_id": "crs_korri",
            },
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
    ):
        shot = resolve_shot_characters(
            db, "proj", ["Korri walks the corridor."], prefer_front=True
        )
    assert len(shot["characters"]) == 1
    assert shot["characters"][0]["assetId"] == "crs_korri"
    assert "Korri" in shot["crs_only"]


def test_apply_h3_front_identity_keeps_crs_by_default():
    """Default: creator CRS assetId stays; no silent Front remap."""
    from app.director_timeline_w46.generation.h3_front_identity import (
        apply_h3_front_identity_to_r2v_slots,
    )

    db = _db_with_images("crs_korri", "hero_front")
    slots = [
        {
            "role": "character",
            "assetId": "crs_korri",
            "identityId": "char_korri",
            "label": "Korri",
            "pictureIndex": 1,
        },
        {"role": "place", "assetId": "place1", "label": "Hall", "pictureIndex": 2},
    ]
    with (
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "hero_front" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
    ):
        result = apply_h3_front_identity_to_r2v_slots(db, "proj", slots)
    assert result["ok"] is True
    assert result["policy"] == "creator_crs_authority"
    assert result["replaced"] == []
    assert slots[0]["assetId"] == "crs_korri"
    assert "replacedCrsAssetId" not in slots[0]
    assert slots[0]["identityForm"] == "reference_sheet"


def test_apply_h3_front_identity_opt_in_remaps_character_slot():
    """prefer_front does not replace a reference sheet with a single Front still."""
    from app.director_timeline_w46.generation.h3_front_identity import (
        apply_h3_front_identity_to_r2v_slots,
    )

    db = _db_with_images("crs_korri", "hero_front")
    slots = [
        {
            "role": "character",
            "assetId": "crs_korri",
            "identityId": "char_korri",
            "label": "Korri",
            "pictureIndex": 1,
        },
        {"role": "place", "assetId": "place1", "label": "Hall", "pictureIndex": 2},
    ]
    with (
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "hero_front" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
    ):
        result = apply_h3_front_identity_to_r2v_slots(
            db, "proj", slots, prefer_front=True
        )
    assert result["ok"] is True
    assert result["policy"] == "prefer_front_over_crs"
    assert slots[0]["assetId"] == "crs_korri"
    assert slots[0]["identityForm"] == "reference_sheet"
    assert "replacedCrsAssetId" not in slots[0]


def test_build_h3_ref2v_quality_has_no_easycache():
    from app.workflows.h3_ref2v_builder import assert_h3_ref2v_graph, build_h3_ref2v

    graph = build_h3_ref2v(
        prompt="test",
        ref_comfy_names=["front.png"],
        filename_prefix="studio/j10",
        length=121,
        fast=False,
    )
    assert_h3_ref2v_graph(graph, expected_names=["front.png"], expect_fast=False)
    assert not any(
        isinstance(n, dict) and n.get("class_type") == "EasyCache" for n in graph.values()
    )

