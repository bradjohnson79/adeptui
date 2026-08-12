"""M42 W46 Director Timeline Master — contracts, migration, snapshots, cancel, overlap."""

from __future__ import annotations

import json

from app.director_timeline import CameraClip, camera_prompt_hint, parse_director_timeline
from app.director_timeline_w46.capabilities import disclose_inpaint_strategy, validate_duration
from app.director_timeline_w46.camera_catalog import classify_camera_capability
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    RepairRange,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.migration import compute_config_fingerprint, migrate_director_to_master
from app.director_timeline_w46.production_gate import evaluate_director_timeline_gate
from app.director_timeline_w46.repair_policy import apply_repair_overlap_policy


def test_batch_block_is_stable_container_not_media_id():
    batch = BatchBlock(sceneId="s1", label="Shot A")
    batch_id = batch.id
    batch.approvedClip = None
    # Changing approved media pointer must not change Batch ID
    from app.director_timeline_w46.contracts import ApprovedClip

    batch.approvedClip = ApprovedClip(assetId="asset-1", executionSnapshotId="snap-1")
    assert batch.id == batch_id
    batch.approvedClip = ApprovedClip(assetId="asset-2", executionSnapshotId="snap-2")
    assert batch.id == batch_id


def test_duration_state_separation():
    d = DurationState(
        plannedDuration=8.0,
        generatedDuration=7.2,
        timelineVisibleDuration=7.2,
        sourceMediaDuration=7.2,
    )
    assert d.plannedDuration != d.generatedDuration
    assert d.timelineVisibleDuration == d.generatedDuration


def test_execution_snapshot_immutable_flag():
    snap = ExecutionSnapshot(batchBlockId="bb1", compiledPrompts={"text": "hello"})
    assert snap.immutable is True
    dumped = snap.model_dump()
    assert dumped["immutable"] is True


def test_migration_idempotent_from_director_json():
    director = {
        "media_mode": "image",
        "duration_sec": 6.0,
        "image_clips": [{"id": "img1", "role": "start", "start": 0, "length": 6, "asset_id": "a1"}],
        "prompt_segments": [{"id": "p1", "start": 0, "length": 6, "text": "wide shot"}],
        "camera_clips": [],
        "video_clips": [],
        "audio_clips": [],
        "sfx_clips": [],
    }
    raw = json.dumps(director)
    m1 = migrate_director_to_master(raw, scene_id="scene-1")
    assert m1.migratedFromDirectorJson is True
    assert len(m1.batchBlocks) == 1
    assert m1.batchBlocks[0].promptSegments[0].text == "wide shot"
    m2 = migrate_director_to_master(raw, scene_id="scene-1", existing=m1)
    assert m2.batchBlocks[0].id == m1.batchBlocks[0].id


def test_repair_overlap_blocked_by_default():
    existing = [RepairRange(start=0.0, length=2.0, label="A")]
    incoming = RepairRange(start=1.0, length=2.0, label="B")
    decision = apply_repair_overlap_policy(existing, incoming, policy="block")
    assert decision.ok is False
    assert decision.blocked is True


def test_repair_overlap_merge_and_stack():
    existing = [RepairRange(start=0.0, length=2.0, label="A")]
    incoming = RepairRange(start=1.0, length=2.0, label="B")
    merged = apply_repair_overlap_policy(existing, incoming, policy="merge")
    assert merged.ok and merged.merged
    stacked = apply_repair_overlap_policy(existing, incoming, policy="stack_advanced")
    assert stacked.ok and stacked.stacked
    assert max(r.layer for r in stacked.ranges) >= 1


def test_native_inpaint_disclosed_not_faked():
    result = disclose_inpaint_strategy("ltx-local", "native")
    assert result["disclosed"] is True
    assert result["strategy"] != "native"


def test_duration_no_silent_truncate():
    result = validate_duration("ltx-local", 30.0)
    assert result["ok"] is False
    assert "split" in result["options"]


def test_invalidation_fingerprint_changes():
    batch = BatchBlock(
        sceneId="s1",
        duration=DurationState(plannedDuration=5),
        promptSegments=[TimelinePromptSegment(text="one", length=5)],
    )
    fp1 = compute_config_fingerprint(batch)
    batch.promptSegments[0].text = "two"
    fp2 = compute_config_fingerprint(batch)
    assert fp1 != fp2


def test_gate_returns_binary_structure():
    gate = evaluate_director_timeline_gate()
    assert gate["mock"] is False
    assert "directorTimelineGo" in gate
    assert gate["verdict"] in ("GO", "NO-GO")
    assert gate["productionDockGoUnchanged"] is True
    assert "executionSnapshotPassed" in gate["flags"]
    assert "dockSingleRowPassed" in gate["flags"]


def test_camera_clip_parse_stays_backward_compatible():
    raw = json.dumps(
        {
            "media_mode": "image",
            "duration_sec": 5.0,
            "image_clips": [],
            "video_clips": [],
            "prompt_segments": [],
            "audio_clips": [],
            "sfx_clips": [],
            "camera_clips": [
                {
                    "id": "cam1",
                    "start": 0.0,
                    "length": 2.0,
                    "motion_type": "static",
                    "rig": "tripod",
                    "speed": 0.2,
                }
            ],
        }
    )
    timeline = parse_director_timeline(raw)
    assert len(timeline.camera_clips) == 1
    clip = timeline.camera_clips[0]
    assert clip.motion_type == "static"
    assert clip.rig == "tripod"
    assert clip.motion_id is None
    assert clip.rig_id is None
    assert clip.execution_strategy is None


def test_camera_prompt_hint_uses_catalog_labels():
    clip = CameraClip(
        motion_type="static",
        rig="tripod",
        motion_id="locked_off",
        rig_id="tripod",
        speed=0.0,
        distance=1.0,
        intensity=0.1,
        subject_lock=0.95,
    )
    hint = camera_prompt_hint([clip])
    assert "Locked Off on Tripod" in hint
    assert "subject lock 0.95" in hint
    assert classify_camera_capability(motion_id="locked_off", rig_id="tripod") == "Workflow-Mapped"
