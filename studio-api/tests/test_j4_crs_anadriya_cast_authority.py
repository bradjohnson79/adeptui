"""J4 regression: Spatial Map Anadriya must not expand CRS cast when unbound."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.director_timeline_w46.contracts import BatchBlock
from app.director_timeline_w46.generation.character_identity_bind import (
    _restrict_to_creator_bound_cast,
    _strip_continuity_boilerplate,
    apply_character_identity,
    mentioned_character_names,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation import request_builder as rb


CONTAMINATED = """UNCHANGED FACTS: environment, cameras, ERS
STARTING STATE (M1): beat PRIMARY Beat
ENDING STATE (M1): beat PRIMARY Beat
ACTION / DIRECTION: PRIMARY Direction — Anadriya keeps walking.
DIALOGUE: Anadriya: PRIMARY line
TIMED PROMPT: @Korri40YearsOld and @Addex stand facing each other.
@Korri40YearsOld and @Addex stand facing each other in a quiet sunlit room."""


def test_strip_continuity_boilerplate_removes_anadriya_action():
    cleaned = _strip_continuity_boilerplate(CONTAMINATED)
    assert "Anadriya" not in cleaned
    assert "@Korri40YearsOld" in cleaned
    assert "@Addex" in cleaned


def test_mentioned_names_do_not_expand_from_movement_boilerplate():
    cleaned = _strip_continuity_boilerplate(CONTAMINATED)
    names = mentioned_character_names(cleaned, ["Korri", "Addex", "Anadriya", "Korri40YearsOld"])
    lower = {n.lower() for n in names}
    assert "anadriya" not in lower
    assert "korri40yearsold" in lower or "korri" in lower
    assert "addex" in lower


def test_restrict_drops_unbound_spatial_cast_when_bindings_exist():
    shot = {
        "characters": [
            {"characterId": "char_korri", "name": "Korri", "assetId": "a"},
            {"characterId": "char_addex", "name": "Addex", "assetId": "b"},
            {"characterId": "char_ana", "name": "Anadriya", "assetId": "c"},
        ],
        "missing": [],
        "mentioned": ["Korri", "Addex", "Anadriya"],
    }
    bound = [
        {
            "kind": "image",
            "role": "character",
            "identityId": "char_korri",
            "assetId": "a",
            "consumed": True,
        },
        {
            "kind": "image",
            "role": "character",
            "identityId": "char_addex",
            "assetId": "b",
            "consumed": True,
        },
    ]
    out = _restrict_to_creator_bound_cast(shot, bound, ["@Korri40YearsOld and @Addex"])
    ids = {c["characterId"] for c in out["characters"]}
    assert ids == {"char_korri", "char_addex"}
    assert "char_ana" not in ids


def test_compile_movement_layers_skips_active_segment_without_binding():
    """movementSegmentRef null + no ~M alias => no Spatial Map cast injection."""

    class Doc:
        pass

    class FakeSession:
        def close(self):
            return None

    batch = BatchBlock(
        id="bb",
        sceneId="sc",
        promptSegments=[
            {
                "id": "ps1",
                "start": 0,
                "length": 12,
                "text": "@Korri40YearsOld and @Addex stand facing each other.",
                "movementSegmentRef": None,
            }
        ],
    )
    with patch("app.db.SessionLocal", return_value=FakeSession()), patch(
        "app.spatial_map.service.list_documents", return_value=[Doc()]
    ), patch(
        "app.spatial_map.movement.hydrate_movement_segments", return_value=None
    ), patch(
        "app.spatial_map.movement.active_segment"
    ) as active:
        result = rb._compile_movement_layers("proj", batch)
    assert result == {}
    assert active.call_count == 0


def test_apply_h3_ignores_anadriya_in_contaminated_prompt():
    request = TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene",
        batchBlockId="bb_1",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt=CONTAMINATED,
        providerOptions={
            "originalGeneratorId": "minimax-h3",
            "authoredPrompt": "@Korri40YearsOld and @Addex stand facing each other.",
        },
    )
    batch = BatchBlock(
        id="bb_1",
        sceneId="scene",
        promptSegments=[
            {
                "id": "ps1",
                "start": 0,
                "length": 12,
                "text": "@Korri40YearsOld and @Addex stand facing each other.",
                "userDirection": "@Korri40YearsOld and @Addex stand facing each other.",
                "referenceNameBindings": [
                    {"tag": "@Korri40YearsOld", "prompt_name": "Korri-40-years-old"},
                    {"tag": "@Addex", "prompt_name": "Addex"},
                ],
            }
        ],
        references=[
            {
                "kind": "image",
                "role": "character",
                "assetId": "crs_korri",
                "identityId": "char_korri",
                "label": "Korri40YearsOld",
                "tag": "@Korri40YearsOld",
                "consumed": True,
            },
            {
                "kind": "image",
                "role": "character",
                "assetId": "crs_addex",
                "identityId": "char_addex",
                "label": "Addex",
                "tag": "@Addex",
                "consumed": True,
            },
        ],
    )

    def _resolve(_db, _pid, name):
        key = (name or "").lower()
        if "korri" in key:
            return {
                "character_id": "char_korri",
                "name": "Korri",
                "approved_sheet_asset_id": "crs_korri",
            }
        if "addex" in key:
            return {
                "character_id": "char_addex",
                "name": "Addex",
                "approved_sheet_asset_id": "crs_addex",
            }
        if "anadriya" in key:
            return {
                "character_id": "char_ana",
                "name": "Anadriya",
                "approved_sheet_asset_id": "crs_ana",
            }
        return None

    db = MagicMock()
    captured = {}

    def _apply(db, request, batch, **kwargs):
        captured["characters"] = kwargs.get("characters")
        return {
            "ok": True,
            "applied": True,
            "method": "h3_ref2va",
            "characters": kwargs.get("characters"),
        }

    with (
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._known_names",
            return_value=["Korri", "Addex", "Anadriya"],
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind.resolve_character",
            side_effect=_resolve,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._asset_is_image",
            return_value=True,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._appearance_from_profile",
            return_value="",
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._drop_front_still_character_refs",
            return_value=None,
        ),
        patch(
            "app.director_timeline_w46.generation.character_identity_bind._apply_i2v_start_identity",
            side_effect=_apply,
        ),
    ):
        result = apply_character_identity(db, request, batch, adapter_id="minimax-h3-t2v-local")

    assert result.get("ok") is True
    names = [c["name"] for c in (captured.get("characters") or [])]
    assert "Anadriya" not in names
    assert "Korri" in names
    assert "Addex" in names
