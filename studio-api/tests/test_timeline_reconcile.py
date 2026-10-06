"""Timeline reconciliation tests — legacy NLE view <-> Timeline Master.

Covers the Timeline final-certification prompt/image sync contract:
- Timed Prompt lane edits reach batch.promptSegments (generation input).
- userDirection is stored separately from text and never clobbers refinement.
- Deletion propagates from the lane into the batch.
- Wave 3A: Visual image_clips do not silently inject sourceAnchors; stale
  managed legacy anchors are still cleaned; explicit Start/End survive.
- Batch-side prompt edits project back to the legacy lane (single truth).
- Value-stability: reconciling consistent state mutates nothing (fingerprint
  and staged snapshots never churn).
"""

from __future__ import annotations

import pytest

from app.director_timeline import DirectorTimeline, PromptSegment
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.migration_reconcile import (
    project_prompts_to_legacy,
    reconcile_legacy_to_master,
)
from app.director_timeline_w46.reconcile import (
    batch_time_windows,
    reconcile_legacy_cameras,
    reconcile_legacy_image_anchors,
    reconcile_legacy_prompts,
)


def _master_with_batches(durations: list[float]) -> SceneTimelineMaster:
    master = SceneTimelineMaster()
    for i, dur in enumerate(durations):
        master.batchBlocks.append(
            BatchBlock(
                id=f"bb_test_{i}",
                sceneId="sc_test",
                order=i,
                label=f"Batch {i + 1}",
                duration=DurationState(plannedDuration=dur),
            )
        )
    return master


def _legacy_prompt(pid: str, start: float, length: float, text: str, **kw) -> PromptSegment:
    return PromptSegment(id=pid, start=start, length=length, text=text, **kw)


def test_lane_prompt_reaches_batch_prompt_segments():
    master = _master_with_batches([5.0, 5.0])
    legacy = [_legacy_prompt("leg_a", 1.0, 3.0, "Woman walks toward camera.")]
    changed = reconcile_legacy_prompts(master, legacy)
    assert changed is True
    batch = master.batchBlocks[0]
    assert len(batch.promptSegments) == 1
    seg = batch.promptSegments[0]
    assert seg.text == "Woman walks toward camera."
    assert seg.legacyPromptSegmentId == "leg_a"
    assert seg.userDirection == "Woman walks toward camera."
    assert seg.start == 1.0
    assert seg.length == 3.0
    # Batch 2 untouched (window isolation)
    assert master.batchBlocks[1].promptSegments == []


def test_second_batch_window_mapping():
    master = _master_with_batches([5.0, 5.0])
    legacy = [
        _legacy_prompt("leg_a", 0.0, 5.0, "Shot one."),
        _legacy_prompt("leg_b", 5.0, 5.0, "Shot two."),
    ]
    reconcile_legacy_prompts(master, legacy)
    assert master.batchBlocks[0].promptSegments[0].text == "Shot one."
    assert master.batchBlocks[1].promptSegments[0].text == "Shot two."


def test_reconcile_is_value_stable():
    master = _master_with_batches([5.0])
    legacy = [_legacy_prompt("leg_a", 0.0, 5.0, "Stable text.")]
    assert reconcile_legacy_prompts(master, legacy) is True
    before = master.model_dump()
    assert reconcile_legacy_prompts(master, legacy) is False
    assert reconcile_legacy_prompts(master, legacy) is False
    assert master.model_dump() == before


def test_lane_edit_updates_batch_and_mirrors_user_direction():
    master = _master_with_batches([5.0])
    legacy = [_legacy_prompt("leg_a", 0.0, 5.0, "Original direction.")]
    reconcile_legacy_prompts(master, legacy)
    # Same author edits the lane text
    legacy[0].text = "New direction after edit."
    changed = reconcile_legacy_prompts(master, legacy)
    assert changed is True
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.text == "New direction after edit."
    assert seg.userDirection == "New direction after edit."


def test_refined_production_prompt_never_clobbered():
    master = _master_with_batches([5.0])
    legacy = [_legacy_prompt("leg_a", 0.0, 5.0, "Walk toward camera.")]
    reconcile_legacy_prompts(master, legacy)
    seg = master.batchBlocks[0].promptSegments[0]
    # Co-Director refinement writes productionPrompt on the lane
    legacy[0].production_prompt = "A spokesperson strides confidently toward the camera, bright commercial lighting, 35mm."
    changed = reconcile_legacy_prompts(master, legacy)
    assert changed is True
    assert seg.productionPrompt is not None
    assert seg.productionPrompt.startswith("A spokesperson strides")
    # Author edits the visible Timed Prompt afterwards: that commit supersedes
    # the stale refinement so the next generation receives the edited text.
    legacy[0].text = "Walk quickly toward camera and smile."
    legacy[0].production_prompt = None
    reconcile_legacy_prompts(master, legacy)
    assert seg.text == "Walk quickly toward camera and smile."
    assert seg.productionPrompt is None
    assert seg.userDirection == "Walk quickly toward camera and smile."


def test_author_timed_prompt_edit_reaches_generation_request():
    from app.director_timeline_w46.contracts import ExecutionSnapshot
    from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request

    master = _master_with_batches([5.0])
    master.batchBlocks[0].generatorId = "minimax-h3"
    legacy = [_legacy_prompt("leg_a", 0.0, 5.0, "STALE PROMPT")]
    reconcile_legacy_prompts(master, legacy)
    master.batchBlocks[0].promptSegments[0].productionPrompt = "STALE PROMPT"
    legacy[0].text = "Edited Timed Prompt LIVE-TP-REGRESSION"
    legacy[0].production_prompt = None
    assert reconcile_legacy_prompts(master, legacy) is True
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.text == "Edited Timed Prompt LIVE-TP-REGRESSION"
    assert seg.productionPrompt is None
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=master.batchBlocks[0],
        snapshot=ExecutionSnapshot(batchBlockId=master.batchBlocks[0].id),
    )
    assert "LIVE-TP-REGRESSION" in req.prompt
    assert "STALE PROMPT" not in req.prompt


def test_dialogue_preserved_verbatim():
    master = _master_with_batches([5.0])
    legacy = [
        _legacy_prompt(
            "leg_a", 0.0, 5.0, "Spokesperson looks at camera.", dialogue="Built to move with you."
        )
    ]
    reconcile_legacy_prompts(master, legacy)
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.dialogue == "Built to move with you."
    # Round trip keeps it verbatim
    reconcile_legacy_prompts(master, legacy)
    assert seg.dialogue == "Built to move with you."


def test_lane_deletion_propagates():
    master = _master_with_batches([5.0])
    legacy = [
        _legacy_prompt("leg_a", 0.0, 2.0, "First."),
        _legacy_prompt("leg_b", 2.0, 3.0, "Second."),
    ]
    reconcile_legacy_prompts(master, legacy)
    assert len(master.batchBlocks[0].promptSegments) == 2
    # Delete the first lane segment
    del legacy[0]
    changed = reconcile_legacy_prompts(master, legacy)
    assert changed is True
    segs = master.batchBlocks[0].promptSegments
    assert len(segs) == 1
    assert segs[0].legacyPromptSegmentId == "leg_b"


def test_image_clip_does_not_silently_inject_source_anchors_wave3a():
    """Wave 3A bleed-control: Visual image_clips must not invent sourceAnchors."""
    master = _master_with_batches([5.0, 5.0])
    tl = DirectorTimeline(image_clips=[])
    from app.director_timeline import ImageClip

    tl.image_clips = [
        ImageClip(id="img_1", asset_id="asset_AAA", start=0.0, length=5.0, role="start", media_type="image"),
        ImageClip(id="img_2", asset_id="asset_BBB", start=5.0, length=5.0, role="guide", media_type="image"),
    ]
    # No silent inject
    assert reconcile_legacy_to_master(master, tl) is False
    assert master.batchBlocks[0].sourceAnchors == []
    assert master.batchBlocks[1].sourceAnchors == []

    # Pre-existing managed legacy anchors are cleaned when clips disappear
    master.batchBlocks[0].sourceAnchors.append(
        TimelineVisualAnchor(kind="image", assetId="asset_AAA", label="legacy:img_1", atTime=0.0)
    )
    master.batchBlocks[0].sourceAnchors.append(
        TimelineVisualAnchor(kind="image", assetId="stale", label="legacy:gone", atTime=0.0)
    )
    assert reconcile_legacy_image_anchors(master, list(tl.image_clips)) is True
    labels = {a.label for a in master.batchBlocks[0].sourceAnchors}
    assert "legacy:img_1" in labels
    assert "legacy:gone" not in labels
    # Value-stable
    assert reconcile_legacy_image_anchors(master, list(tl.image_clips)) is False


def test_user_start_anchor_survives_reconcile():
    master = _master_with_batches([5.0])
    master.batchBlocks[0].sourceAnchors.append(
        TimelineVisualAnchor(kind="image", assetId="asset_USER", label="Start", atTime=0.0)
    )
    tl = DirectorTimeline()
    from app.director_timeline import ImageClip

    tl.image_clips = [ImageClip(id="img_1", asset_id="asset_AAA", start=0.0, length=5.0, role="start", media_type="image")]
    reconcile_legacy_to_master(master, tl)
    labels = {a.label for a in master.batchBlocks[0].sourceAnchors}
    assert "Start" in labels
    # Wave 3A: no silent legacy inject alongside explicit Start
    assert "legacy:img_1" not in labels


def test_projection_round_trip_is_stable():
    master = _master_with_batches([5.0, 5.0])
    master.batchBlocks[0].promptSegments.append(
        TimelinePromptSegment(
            id="ps_b1", start=0.0, length=5.0, text="Batch one prompt.", userDirection="Batch one prompt."
        )
    )
    master.batchBlocks[1].promptSegments.append(
        TimelinePromptSegment(
            id="ps_b2", start=1.0, length=4.0, text="Batch two prompt.", dialogue="Say this line."
        )
    )
    projected = project_prompts_to_legacy(master)
    assert len(projected) == 2
    assert projected[0]["start"] == 0.0
    assert projected[0]["text"] == "Batch one prompt."
    assert projected[1]["start"] == 6.0  # 5s batch offset
    assert projected[1]["dialogue"] == "Say this line."
    # Round trip: project -> reconcile -> same state (no duplicates).
    # First reconcile may populate the missing userDirection mirror on
    # batch-created segments; the SECOND reconcile must be a no-op.
    legacy = [PromptSegment(**p) for p in projected]
    reconcile_legacy_prompts(master, legacy)
    assert reconcile_legacy_prompts(master, legacy) is False
    assert len(master.batchBlocks[0].promptSegments) == 1
    assert len(master.batchBlocks[1].promptSegments) == 1
    assert master.batchBlocks[1].promptSegments[0].dialogue == "Say this line."


def test_batch_time_windows_match_frontend_resolver():
    master = _master_with_batches([5.0, 5.0, 4.0])
    windows = batch_time_windows(master)
    assert [(round(a, 3), round(b, 3)) for _, a, b in windows] == [
        (0.0, 5.0),
        (5.0, 10.0),
        (10.0, 14.0),
    ]


def test_multi_batch_projection_never_stretches_to_scene_duration():
    """REBUILD LAW fence (Timeline source rebuild).

    The removed "one scene / one prompt" projection rewrote the first lane
    entry to (0, scene_duration, compiled_prompt); the next legacy→master
    reconcile then adopted it and re-stretched Batch 1's own window segment
    in the MASTER (Take N regression). The projection must be plain window
    projection: every batch entry keeps its own window length, and the
    project → reconcile round trip is value-stable with no stretch.
    """
    master = _master_with_batches([15.0, 15.0])
    master.batchBlocks[0].promptSegments.append(
        TimelinePromptSegment(
            id="ps_b1", start=0.0, length=15.0, text="Batch one window prompt."
        )
    )
    master.batchBlocks[1].promptSegments.append(
        TimelinePromptSegment(
            id="ps_b2", start=0.0, length=15.0, text="Batch two window prompt."
        )
    )
    projected = project_prompts_to_legacy(master)
    assert len(projected) == 2
    assert projected[0]["start"] == pytest.approx(0.0)
    assert projected[0]["length"] == pytest.approx(15.0)
    assert projected[1]["start"] == pytest.approx(15.0)
    assert projected[1]["length"] == pytest.approx(15.0)
    # No entry covers the full 30s scene.
    for entry in projected:
        assert float(entry["length"]) < 30.0
    legacy = [PromptSegment(**p) for p in projected]
    reconcile_legacy_prompts(master, legacy)
    assert reconcile_legacy_prompts(master, legacy) is False
    b1_seg = master.batchBlocks[0].promptSegments[0]
    b2_seg = master.batchBlocks[1].promptSegments[0]
    assert b1_seg.length == pytest.approx(15.0)
    assert b1_seg.text == "Batch one window prompt."
    assert b2_seg.length == pytest.approx(15.0)
    assert b2_seg.text == "Batch two window prompt."
    # A full-scene lane write (0-30) is owned by the ROOT window only —
    # start containment never duplicates it into Batch 2's window. (Batch 2's
    # own segment being removed when its lane source disappears is the
    # separately-pinned designed deletion propagation.)
    stretched = [PromptSegment(id="leg_stretch", start=0.0, length=30.0, text="Full scene recipe.")]
    reconcile_legacy_prompts(master, stretched)
    b1_texts = [seg.text for seg in master.batchBlocks[0].promptSegments]
    assert "Full scene recipe." in b1_texts
    assert all(seg.text != "Full scene recipe." for seg in master.batchBlocks[1].promptSegments)


def test_reconcile_copies_temperature_movement_and_camera_optics():
    """PUT-director-style: Inspector fields reach master. weight is not temperature."""
    from app.director_timeline import CameraClip, DirectorTimeline

    master = _master_with_batches([5.0])
    tl = DirectorTimeline(
        duration_sec=5.0,
        prompt_segments=[
            PromptSegment(
                id="leg_insp",
                start=0.5,
                length=4.0,
                text="Inspector prompt",
                weight=0.2,
                temperature=0.4,
                movement_segment_ref={"segmentId": "mv1"},
                movement_segment_revision=3,
            )
        ],
        camera_clips=[
            CameraClip(
                id="cam1",
                start=0.0,
                length=5.0,
                motion_type="dolly_in",
                rig="dolly",
                shot_id="close_up",
                lens_id="35",
                lighting_id="golden_hour",
                text="slow push",
                focus_id="char_hero",
            )
        ],
    )
    assert reconcile_legacy_to_master(master, tl) is True
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.text == "Inspector prompt"
    assert seg.start == 0.5
    assert seg.length == 4.0
    assert seg.temperature == 0.4
    assert seg.strength == 0.2  # weight maps to strength only
    assert seg.temperature != seg.strength
    assert seg.movementSegmentRef == {"segmentId": "mv1"}
    assert seg.movementSegmentRevision == 3
    # Phase 0 camera freeze: legacy camera_clips are a FROZEN no-op by default
    # (Timed Prompt is the sole camera authority). Camera sync only runs under
    # the debug env ADEPT_RECONCILE_LEGACY_CAMERAS=1.
    assert master.batchBlocks[0].cameraInstructions == []
    assert reconcile_legacy_cameras(master, list(tl.camera_clips or [])) is False
    # projection keeps temperature/movement; weight stays strength
    projected = project_prompts_to_legacy(master)
    assert projected[0]["temperature"] == 0.4
    assert projected[0]["weight"] == 0.2
    assert projected[0]["movement_segment_ref"]["segmentId"] == "mv1"
    # idempotent
    assert reconcile_legacy_to_master(master, tl) is False


def test_weight_is_never_used_as_temperature():
    master = _master_with_batches([5.0])
    legacy = [_legacy_prompt("leg_a", 0.0, 5.0, "Keep weight separate.", weight=0.8)]
    reconcile_legacy_prompts(master, legacy)
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.strength == 0.8
    assert seg.temperature == 1.0
