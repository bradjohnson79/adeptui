"""Contract: Timeline Reference @tag is CRS authority for missing-sheet warning."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.director_timeline_w46.generation.character_identity_bind import (
    _crs_authority_bound_assets,
    _match_bound_character_sheet_by_tag,
    apply_character_identity,
    resolve_shot_characters,
)
from app.director_timeline_w46.contracts import BatchBlock
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest


def _image_asset(asset_id: str = "img", project_id: str = "proj"):
    asset = MagicMock()
    asset.id = asset_id
    asset.kind = "image"
    asset.project_id = project_id
    return asset


def _db_with_images(*asset_ids: str, project_id: str = "proj"):
    db = MagicMock()
    catalog = {aid: _image_asset(aid, project_id) for aid in asset_ids}

    def _get(_model, key):
        return catalog.get(str(key))

    db.get.side_effect = _get
    return db


def test_match_bound_character_sheet_by_alias_tag():
    bound = [
        {
            "kind": "image",
            "role": "character",
            "assetId": "crs_korri40",
            "identityId": "char_korri",
            "label": "Korri40YearsOld",
            "tag": "@Korri40YearsOld",
            "promptName": "Korri40YearsOld",
            "consumed": True,
        }
    ]
    hit = _match_bound_character_sheet_by_tag("Korri40YearsOld", bound)
    assert hit is not None
    assert hit["assetId"] == "crs_korri40"


def test_crs_authority_includes_unconsumed_entity_character_refs():
    refs = [
        {
            "kind": "entity",
            "role": "entity_reference",
            "assetId": "crs_korri40",
            "identityId": "char_korri",
            "alias": "Korri40YearsOld",
            "consumed": False,
            "referenceType": "character",
        },
        {
            "kind": "image",
            "role": "place",
            "assetId": "ers_room",
            "consumed": False,
        },
    ]
    auth = _crs_authority_bound_assets(refs)
    assert len(auth) == 1
    assert auth[0]["assetId"] == "crs_korri40"


def test_tagged_and_bound_reference_clears_missing_crs_warning():
    """@Korri40YearsOld bound as Timeline Character sheet must not be missing.

    Profile name may be \"Korri\" — Reference alias is the CRS tag authority.
    """
    db = _db_with_images("crs_korri40", "crs_addex")
    bound = [
        {
            "kind": "image",
            "role": "character",
            "assetId": "crs_korri40",
            "identityId": "char_korri",
            "label": "Korri40YearsOld",
            "tag": "@Korri40YearsOld",
            "promptName": "Korri40YearsOld",
            "consumed": True,
        },
        {
            "kind": "image",
            "role": "character",
            "assetId": "crs_addex",
            "identityId": "char_addex",
            "label": "Addex",
            "tag": "@Addex",
            "promptName": "Addex",
            "consumed": True,
        },
    ]

    def _resolve(_db, _pid, name):
        # Alias does not match profile name — this is the bug failure mode.
        if name == "Addex":
            return {
                "character_id": "char_addex",
                "name": "Addex",
                "approved_sheet_asset_id": "crs_addex",
            }
        if name == "Korri":
            return {
                "character_id": "char_korri",
                "name": "Korri",
                "approved_sheet_asset_id": "crs_korri40",
            }
        return None  # Korri40YearsOld would miss without Timeline Reference authority

    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri", "Addex"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            side_effect=_resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.get_profile",
            side_effect=lambda _db, _pid, cid: MagicMock(name="Korri")
            if cid == "char_korri"
            else MagicMock(name="Addex"),
        ),
    ):
        # get_profile returns MagicMock; name attribute access needs care
        shot = resolve_shot_characters(
            db,
            "proj",
            ["@Korri40YearsOld and @Addex enter the room."],
            prefer_sheet=True,
            bound_assets=bound,
        )
    assert shot["missing"] == []
    names = {c["name"] for c in shot["characters"]}
    assert "Addex" in names
    # Bound identity resolves; display may be profile name or alias
    assert any(c["assetId"] == "crs_korri40" for c in shot["characters"])
    assert any(c["assetId"] == "crs_addex" for c in shot["characters"])


def test_tagged_unbound_still_warns_honestly():
    """@Korri40YearsOld with no Timeline Character binding remains missing."""
    db = _db_with_images("crs_addex")

    def _resolve(_db, _pid, name):
        if name == "Addex":
            return {
                "character_id": "char_addex",
                "name": "Addex",
                "approved_sheet_asset_id": "crs_addex",
            }
        return None

    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri", "Addex"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            side_effect=_resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
    ):
        shot = resolve_shot_characters(
            db,
            "proj",
            ["@Korri40YearsOld and @Addex enter the room."],
            prefer_sheet=True,
            bound_assets=[
                {
                    "kind": "image",
                    "role": "character",
                    "assetId": "crs_addex",
                    "identityId": "char_addex",
                    "label": "Addex",
                    "tag": "@Addex",
                    "consumed": True,
                }
            ],
        )
    assert "Korri40YearsOld" in shot["missing"]
    assert any(c["name"] == "Addex" for c in shot["characters"])


def test_apply_character_identity_bound_alias_tag_does_not_block():
    request = TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene",
        batchBlockId="bb_1",
        executionSnapshotId="snap",
        generatorId="ltx-2.5-full",
        prompt="@Korri40YearsOld walks in.",
        providerOptions={"originalGeneratorId": "ltx-2.5-full"},
    )
    batch = BatchBlock(
        id="bb_1",
        sceneId="scene",
        references=[
            {
                "kind": "image",
                "role": "character",
                "assetId": "crs_korri40",
                "identityId": "char_korri",
                "label": "Korri40YearsOld",
                "tag": "@Korri40YearsOld",
                "promptName": "Korri40YearsOld",
                "consumed": True,
                "source": "prompt_clip",
            }
        ],
    )
    db = _db_with_images("crs_korri40")

    def _resolve(_db, _pid, name):
        return None  # alias != profile name

    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            side_effect=_resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.get_profile",
            return_value=MagicMock(**{"name": "Korri"}),
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._drop_front_still_character_refs",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._apply_i2v_start_identity",
            return_value={"ok": True, "applied": True, "method": "ltx25_r2v_single_cond"},
        ) as apply_i2v,
    ):
        # get_profile MagicMock name= sets mock name not attribute — use configure
        result = apply_character_identity(db, request, batch, adapter_id="ltx-local")
    assert result.get("ok") is True
    assert result.get("error") != "CHARACTER_IDENTITY_MISSING"
    assert apply_i2v.called


def test_apply_character_identity_unbound_tag_still_blocks():
    request = TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene",
        batchBlockId="bb_1",
        executionSnapshotId="snap",
        generatorId="ltx-2.5-full",
        prompt="@Korri40YearsOld walks in.",
        providerOptions={"originalGeneratorId": "ltx-2.5-full"},
    )
    batch = BatchBlock(id="bb_1", sceneId="scene", references=[])
    db = _db_with_images()

    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_approved_reference",
            return_value=None,
        ),
    ):
        result = apply_character_identity(db, request, batch, adapter_id="ltx-local")
    assert result["ok"] is False
    assert result["error"] == "CHARACTER_IDENTITY_MISSING"
    assert "Korri40YearsOld" in result["message"]
    assert "Character Reference Sheet" in result["message"]
