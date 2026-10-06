"""Whole-scene Timeline Takes — labels, Take A migrate, delete law, isolation."""

from __future__ import annotations

from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    BatchClip,
    CandidateVersion,
    DurationState,
    GenerationJobRef,
    ScenePublishState,
    SceneStitch,
    SceneTake,
    SceneTakeBatchMember,
    SceneTimelineMaster,
)
from app.director_timeline_w46.scene_takes import (
    adopt_legacy_retakes,
    batch_has_unsubmitted_snapshot,
    allocate_rendering_take,
    cancel_active_render,
    capture_members_for_active_take,
    clear_stale_queued_batches,
    iter_active_render_jobs,
    delete_block_reason,
    ensure_scene_takes,
    next_scene_take_index,
    reclaim_misallocated_take_a,
    refresh_current_take_after_repair,
    scene_has_live_render,
    scene_take_candidate_label,
    scene_take_display,
    scene_take_letter,
    sync_rendering_take,
    take_render_is_live,
)


def test_staged_later_window_keeps_the_open_take_rendering():
    done = BatchBlock(
        id="b1",
        sceneId="s12b",
        order=0,
        status="QC_Pending",
        duration=DurationState(plannedDuration=15.0),
        generationJobs=[
            GenerationJobRef(executionSnapshotId="snap_done", queueJobId="job-done", status="completed")
        ],
    )
    waiting = BatchBlock(
        id="b2",
        sceneId="s12b",
        order=1,
        status="QC_Pending",
        duration=DurationState(plannedDuration=15.0),
        pendingSnapshotId="snap_waiting",
        generationJobs=[
            GenerationJobRef(executionSnapshotId="snap_old", queueJobId="job-old", status="completed")
        ],
    )
    take = SceneTake(
        id="stk_d",
        label="D",
        letterIndex=4,
        status="incomplete",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-window-1"),
            SceneTakeBatchMember(batchId="b2", order=1),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[done, waiting],
        sceneTakes=[take],
        currentSceneTakeId=take.id,
    )
    assert batch_has_unsubmitted_snapshot(waiting) is True
    assert batch_has_unsubmitted_snapshot(done) is False
    approved = waiting.model_copy(update={"status": "Approved"})
    assert batch_has_unsubmitted_snapshot(approved) is False
    assert scene_has_live_render(master) is True
    assert sync_rendering_take(master) is True
    assert master.activeSceneTakeId == take.id
    assert take.status == "rendering"


def test_handoff_gap_does_not_cancel_the_take():
    done = BatchBlock(
        id="b1",
        sceneId="s12b",
        order=0,
        status="CandidateReady",
        duration=DurationState(plannedDuration=15.0),
    )
    nxt = BatchBlock(
        id="b2",
        sceneId="s12b",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=15.0),
    )
    take = SceneTake(
        id="stk_f",
        label="F",
        letterIndex=6,
        status="rendering",
        batches=[SceneTakeBatchMember(batchId="b1", order=0), SceneTakeBatchMember(batchId="b2", order=1)],
    )
    master = SceneTimelineMaster(
        batchBlocks=[done, nxt],
        sceneTakes=[take],
        activeSceneTakeId=take.id,
        currentSceneTakeId=take.id,
    )
    assert scene_has_live_render(master) is True
    assert sync_rendering_take(master) is True
    assert take.status == "rendering"
    assert scene_take_letter(1) == "A"
    assert scene_take_letter(2) == "B"
    assert scene_take_letter(26) == "Z"
    assert scene_take_letter(27) == "Z1"
    assert scene_take_letter(28) == "Z2"
    assert scene_take_display("B") == "Take B"
    assert scene_take_display("Take C") == "Take C"


def _batch(batch_id: str, order: int, asset: str, status: str = "Approved") -> BatchBlock:
    return BatchBlock(
        id=batch_id,
        sceneId="s12b",
        order=order,
        status=status,
        duration=DurationState(plannedDuration=5.0),
        approvedClip=ApprovedClip(assetId=asset, executionSnapshotId="snap", candidateId=f"c_{batch_id}"),
    )


def test_migrate_complete_render_to_take_a_without_rerender():
    master = SceneTimelineMaster(
        batchBlocks=[_batch("b1", 0, "asset-a1"), _batch("b2", 1, "asset-a2")],
        sceneStitch=SceneStitch(assetId="stitch-a", sourceBatchIds=["b1", "b2"], sourceAssetIds=["asset-a1", "asset-a2"]),
    )
    assert ensure_scene_takes(master) is True
    assert len(master.sceneTakes) == 1
    take = master.sceneTakes[0]
    assert take.label == "A"
    assert take.letterIndex == 1
    assert take.resultAssetId == "stitch-a"
    assert [m.assetId for m in take.batches] == ["asset-a1", "asset-a2"]
    assert master.currentSceneTakeId == take.id
    assert ensure_scene_takes(master) is False


def test_next_index_does_not_reset_per_batch():
    master = SceneTimelineMaster(
        sceneTakes=[
            SceneTake(id="stk_a", label="A", letterIndex=1),
            SceneTake(id="stk_b", label="B", letterIndex=2),
        ]
    )
    assert next_scene_take_index(master) == 3


def test_adopt_legacy_retakes_only_stamps_take_a():
    """SINGLE-STORE: retake clips are Master batch.visualClips (rtclip_* with
    metadata.retakeId). The retired legacy video_clips array is never read."""
    master = SceneTimelineMaster(
        batchBlocks=[
            BatchBlock(
                id="b1",
                sceneId="s12b",
                order=0,
                duration=DurationState(plannedDuration=5.0),
                visualClips=[
                    BatchClip(
                        id="rtclip_rr_old",
                        kind="video",
                        assetId="asset-rt1",
                        start=1.0,
                        length=1.0,
                        metadata={"retakeId": "rr_old", "role": "retake", "sourceBatchId": "b1"},
                    ),
                    BatchClip(
                        id="rtclip_rr_old2",
                        kind="video",
                        assetId="asset-rt2",
                        start=3.0,
                        length=1.0,
                        metadata={"retakeId": "rr_old2", "role": "retake", "sourceBatchId": "b1"},
                    ),
                ],
            )
        ],
        sceneTakes=[
            SceneTake(id="stk_a", label="A", letterIndex=1),
            SceneTake(id="stk_c", label="C", letterIndex=3),
        ],
    )
    assert adopt_legacy_retakes(master) is True
    assert master.sceneTakes[0].retakeIds == ["rr_old", "rr_old2"]
    assert master.sceneTakes[1].retakeIds == []
    assert adopt_legacy_retakes(master) is False


def test_delete_blocks_current_and_published():
    current = SceneTake(id="stk_a", label="A", letterIndex=1, resultAssetId="stitch-a")
    other = SceneTake(id="stk_b", label="B", letterIndex=2, resultAssetId="stitch-b")
    master = SceneTimelineMaster(
        sceneTakes=[current, other],
        currentSceneTakeId=current.id,
        scenePublish=ScenePublishState(publishedAssetId="pub-b", takeId=other.id, takeLabel="Take B"),
    )
    other.publishedAssetId = "pub-b"
    assert "current take" in (delete_block_reason(master, current) or "").lower()
    assert "published" in (delete_block_reason(master, other) or "").lower()
    spare = SceneTake(id="stk_c", label="C", letterIndex=3)
    master.sceneTakes.append(spare)
    assert delete_block_reason(master, spare) is None


def test_historical_incomplete_current_take_is_immutable_on_repair():
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="incomplete",
        completedAt="2026-09-17T18:20:45.310491+00:00",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, status="pending"),
            SceneTakeBatchMember(batchId="b2", order=1, assetId="hist-b2"),
        ],
    )
    take_g = SceneTake(
        id="stk_g",
        label="G",
        letterIndex=7,
        status="ready",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="g1")],
    )
    master = SceneTimelineMaster(
        sceneTakes=[take_a, take_g],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=None,
    )
    assert refresh_current_take_after_repair(master, "b1", asset_id="g1-new") is False
    assert take_a.batches[0].assetId is None
    assert take_a.batches[1].assetId == "hist-b2"
    assert take_g.batches[0].assetId == "g1"


def test_retake_repairs_current_take_only():
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="a1")],
    )
    take_b = SceneTake(
        id="stk_b",
        label="B",
        letterIndex=2,
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="b1")],
    )
    master = SceneTimelineMaster(sceneTakes=[take_a, take_b], currentSceneTakeId=take_b.id)
    assert refresh_current_take_after_repair(master, "b1", asset_id="b1-repair", retake_id="rt_1") is True
    assert take_b.batches[0].assetId == "b1-repair"
    assert "rt_1" in take_b.retakeIds
    assert take_a.batches[0].assetId == "a1"


def test_rendering_take_does_not_inherit_prior_take_assets():
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="ready",
        createdAt="2026-01-01T00:00:00+00:00",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-a")],
    )
    take_b = SceneTake(
        id="stk_b",
        label="B",
        letterIndex=2,
        status="rendering",
        createdAt="2026-02-01T00:00:00+00:00",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, status="pending")],
    )
    batch = _batch("b1", 0, "asset-a")
    batch.candidateVersions = [
        CandidateVersion(
            id="c_old",
            executionSnapshotId="s1",
            assetId="asset-a",
            label="A",
            createdAt="2026-01-01T00:00:00+00:00",
            approved=True,
        )
    ]
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        sceneTakes=[take_a, take_b],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_b.id,
    )
    rows = capture_members_for_active_take(master, take_b)
    assert rows[0].assetId is None
    batch.candidateVersions.append(
        CandidateVersion(
            id="c_new",
            executionSnapshotId="s2",
            assetId="asset-b",
            label="B",
            createdAt="2026-02-01T01:00:00+00:00",
            approved=False,
        )
    )
    batch.status = "CandidateReady"
    assert sync_rendering_take(master) is True
    assert take_b.status == "ready"
    assert take_b.batches[0].assetId == "asset-b"
    assert take_a.batches[0].assetId == "asset-a"


def test_partial_history_migrates_to_take_a_without_stealing_letter():
    batch = _batch("b2", 1, "hist-asset", status="CandidateReady")
    batch.candidateVersions = [
        CandidateVersion(
            id="cand_hist",
            executionSnapshotId="snap_hist",
            assetId="hist-asset",
            label="Take A",
            createdAt="2026-09-17T15:12:14+00:00",
        )
    ]
    empty = BatchBlock(
        id="b1",
        sceneId="s12b",
        order=0,
        status="Draft",
        duration=DurationState(plannedDuration=15.0),
    )
    master = SceneTimelineMaster(batchBlocks=[empty, batch])
    assert ensure_scene_takes(master) is True
    assert len(master.sceneTakes) == 1
    assert master.sceneTakes[0].label == "A"
    assert master.sceneTakes[0].status == "incomplete"
    assert master.sceneTakes[0].batches[1].assetId == "hist-asset"
    nxt = allocate_rendering_take(master)
    assert nxt.label == "B"
    assert nxt.status == "rendering"
    assert master.activeSceneTakeId == nxt.id
    assert master.sceneTakes[0].status == "incomplete"
    assert master.sceneTakes[0].id != nxt.id


def test_new_take_does_not_rebind_completed_take_a():
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="ready",
        completedAt="2026-09-17T15:12:14+00:00",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-a", candidateId="cand_a")],
    )
    master = SceneTimelineMaster(
        batchBlocks=[_batch("b1", 0, "asset-a")],
        sceneTakes=[take_a],
        currentSceneTakeId=take_a.id,
    )
    take_b = allocate_rendering_take(master)
    assert take_b.label == "B"
    assert take_a.status == "ready"
    assert take_a.batches[0].assetId == "asset-a"
    assert take_b.id != take_a.id
    assert master.activeSceneTakeId == take_b.id
    assert master.currentSceneTakeId == take_a.id
    assert scene_take_candidate_label(master) == "Take B"
    assert take_render_is_live(master, take_a) is False


def _deposited(batch_id: str, order: int, status: str) -> BatchBlock:
    return BatchBlock(
        id=batch_id,
        sceneId="s",
        order=order,
        status=status,
        duration=DurationState(plannedDuration=15.0),
        candidateVersions=[
            CandidateVersion(
                id=f"cand-{batch_id}",
                executionSnapshotId=f"snap-{batch_id}",
                assetId=f"asset-{batch_id}",
                createdAt="2026-09-22T23:10:00+00:00",
            )
        ],
    )


def test_dialogue_hold_does_not_mark_the_take_ready():
    take = SceneTake(
        id="stk_hold",
        label="A",
        letterIndex=1,
        status="rendering",
        createdAt="2026-09-22T23:00:00+00:00",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0),
            SceneTakeBatchMember(batchId="b2", order=1),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            _deposited("b1", 0, "NeedsDialogueRetake"),
            _deposited("b2", 1, "CandidateReady"),
        ],
        sceneTakes=[take],
        activeSceneTakeId=take.id,
        currentSceneTakeId=take.id,
    )
    assert sync_rendering_take(master) is True
    assert take.status == "incomplete"


def test_qc_pending_window_keeps_the_take_rendering():
    take = SceneTake(
        id="stk_qc",
        label="A",
        letterIndex=1,
        status="rendering",
        createdAt="2026-09-22T23:00:00+00:00",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0),
            SceneTakeBatchMember(batchId="b2", order=1),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            _deposited("b1", 0, "CandidateReady"),
            _deposited("b2", 1, "QC_Pending"),
        ],
        sceneTakes=[take],
        activeSceneTakeId=take.id,
        currentSceneTakeId=take.id,
    )
    assert sync_rendering_take(master) is True
    assert take.status == "rendering"


def _open_take(*batches: BatchBlock) -> tuple[SceneTimelineMaster, SceneTake]:
    take = SceneTake(
        id="stk_gate",
        label="A",
        letterIndex=1,
        status="rendering",
        createdAt="2026-09-22T23:00:00+00:00",
        batches=[
            SceneTakeBatchMember(batchId=batch.id, order=batch.order)
            for batch in batches
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=list(batches),
        sceneTakes=[take],
        activeSceneTakeId=take.id,
        currentSceneTakeId=take.id,
    )
    return master, take


def _reload_keeps(master: SceneTimelineMaster, take: SceneTake, expected: str) -> None:
    assert sync_rendering_take(master) is True
    assert take.status == expected
    sync_rendering_take(master)
    ensure_scene_takes(master)
    assert take.status == expected


def test_capture_includes_a_window_that_has_not_generated():
    master, take = _open_take(
        _deposited("b1", 0, "CandidateReady"),
        BatchBlock(id="b2", sceneId="s", order=1, status="Queued", duration=DurationState(plannedDuration=15.0)),
    )
    rows = capture_members_for_active_take(master, take)
    assert [row.batchId for row in rows] == ["b1", "b2"]
    assert rows[1].assetId is None


def test_all_candidate_ready_windows_mark_the_take_ready():
    master, take = _open_take(_deposited("b1", 0, "CandidateReady"), _deposited("b2", 1, "CandidateReady"))
    _reload_keeps(master, take, "ready")


def test_all_approved_windows_mark_the_take_ready():
    master, take = _open_take(_deposited("b1", 0, "Approved"), _deposited("b2", 1, "Approved"))
    _reload_keeps(master, take, "ready")


def test_mixed_approved_and_candidate_ready_marks_the_take_ready():
    master, take = _open_take(_deposited("b1", 0, "Approved"), _deposited("b2", 1, "CandidateReady"))
    _reload_keeps(master, take, "ready")


def test_candidate_ready_plus_qc_pending_is_not_ready():
    master, take = _open_take(_deposited("b1", 0, "CandidateReady"), _deposited("b2", 1, "QC_Pending"))
    _reload_keeps(master, take, "rendering")


def test_dialogue_retake_plus_candidate_ready_is_not_ready():
    master, take = _open_take(
        _deposited("b1", 0, "NeedsDialogueRetake"),
        _deposited("b2", 1, "CandidateReady"),
    )
    _reload_keeps(master, take, "incomplete")
    assert take.status != "cancelled"


def test_failed_window_with_a_finished_sibling_is_not_ready():
    master, take = _open_take(_deposited("b1", 0, "Failed"), _deposited("b2", 1, "CandidateReady"))
    _reload_keeps(master, take, "incomplete")
    assert take.batches[0].batchId == "b1"
    assert take.batches[0].assetId == "asset-b1"
    assert take.batches[1].assetId == "asset-b2"


def test_queued_later_window_is_not_ready():
    master, take = _open_take(
        _deposited("b1", 0, "CandidateReady"),
        BatchBlock(
            id="b2",
            sceneId="s",
            order=1,
            status="Queued",
            pendingSnapshotId="snap-next",
            duration=DurationState(plannedDuration=15.0),
        ),
    )
    _reload_keeps(master, take, "rendering")


def test_generating_later_window_keeps_the_take_rendering():
    master, take = _open_take(
        _deposited("b1", 0, "CandidateReady"),
        BatchBlock(id="b2", sceneId="s", order=1, status="Generating", duration=DurationState(plannedDuration=15.0)),
    )
    _reload_keeps(master, take, "rendering")


def test_reload_does_not_mark_ready_from_deposited_assets():
    master, take = _open_take(
        _deposited("b1", 0, "NeedsDialogueRetake"),
        _deposited("b2", 1, "QC_Pending"),
    )
    assert reclaim_misallocated_take_a(master) is False
    assert take.status == "rendering"
    ensure_scene_takes(master)
    assert take.status == "rendering"


def test_dialogue_hold_while_qc_is_pending_is_not_ready():
    master, take = _open_take(
        _deposited("b1", 0, "NeedsDialogueRetake"),
        _deposited("b2", 1, "QC_Pending"),
    )
    _reload_keeps(master, take, "rendering")


def test_deposited_asset_with_a_corrective_status_is_not_ready():
    master, take = _open_take(
        _deposited("b1", 0, "NeedsDialogueRetake"),
        _deposited("b2", 1, "NeedsDialogueRetake"),
    )
    assert all(member.assetId for member in capture_members_for_active_take(master, take))
    _reload_keeps(master, take, "incomplete")


def test_reclaim_does_not_cancel_a_take_with_a_queued_later_window():
    take_a = SceneTake(
        id="stk_open",
        label="A",
        letterIndex=1,
        status="rendering",
        createdAt="2026-09-22T23:00:00+00:00",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, status="pending"),
            SceneTakeBatchMember(batchId="b2", order=1, status="pending"),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            BatchBlock(id="b1", sceneId="s", order=0, status="Draft", duration=DurationState(plannedDuration=15.0)),
            BatchBlock(id="b2", sceneId="s", order=1, status="Queued", duration=DurationState(plannedDuration=15.0)),
        ],
        sceneTakes=[take_a],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_a.id,
    )
    assert reclaim_misallocated_take_a(master) is False
    assert take_a.status == "rendering"
    assert master.activeSceneTakeId == take_a.id


def test_reclaim_misallocated_take_a_keeps_historical_candidate():
    take_a = SceneTake(
        id="stk_new",
        label="A",
        letterIndex=1,
        status="rendering",
        createdAt="2026-09-17T17:28:21+00:00",
        batches=[SceneTakeBatchMember(batchId="b2", order=1, status="pending")],
    )
    hist = CandidateVersion(
        id="cand_be4f6ed2dade",
        executionSnapshotId="snap_f7fbe36657a1",
        assetId="22c81580-4655-4ba4-8d55-626df808cf96",
        label="Take A",
        createdAt="2026-09-17T15:12:14+00:00",
    )
    batch = BatchBlock(
        id="b2",
        sceneId="s3",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=15.0),
        candidateVersions=[hist],
    )
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        sceneTakes=[take_a],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_a.id,
    )
    assert reclaim_misallocated_take_a(master) is True
    assert take_a.status in {"ready", "incomplete"}
    assert take_a.batches[0].assetId == hist.assetId
    assert take_a.batches[0].candidateId == hist.id
    assert master.activeSceneTakeId is None
    take_b = allocate_rendering_take(master)
    assert take_b.label == "B"
    assert take_a.status in {"ready", "incomplete"}
    assert take_a.batches[0].candidateId == hist.id


def test_stale_queued_without_generating_is_not_live():
    hist = CandidateVersion(
        id="cand_hist",
        executionSnapshotId="snap_hist",
        assetId="asset-hist",
        label="Take A",
        createdAt="2026-09-17T15:12:14+00:00",
    )
    queued = BatchBlock(
        id="b2",
        sceneId="s3",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=15.0),
        candidateVersions=[hist],
        approvedClip=ApprovedClip(assetId=hist.assetId, executionSnapshotId="snap_hist", candidateId=hist.id),
    )
    draft = BatchBlock(
        id="b1",
        sceneId="s3",
        order=0,
        status="Draft",
        duration=DurationState(plannedDuration=15.0),
    )
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="incomplete",
        batches=[SceneTakeBatchMember(batchId="b2", order=1, assetId=hist.assetId, candidateId=hist.id)],
    )
    master = SceneTimelineMaster(
        batchBlocks=[draft, queued],
        sceneTakes=[take_a],
        currentSceneTakeId=take_a.id,
    )
    assert scene_has_live_render(master) is False
    assert take_render_is_live(master, take_a) is False
    assert clear_stale_queued_batches(master) is True
    assert queued.status == "CandidateReady"
    take_b = allocate_rendering_take(master)
    assert take_b.label == "B"
    assert take_b.id != take_a.id
    assert take_a.status == "incomplete"
    assert take_a.batches[0].candidateId == hist.id
    assert master.activeSceneTakeId == take_b.id


def test_staged_sequential_window_survives_idle_refresh():
    """Queued + pendingSnapshotId is the next MiniMax window, not a leftover."""
    done = BatchBlock(
        id="b1",
        sceneId="s3",
        order=0,
        status="CandidateReady",
        duration=DurationState(plannedDuration=15.0),
    )
    staged = BatchBlock(
        id="b2",
        sceneId="s3",
        order=1,
        status="Queued",
        pendingSnapshotId="snap-window-2",
        duration=DurationState(plannedDuration=15.0),
    )
    take = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="rendering",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0),
            SceneTakeBatchMember(batchId="b2", order=1),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[done, staged],
        sceneTakes=[take],
        currentSceneTakeId=take.id,
        activeSceneTakeId=take.id,
    )
    assert scene_has_live_render(master) is True
    assert clear_stale_queued_batches(master) is False
    assert staged.status == "Queued"
    assert staged.pendingSnapshotId == "snap-window-2"


def test_sync_clears_active_pointer_on_cancelled_take():
    take_a = SceneTake(id="stk_a", label="A", letterIndex=1, status="incomplete")
    take_c = SceneTake(id="stk_c", label="C", letterIndex=3, status="cancelled")
    master = SceneTimelineMaster(
        batchBlocks=[_batch("b1", 0, "asset-a")],
        sceneTakes=[take_a, take_c],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_c.id,
    )
    assert sync_rendering_take(master) is True
    assert master.activeSceneTakeId is None
    assert take_a.status == "incomplete"


def test_cancel_active_render_targets_take_b_only():
    take_a = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="ready",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-a", candidateId="cand_a")],
    )
    take_b = SceneTake(id="stk_b", label="B", letterIndex=2, status="rendering")
    hist = CandidateVersion(
        id="cand_a",
        executionSnapshotId="snap_a",
        assetId="asset-a",
        label="Take A",
        createdAt="2026-09-17T15:00:00+00:00",
    )
    live = GenerationJobRef(
        id="job_b",
        executionSnapshotId="snap_b",
        queueJobId="queue_b",
        status="running",
        locality="local",
        sceneTakeId="stk_b",
        generatorId="minimax-h3",
    )
    stale_a = GenerationJobRef(
        id="job_a",
        executionSnapshotId="snap_a",
        status="completed",
        locality="local",
        sceneTakeId="stk_a",
    )
    b1 = BatchBlock(
        id="b1",
        sceneId="s3",
        order=0,
        status="Generating",
        duration=DurationState(plannedDuration=5.0),
        generationJobs=[stale_a, live],
        promptSegments=[{"id": "ps1", "start": 0, "length": 5, "text": "keep this prompt"}],
    )
    b2 = BatchBlock(
        id="b2",
        sceneId="s3",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=5.0),
        candidateVersions=[hist],
        approvedClip=ApprovedClip(assetId="asset-a", executionSnapshotId="snap_a", candidateId="cand_a"),
    )
    master = SceneTimelineMaster(
        batchBlocks=[b1, b2],
        sceneTakes=[take_a, take_b],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_b.id,
    )
    assert [job.id for _b, job in iter_active_render_jobs(master)] == ["job_b"]
    report = cancel_active_render(master)
    assert report["cancelledTakeId"] == "stk_b"
    assert report["cancelledJobIds"] == ["job_b"]
    assert live.status == "cancelled"
    assert stale_a.status == "completed"
    assert take_a.status == "ready"
    assert take_a.batches[0].assetId == "asset-a"
    assert take_b.status == "cancelled"
    assert master.activeSceneTakeId is None
    assert master.currentSceneTakeId == take_a.id
    assert b2.approvedClip.assetId == "asset-a"
    assert b2.candidateVersions[0].id == "cand_a"
    assert b1.promptSegments[0].text == "keep this prompt"
    assert hist.assetId == "asset-a"


def test_cancel_finds_live_job_when_active_pointer_cleared():
    take_a = SceneTake(id="stk_a", label="A", letterIndex=1, status="incomplete")
    take_b = SceneTake(id="stk_b", label="B", letterIndex=2, status="cancelled")
    live = GenerationJobRef(
        id="job_b",
        executionSnapshotId="snap_b",
        queueJobId="queue_b",
        status="running",
        locality="local",
        sceneTakeId="stk_b",
        generatorId="minimax-h3",
    )
    hist = GenerationJobRef(
        id="job_a",
        executionSnapshotId="snap_a",
        status="completed",
        locality="local",
        sceneTakeId="stk_a",
    )
    b1 = BatchBlock(
        id="b1",
        sceneId="s3",
        order=0,
        status="Generating",
        duration=DurationState(plannedDuration=5.0),
        generationJobs=[hist, live],
    )
    master = SceneTimelineMaster(
        batchBlocks=[b1],
        sceneTakes=[take_a, take_b],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=None,
    )
    assert [job.id for _b, job in iter_active_render_jobs(master)] == ["job_b"]
    report = cancel_active_render(master)
    assert report["cancelledJobIds"] == ["job_b"]
    assert live.status == "cancelled"
    assert hist.status == "completed"
    assert take_a.status == "incomplete"

def test_switching_to_incomplete_take_clears_stale_scene_stitch():
    """REBUILD LAW fence (scene result authority): a take without a result is
    NOT a stitched scene result. Making an incomplete multi-batch take current
    must never leave the prior take's stitch asset in place — the scene
    honestly reports 'needs stitch' instead of a mixed-take result."""
    from app.director_timeline_w46.scene_takes import apply_take_to_live_batches

    prior_take = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        resultAssetId="stitch-a",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-a1"),
            SceneTakeBatchMember(batchId="b2", order=1, assetId="asset-a2"),
        ],
    )
    incomplete_take = SceneTake(
        id="stk_b",
        label="B",
        letterIndex=2,
        resultAssetId="",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-b1")],
    )
    master = SceneTimelineMaster(
        batchBlocks=[_batch("b1", 0, "asset-a1"), _batch("b2", 1, "asset-a2")],
        sceneStitch=SceneStitch(
            assetId="stitch-a",
            sourceBatchIds=["b1", "b2"],
            sourceAssetIds=["asset-a1", "asset-a2"],
        ),
        sceneTakes=[prior_take, incomplete_take],
        currentSceneTakeId=prior_take.id,
    )
    apply_take_to_live_batches(master, incomplete_take)
    assert master.currentSceneTakeId == incomplete_take.id
    assert master.sceneStitch is None, "stale prior-take stitch must not survive an incomplete take switch"


def test_cancelled_take_keeps_window_that_finished_after_it_opened():
    take_k = SceneTake(
        id="stk_k",
        label="K",
        letterIndex=11,
        status="ready",
        createdAt="2026-09-20T20:52:44+00:00",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-k")],
    )
    take_l = SceneTake(
        id="stk_l",
        label="L",
        letterIndex=12,
        status="cancelled",
        createdAt="2026-09-21T20:03:21+00:00",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, status="pending")],
    )
    batch = _batch("b1", 0, "asset-k", status="QC_RetryRequired")
    batch.candidateVersions = [
        CandidateVersion(
            id="c_k",
            executionSnapshotId="snap_k",
            assetId="asset-k",
            label="Take K",
            createdAt="2026-09-20T20:56:57+00:00",
        ),
        CandidateVersion(
            id="c_l",
            executionSnapshotId="snap_l",
            assetId="asset-l",
            label="Take A",
            createdAt="2026-09-21T20:07:58+00:00",
        ),
    ]
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        sceneTakes=[take_k, take_l],
        currentSceneTakeId=take_k.id,
    )
    assert ensure_scene_takes(master) is True
    assert take_l.status == "incomplete"
    assert take_l.batches[0].assetId == "asset-l"
    assert take_k.batches[0].assetId == "asset-k"


def test_rendering_take_clip_is_the_continuity_source_not_the_selected_take():
    """New Take leaves the previous ready take selected. The new clip is the tail source."""
    from app.director_timeline_w46.continuity import bridge_source_stale
    from app.director_timeline_w46.contracts import ContinuityBridge
    from app.director_timeline_w46.current_take import current_take_asset_id

    selected = SceneTake(
        id="stk_a",
        label="A",
        letterIndex=1,
        status="ready",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, assetId="asset-old")],
    )
    rendering = SceneTake(
        id="stk_g",
        label="G",
        letterIndex=7,
        status="rendering",
        batches=[SceneTakeBatchMember(batchId="b1", order=0, status="pending")],
    )
    batch = _batch("b1", 0, "asset-old")
    batch.currentTakeAssetId = "asset-new"
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        sceneTakes=[selected, rendering],
        currentSceneTakeId=selected.id,
        activeSceneTakeId=rendering.id,
    )
    assert current_take_asset_id(batch, master) == "asset-new"
    bridge = ContinuityBridge(
        bridgeId="cbr_new",
        sourceBatchId="b1",
        targetBatchId="b2",
        status="Applied",
        continuityState={"sourceAssetId": "asset-new", "sceneTakeId": "stk_g"},
    )
    assert bridge_source_stale(bridge, batch, master) is False
    bridge.continuityState["sourceAssetId"] = "asset-old"
    assert bridge_source_stale(bridge, batch, master) is True


def test_two_deposited_windows_join_without_becoming_ready():
    """API windows can be speech-checked and still join. Ready stays a separate gate."""
    from app.director_timeline_w46.scene_takes import deposited_take_to_join

    take = SceneTake(
        id="stk_c",
        label="C",
        letterIndex=3,
        status="rendering",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, assetId="clip-1", durationSec=15),
            SceneTakeBatchMember(batchId="b2", order=1, assetId="clip-2", durationSec=15),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            _batch("b1", 0, "clip-1", status="QC_RetryRequired"),
            _batch("b2", 1, "clip-2", status="QC_RetryRequired"),
        ],
        sceneTakes=[take],
        activeSceneTakeId=take.id,
    )
    joined = deposited_take_to_join(master)
    assert joined is take
    assert take.status == "rendering"


def test_closed_incomplete_take_still_joins_without_becoming_ready():
    """Speech check closes the take before the join used to look. The pictures still join."""
    import inspect

    from app.director_timeline_w46 import orchestrator
    from app.director_timeline_w46.scene_takes import deposited_take_to_join

    take = SceneTake(
        id="stk_c",
        label="C",
        letterIndex=3,
        status="incomplete",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, assetId="clip-1", durationSec=15),
            SceneTakeBatchMember(batchId="b2", order=1, assetId="clip-2", durationSec=15),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            _batch("b1", 0, "clip-1", status="NeedsDialogueRetake"),
            _batch("b2", 1, "clip-2", status="NeedsDialogueRetake"),
        ],
        sceneTakes=[take],
        activeSceneTakeId=None,
    )
    joined = deposited_take_to_join(master)
    assert joined is take
    assert take.status == "incomplete"
    src = inspect.getsource(orchestrator.complete_batch_candidate)
    assert src.index("ensure_deposited_scene_join") < src.index("sync_rendering_take")


def test_join_waits_until_every_window_has_a_picture():
    from app.director_timeline_w46.scene_takes import deposited_take_to_join

    take = SceneTake(
        id="stk_c",
        label="C",
        letterIndex=3,
        status="rendering",
        batches=[
            SceneTakeBatchMember(batchId="b1", order=0, assetId="clip-1"),
            SceneTakeBatchMember(batchId="b2", order=1, assetId=None),
        ],
    )
    master = SceneTimelineMaster(
        batchBlocks=[
            _batch("b1", 0, "clip-1", status="QC_RetryRequired"),
            BatchBlock(id="b2", sceneId="s12b", order=1, status="Queued", duration=DurationState(plannedDuration=15)),
        ],
        sceneTakes=[take],
        activeSceneTakeId=take.id,
    )
    assert deposited_take_to_join(master) is None
