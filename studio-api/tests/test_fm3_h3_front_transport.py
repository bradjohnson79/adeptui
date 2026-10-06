"""FM3: H3 Front-only transport packing (Brad GO).

When Character Creator Front exists, Timeline H3 packs Front into ref_image_N
instead of multi-panel CRS-alone. Plain Front bytes; no CRS crop; no place invent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
from app.director_timeline_w46.generation.direct_reference import build_direct_reference_payload
from app.director_timeline_w46.generation.h3_front_identity import (
    apply_h3_front_identity_to_request,
    apply_h3_front_identity_to_r2v_slots,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest


class _Asset:
    def __init__(self, asset_id: str, *, kind: str = "image", filename: str = "", path: str = ""):
        self.id = asset_id
        self.kind = kind
        self.filename = filename or f"{asset_id}.png"
        self.path = path or f"C:/library/{asset_id}.png"
        self.project_id = "proj"
        self.comfy_name = None


class _Db:
    def __init__(self, assets: dict[str, _Asset]):
        self._assets = assets

    def get(self, model, key):  # noqa: ANN001
        return self._assets.get(str(key))


def _batch(binding_ids: list[str]) -> BatchBlock:
    return BatchBlock(
        sceneId="scene-korri",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                text="<subject 1> is Korri. Korri sits for an interview.",
                start=0,
                length=5,
                referenceBindingIds=binding_ids,
            )
        ],
    )


def test_dr_h3_front_transport_packs_front_over_crs():
    """A checked reference sheet stays the Load Image file. It is not swapped for Front."""
    db = _Db(
        {
            "crs_korri": _Asset("crs_korri", filename="Korri 40 years old.jpeg"),
            "front_korri": _Asset("front_korri", filename="Korri-Addex.jpeg"),
        }
    )

    def resolve(_db, _project_id, binding_id):
        return {
            "bindingId": binding_id,
            "assetId": "crs_korri",
            "identityId": "char_korri",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "Korri40YearsOld",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        }

    with (
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_binding_id",
            side_effect=resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_library_source",
            side_effect=lambda asset: str(asset.path),
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "front_korri" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity._asset_is_image",
            return_value=True,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity._is_front_still_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "front_korri",
        ),
    ):
        payload = build_direct_reference_payload(
            db,
            project_id="proj",
            scene_id="scene-korri",
            batch=_batch(["bind-korri"]),
            generator_id="minimax-h3",
        )

    assert len(payload.characters) == 1
    assert payload.characters[0].assetId == "crs_korri"
    assert payload.characters[0].identityForm == "reference_sheet"
    assert payload.sockets[0].socket == "ref_image_0"
    assert payload.sockets[0].assetId == "crs_korri"
    assert payload.blocked == []


def test_dr_h3_front_transport_keeps_crs_when_no_front():
    """DR packing: CRS checked + no Front -> CRS stays (crs_sheet_only)."""
    db = _Db({"crs_korri": _Asset("crs_korri", filename="Korri 40 years old.jpeg")})

    def resolve(_db, _project_id, binding_id):
        return {
            "bindingId": binding_id,
            "assetId": "crs_korri",
            "identityId": "char_korri",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "Korri40YearsOld",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        }

    with (
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_binding_id",
            side_effect=resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_library_source",
            side_effect=lambda asset: str(asset.path),
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity._asset_is_image",
            return_value=True,
        ),
    ):
        payload = build_direct_reference_payload(
            db,
            project_id="proj",
            scene_id="scene-korri",
            batch=_batch(["bind-korri"]),
            generator_id="minimax-h3",
        )

    assert payload.characters[0].assetId == "crs_korri"
    assert payload.characters[0].checkedAssetId is None
    assert payload.characters[0].identityForm == "reference_sheet"
    assert payload.sockets[0].assetId == "crs_korri"


def test_dr_h3_keeps_creator_attached_front_without_swap():
    """Creator already checked Front still — do not invent a second Front."""
    db = _Db({"front_korri": _Asset("front_korri", filename="Korri Front.png")})

    def resolve(_db, _project_id, binding_id):
        return {
            "bindingId": binding_id,
            "assetId": "front_korri",
            "identityId": "char_korri",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "KorriFront",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        }

    with (
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_binding_id",
            side_effect=resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.direct_reference.resolve_library_source",
            side_effect=lambda asset: str(asset.path),
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            return_value=False,
        ),
    ):
        payload = build_direct_reference_payload(
            db,
            project_id="proj",
            scene_id="scene-korri",
            batch=_batch(["bind-front"]),
            generator_id="minimax-h3",
        )

    assert payload.characters[0].assetId == "front_korri"
    assert payload.characters[0].identityForm == "creator_attached"


def test_apply_h3_front_transport_packs_slot_by_default_on_request():
    """Request path keeps the reference sheet on the slot. Load Image gets the whole file."""
    db = _Db(
        {
            "crs_korri": _Asset("crs_korri", filename="Korri 40 years old.jpeg"),
            "front_korri": _Asset("front_korri", filename="Korri-Addex.jpeg"),
        }
    )
    req = TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene-korri",
        batchBlockId="bb_test",
        executionSnapshotId="snap_test",
        generatorId="minimax-h3",
        prompt="<subject 1> is Korri.",
        duration=5.0,
        providerOptions={
            "r2v": {
                "slots": [
                    {
                        "role": "character",
                        "assetId": "crs_korri",
                        "identityId": "char_korri",
                        "label": "Korri",
                        "pictureIndex": 1,
                    }
                ]
            }
        },
    )
    with (
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "front_korri" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity._asset_is_image",
            return_value=True,
        ),
    ):
        result = apply_h3_front_identity_to_request(db, req)

    assert result["policy"] == "h3_front_transport"
    slots = ((req.providerOptions or {}).get("r2v") or {}).get("slots") or []
    assert slots[0]["assetId"] == "crs_korri"
    assert slots[0]["identityForm"] == "reference_sheet"
    assert "replacedCrsAssetId" not in slots[0]


def test_apply_h3_front_transport_opt_out_keeps_crs():
    """h3CreatorCrsAuthority / front_transport=False keeps CRS (no pack)."""
    db = _Db(
        {
            "crs_korri": _Asset("crs_korri", filename="Korri 40 years old.jpeg"),
            "front_korri": _Asset("front_korri", filename="Korri-Addex.jpeg"),
        }
    )
    slots = [
        {
            "role": "character",
            "assetId": "crs_korri",
            "identityId": "char_korri",
            "label": "Korri",
            "pictureIndex": 1,
        }
    ]
    with (
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.resolve_approved_reference",
            side_effect=lambda _db, _cid, role: "front_korri" if role == "hero_identity" else None,
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity.is_multi_panel_crs_asset",
            side_effect=lambda _db, _pid, aid: str(aid) == "crs_korri",
        ),
        patch(
            "app.director_timeline_w46.generation.h3_front_identity._asset_is_image",
            return_value=True,
        ),
    ):
        result = apply_h3_front_identity_to_r2v_slots(
            db, "proj", slots, prefer_front=False, front_transport=False
        )
    assert result["policy"] == "creator_crs_authority"
    assert slots[0]["assetId"] == "crs_korri"
    assert slots[0]["identityForm"] == "reference_sheet"


def test_side_angle_slot_uses_approved_front_not_the_adopt():
    """Cade's review side adopt must not be the H3 picture when Front is approved."""
    side = _Asset("side_cade", filename="cade-side-cd-adopt.png")
    side.tag = "cade-side-cd-adopt"
    side.labels_json = '["character_angle", "side", "uploaded"]'
    front = _Asset("front_cade", filename="Cade Front.png")
    front.tag = "character_reference"
    front.labels_json = "[]"
    korri = _Asset("front_korri", filename="Korri Front.png")
    korri.tag = "character_reference"
    korri.labels_json = "[]"

    class _Row:
        def __init__(self, profile, asset, role, canonical, status):
            self.character_profile_id = profile
            self.asset_id = asset
            self.reference_role = role
            self.canonical = canonical
            self.approval_status = status

    rows = [
        _Row("char_cade", "side_cade", "hero_identity", False, "review"),
        _Row("char_cade", "front_cade", "hero_identity", True, "approved"),
    ]

    class _Query:
        def __init__(self, found):
            self._found = found

        def filter(self, *exprs, **_kwargs):
            found = list(self._found)
            for expr in exprs:
                try:
                    key = expr.left.key
                    value = expr.right.value
                except Exception:
                    continue
                found = [row for row in found if getattr(row, key, None) == value]
            return _Query(found)

        def all(self):
            return self._found

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._found[0] if self._found else None

    class _AngleDb(_Db):
        def query(self, _model):
            return _Query(rows)

    db = _AngleDb({"side_cade": side, "front_cade": front, "front_korri": korri})
    slots = [
        {"role": "character", "assetId": "front_korri", "identityId": None, "label": "@Korri", "pictureIndex": 1},
        {"role": "character", "assetId": "side_cade", "identityId": None, "label": "@CadeOConnor", "pictureIndex": 2},
    ]
    apply_h3_front_identity_to_r2v_slots(db, "proj", slots, front_transport=True)
    assert slots[0]["assetId"] == "front_korri"
    assert slots[1]["assetId"] == "front_cade"
    assert slots[1]["identityId"] == "char_cade"
    assert slots[1]["replacedCrsAssetId"] == "side_cade"


def test_front_still_is_replaced_by_the_whole_reference_sheet():
    """Load Image must receive the approved sheet, not the cropped Front still."""
    front = _Asset("front_cade", filename="Cade Front.png")
    front.tag = "character_reference"
    sheet = _Asset("sheet_cade", filename="character_sheet_cade.png")
    sheet.tag = "character_sheet"
    sheet.labels_json = '["character_sheet", "composed"]'
    db = _Db({"front_cade": front, "sheet_cade": sheet})
    slots = [
        {
            "role": "character",
            "assetId": "front_cade",
            "identityId": "char_cade",
            "label": "@CadeOConnor",
            "pictureIndex": 1,
        }
    ]
    with patch(
        "app.character_identity.crs_service.load_persisted_crs",
        return_value={"approved_sheet_asset_id": "sheet_cade"},
    ):
        apply_h3_front_identity_to_r2v_slots(db, "proj", slots, front_transport=True)
    assert slots[0]["assetId"] == "sheet_cade"
    assert slots[0]["identityForm"] == "reference_sheet"
    assert slots[0]["replacedCropAssetId"] == "front_cade"


