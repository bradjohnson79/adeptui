"""ORDER 8B: no Batch 1 mint on empty migrate; Owner Batch UX lock; Window labels."""

from __future__ import annotations

import json

import pytest

from app.director_timeline_w46.creator_batch_surface import (
    OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN,
    TIMELINE_BATCHES_CREATOR_UI,
    creator_batch_mutation_blocked,
    default_execution_window_label,
    forbid_creator_batch_first_mint,
    owner_batch_ux_reintroduce_forbidden,
)
from app.director_timeline_w46.migration import migrate_director_to_master


def test_owner_law_aligned_with_fe_flag():
    assert TIMELINE_BATCHES_CREATOR_UI is False
    assert OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN is True
    assert owner_batch_ux_reintroduce_forbidden() is True


def test_migrate_none_leaves_empty_batch_blocks():
    master = migrate_director_to_master(None, scene_id="scene-empty")
    assert master.migratedFromDirectorJson is True
    assert master.batchBlocks == []
    note = master.migrationNote or ""
    assert "no Batch 1 mint" in note or "awaits CD rematerialize" in note
    assert "SceneTake" in note or "rematerialize" in note


def test_migrate_empty_json_leaves_empty_batch_blocks():
    master = migrate_director_to_master("{}", scene_id="scene-empty-json")
    assert master.migratedFromDirectorJson is True
    assert master.batchBlocks == []


def test_migrate_empty_object_string_variants():
    for raw in (None, "", "{}"):
        master = migrate_director_to_master(raw, scene_id="s")
        assert master.batchBlocks == [], f"raw={raw!r} minted {len(master.batchBlocks)} blocks"
        assert master.migratedFromDirectorJson is True


def test_migrate_contentful_uses_window_1_not_batch_1():
    raw = json.dumps(
        {
            "media_mode": "image",
            "duration_sec": 6.0,
            "image_clips": [
                {"id": "img1", "role": "start", "start": 0, "length": 6, "asset_id": "a1"}
            ],
            "prompt_segments": [
                {"id": "p1", "start": 0, "length": 6, "text": "wide shot"}
            ],
            "camera_clips": [],
            "video_clips": [],
            "audio_clips": [],
            "sfx_clips": [],
        }
    )
    master = migrate_director_to_master(raw, scene_id="scene-1")
    assert len(master.batchBlocks) == 1
    assert master.batchBlocks[0].label == "Window 1"
    assert not str(master.batchBlocks[0].label).startswith("Batch ")


def test_never_collapse_existing_multi_batch():
    first = migrate_director_to_master(
        json.dumps(
            {
                "media_mode": "image",
                "duration_sec": 6.0,
                "image_clips": [
                    {"id": "img1", "role": "start", "start": 0, "length": 6, "asset_id": "a1"}
                ],
                "prompt_segments": [
                    {"id": "p1", "start": 0, "length": 6, "text": "a"}
                ],
                "camera_clips": [],
                "video_clips": [],
                "audio_clips": [],
                "sfx_clips": [],
            }
        ),
        scene_id="scene-1",
    )
    # Simulate second block
    from copy import deepcopy

    b0 = first.batchBlocks[0]
    b1 = b0.model_copy(deep=True)
    b1.id = "bb_second"
    b1.order = 1
    b1.label = "Window 2"
    first.batchBlocks = [b0, b1]
    preserved = migrate_director_to_master("{}", scene_id="scene-1", existing=first)
    assert len(preserved.batchBlocks) == 2
    assert preserved.batchBlocks[0].id == b0.id


def test_forbid_creator_batch_first_mint_raises_under_owner_lock():
    with pytest.raises(RuntimeError, match="OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN"):
        forbid_creator_batch_first_mint("unit-test generate default Batch 1")


def test_add_batch_duplicate_still_disabled():
    blocked = creator_batch_mutation_blocked("add_batch")
    assert blocked["ok"] is False
    assert blocked["error"] == "CREATOR_BATCH_MUTATION_DISABLED"
    blocked2 = creator_batch_mutation_blocked("duplicate_batch")
    assert blocked2["error"] == "CREATOR_BATCH_MUTATION_DISABLED"


def test_default_execution_window_label():
    assert default_execution_window_label(0) == "Window 1"
    assert default_execution_window_label(2) == "Window 3"


def test_rematerialize_default_labels_are_windows():
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46.execution_window_materialize import (
        rematerialize_batch_blocks_from_plan,
    )

    master = SceneTimelineMaster(
        version=1,
        mode="video_finishing",
        batchBlocks=[],
        executionSnapshots={},
        migratedFromDirectorJson=True,
    )
    # Force rematerialize with two windows via plan-like windows list
    result = rematerialize_batch_blocks_from_plan(
        master,
        windows=[{"start": 0.0, "end": 5.0}, {"start": 5.0, "end": 10.0}],
        generator_id="gen_test",
        scene_id="scene-win",
        duration_seconds=10.0,
        force=True,
    )
    assert result.get("ok") is True
    labels = [b.label for b in master.batchBlocks]
    assert labels == ["Window 1", "Window 2"]
    assert all(not str(l).startswith("Batch ") for l in labels)
