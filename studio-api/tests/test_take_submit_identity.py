"""New Take / Re-Take submit identity. One live Studio job per scene/take/batch/snapshot."""

from __future__ import annotations

import inspect
import threading

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    GenerationJobRef,
    SceneTake,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.submit_identity import (
    claim_scene_slot,
    job_matches_tuple,
    live_job_id,
    scene_flight,
    single_flight,
)
from app.director_timeline_w46.orchestrator import submit_batch_generation
from app.director_timeline_w46.scene_takes import iter_active_render_jobs, start_new_take


def _row(job_id: str, status: str, take: str, batch: str, snap: str, created: str) -> dict:
    return {
        "id": job_id,
        "status": status,
        "created_at": created,
        "params": {
            "batchBlockId": batch,
            "executionSnapshotId": snap,
            "sceneTakeId": take,
        },
    }


def test_r1_second_claim_leaves_the_live_job_running():
    rows = [_row("job-a", "running", "take-a", "bb", "snap", "2026-09-22T07:50:45")]
    found = live_job_id(rows, take_id="take-a", batch_id="bb", snapshot_id="snap")
    assert found == "job-a"
    assert rows[0]["status"] == "running"
    assert "cancel_active_render" not in inspect.getsource(start_new_take)


def test_r2_other_take_is_not_the_same_job():
    rows = [_row("job-a", "running", "take-a", "bb", "snap-a", "2026-09-22T07:50:45")]
    assert live_job_id(rows, take_id="take-b", batch_id="bb", snapshot_id="snap-b") is None
    assert job_matches_tuple(
        rows[0]["params"], take_id="take-b", batch_id="bb", snapshot_id="snap-a"
    ) is False


def test_r3_second_lookup_returns_the_same_job():
    rows = [_row("job-a", "queued", "take-a", "bb", "snap", "2026-09-22T07:50:45")]
    first = live_job_id(rows, take_id="take-a", batch_id="bb", snapshot_id="snap")
    second = live_job_id(rows, take_id="take-a", batch_id="bb", snapshot_id="snap")
    assert first == second == "job-a"
    assert len(rows) == 1


def test_r4_cancelled_previous_take_is_not_live():
    rows = [
        _row("job-old", "cancelled", "take-a", "bb", "snap-a", "2026-09-22T07:51:59"),
        _row("job-new", "running", "take-b", "bb", "snap-b", "2026-09-22T08:10:00"),
    ]
    assert live_job_id(rows, take_id="take-b", batch_id="bb", snapshot_id="snap-b") == "job-new"
    assert live_job_id(rows, take_id="take-a", batch_id="bb", snapshot_id="snap-a") is None


def test_r5_reload_observes_the_job_without_cancelling_it():
    rows = [_row("job-a", "running", "take-a", "bb", "snap", "2026-09-22T07:50:45")]
    assert live_job_id(rows, take_id="take-a", batch_id="bb", snapshot_id="snap") == "job-a"
    assert rows[0]["status"] == "running"


def test_r6_next_window_is_a_different_tuple():
    rows = [_row("job-w1", "running", "take-a", "bb1", "snap-1", "2026-09-22T07:50:45")]
    assert live_job_id(rows, take_id="take-a", batch_id="bb2", snapshot_id="snap-2") is None
    assert live_job_id(rows, take_id="take-a", batch_id="bb1", snapshot_id="snap-1") == "job-w1"


def test_r7_cancel_targets_only_the_active_take():
    take_a = SceneTake(id="stk_a", label="A", letterIndex=1, status="ready")
    take_b = SceneTake(id="stk_b", label="B", letterIndex=2, status="rendering")
    job_a = GenerationJobRef(
        id="job_a",
        executionSnapshotId="snap_a",
        queueJobId="queue_a",
        status="running",
        locality="local",
        sceneTakeId="stk_a",
    )
    job_b = GenerationJobRef(
        id="job_b",
        executionSnapshotId="snap_b",
        queueJobId="queue_b",
        status="running",
        locality="local",
        sceneTakeId="stk_b",
    )
    batch = BatchBlock(
        id="bb",
        sceneId="scene",
        status="Generating",
        duration=DurationState(plannedDuration=4.0),
        generationJobs=[job_a, job_b],
    )
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        sceneTakes=[take_a, take_b],
        currentSceneTakeId=take_a.id,
        activeSceneTakeId=take_b.id,
    )
    assert [job.id for _batch, job in iter_active_render_jobs(master)] == ["job_b"]


def test_multi_batch_defers_while_another_window_is_live():
    rows = [
        _row("job-w1", "running", "take-a", "bb1", "snap-1", "2026-09-22T07:50:45"),
    ]
    same = claim_scene_slot(rows, take_id="take-a", batch_id="bb1", snapshot_id="snap-1")
    later = claim_scene_slot(rows, take_id="take-a", batch_id="bb2", snapshot_id="snap-2")
    assert same == {"action": "reuse", "jobId": "job-w1"}
    assert later["action"] == "defer"
    assert later["jobId"] == "job-w1"


def test_multi_batch_submits_next_window_after_the_live_one_finishes():
    rows = [
        _row("job-w1", "done", "take-a", "bb1", "snap-1", "2026-09-22T07:50:45"),
    ]
    nxt = claim_scene_slot(rows, take_id="take-a", batch_id="bb2", snapshot_id="snap-2")
    assert nxt["action"] == "submit"


def test_overlapping_windows_enqueue_only_one():
    scene = "scene"
    store: list[dict] = []
    seen: list[str] = []
    barrier = threading.Barrier(2)
    windows = (("bb1", "snap-1"), ("bb2", "snap-2"))

    def claim(batch: str, snap: str) -> None:
        barrier.wait()
        with scene_flight(scene):
            slot = claim_scene_slot(store, take_id="take-a", batch_id=batch, snapshot_id=snap)
            if slot["action"] != "submit":
                seen.append(slot["jobId"])
                return
            job_id = f"job-{batch}"
            store.append(_row(job_id, "running", "take-a", batch, snap, "2026-09-22T07:50:45"))
            seen.append(job_id)

    threads = [threading.Thread(target=claim, args=window) for window in windows]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(store) == 1
    assert len(seen) == 2
    assert seen[0] == seen[1] == store[0]["id"]


def test_r8_overlapping_claims_create_one_job():
    scene, take, batch, snap = "scene", "take", "bb", "snap"
    store: list[dict] = []
    seen: list[str] = []
    barrier = threading.Barrier(8)

    def claim() -> None:
        barrier.wait()
        with single_flight(scene, take, batch, snap):
            existing = live_job_id(store, take_id=take, batch_id=batch, snapshot_id=snap)
            if existing:
                seen.append(existing)
                return
            job_id = f"job-{threading.get_ident()}"
            store.append(_row(job_id, "running", take, batch, snap, "2026-09-22T07:50:45"))
            seen.append(job_id)

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(store) == 1
    assert len(set(seen)) == 1
    assert seen[0] == store[0]["id"]


def test_workspace_resubmit_observes_the_live_job(monkeypatch):
    submitted: list[object] = []

    class Caps:
        executionType = "local"
        id = "timeline-test-gen"
        supportsTimelineGeneration = True
        executable = True
        disabledReason = ""
        readiness = ""
        label = "Test"
        locality = "local"
        maxDurationSec = None

    class Adapter:
        id = "timeline-test-gen"
        capabilities = Caps()

        def submit(self, request):
            submitted.append(request)
            raise AssertionError("must not enqueue a second job")

    class Registry:
        def get(self, _generator_id):
            return Adapter()

    batch = BatchBlock(
        id="bb1",
        sceneId="scene-1",
        status="Queued",
        generatorId="timeline-test-gen",
        duration=DurationState(plannedDuration=4.0),
        pendingSnapshotId="snap1",
    )
    snap = ExecutionSnapshot(id="snap1", batchBlockId="bb1", immutable=True)
    master = SceneTimelineMaster(
        batchBlocks=[batch],
        executionSnapshots={"snap1": snap},
        activeSceneTakeId="take-1",
    )

    def load_master(_db, _project_id, _scene_id):
        return {"ok": True, "master": master.model_dump()}

    def save_master(_db, _project_id, _scene_id, fresh, touch_batches=False):
        return {"ok": True}

    monkeypatch.setattr("app.director_timeline_w46.orchestrator.store.load_master", load_master)
    monkeypatch.setattr("app.director_timeline_w46.orchestrator.store.save_master", save_master)
    monkeypatch.setattr(
        "app.director_timeline_w46.capabilities.list_generators",
        lambda: [Caps()],
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.registry.get_registry",
        lambda: Registry(),
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.submit_identity.find_live_studio_job",
        lambda **_kwargs: "job-live",
    )

    first = submit_batch_generation(
        None,  # type: ignore[arg-type]
        "project-1",
        "scene-1",
        "bb1",
        precreated_snapshot_id="snap1",
    )
    second = submit_batch_generation(
        None,  # type: ignore[arg-type]
        "project-1",
        "scene-1",
        "bb1",
        precreated_snapshot_id="snap1",
    )
    assert first["ok"] is True
    assert second["ok"] is True
    assert first["idempotent"] is True
    assert first["queueJobId"] == second["queueJobId"] == "job-live"
    assert submitted == []


def _two_window_master(*, mode: str = "parallel") -> SceneTimelineMaster:
    first = BatchBlock(
        id="bb1",
        sceneId="scene-1",
        order=0,
        status="Draft",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="The host lifts the thermos.", start=0.0, length=5.0)],
    )
    second = BatchBlock(
        id="bb2",
        sceneId="scene-1",
        order=1,
        status="Draft",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="The beans splash the lens.", start=5.0, length=5.0)],
    )
    from app.runtime_session import current_runtime_session_id

    return SceneTimelineMaster(
        batchBlocks=[first, second],
        orchestratorMode=mode,
        sceneGeneratorId="minimax-h3",
        renderSessionId=current_runtime_session_id(),
    )


def test_generate_scene_submits_one_window_even_in_parallel(monkeypatch):
    from app.director_timeline_w46.orchestrator import generate_scene

    master = _two_window_master()
    submitted: list[str] = []
    staged: list[str] = []

    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.save_master",
        lambda *_a, **_k: {"ok": True},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.run_preflight",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.submit_identity.live_scene_batch_ids",
        lambda *_a, **_k: set(),
    )

    def fake_submit(_db, _project, _scene, batch_id, **_kwargs):
        submitted.append(batch_id)
        return {"ok": True, "batchBlockId": batch_id}

    def fake_stage(_db, _project, _scene, batch_id):
        staged.append(batch_id)
        return {"ok": True, "staged": True, "batchBlockId": batch_id}

    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.submit_batch_generation",
        fake_submit,
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.stage_batch_snapshot",
        fake_stage,
    )
    master.coDirectorContinuityPolicy.enabled = False

    result = generate_scene(object(), "project-1", "scene-1", scope="full")
    assert result["ok"] is True
    assert submitted == ["bb1"]
    assert staged == ["bb2"]


def test_opening_a_previous_session_does_not_submit(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch
    from app.director_timeline_w46.scene_takes import close_previous_session_render

    master = _two_window_master()
    master.renderSessionId = "previous-session"
    master.batchBlocks[0].status = "QC_Pending"
    master.batchBlocks[0].candidateVersions = []
    master.batchBlocks[1].status = "Queued"
    master.batchBlocks[1].pendingSnapshotId = "snap-stale"
    master.sceneTakes = [
        SceneTake(
            id="stk_e",
            label="E",
            letterIndex=5,
            status="rendering",
            batches=[
                {"batchId": "bb1", "order": 0, "assetId": "asset-kept"},
                {"batchId": "bb2", "order": 1},
            ],
        )
    ]
    submitted: list[str] = []
    assert close_previous_session_render(master) is True
    assert master.batchBlocks[0].status == "QC_Pending"
    assert master.batchBlocks[1].status == "Cancelled"
    assert master.batchBlocks[1].pendingSnapshotId is None
    assert master.sceneTakes[0].status == "incomplete"
    assert master.sceneTakes[0].batches[0].assetId == "asset-kept"
    assert master.renderSessionId is None
    assert master.activeSceneTakeId is None

    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.submit_batch_generation",
        lambda *_a, **_k: submitted.append("submit") or {"ok": True},
    )
    result = submit_next_queued_batch(object(), "project-1", "scene-1")
    assert result["submitted"] is False
    assert result["reason"] == "previous_session"
    assert submitted == []


def test_workspace_get_does_not_submit_the_next_window():
    import inspect

    from app.director_timeline_w46.service import workspace

    source = inspect.getsource(workspace)
    assert "submit_next_queued_batch" not in source
    assert "submit_batch_generation" not in source


def test_cancelled_window_drops_a_leftover_running_job():
    from app.director_timeline_w46.scene_takes import close_previous_session_render

    master = _two_window_master()
    master.renderSessionId = None
    master.batchBlocks[0].status = "Cancelled"
    master.batchBlocks[0].generationJobs = [
        GenerationJobRef(
            executionSnapshotId="snap-done",
            status="completed",
            providerJobId="fal-done",
        ),
        GenerationJobRef(
            executionSnapshotId="snap-stale",
            status="running",
            providerJobId="seedance_stale",
            locality="hosted",
            apiUsed=True,
        ),
    ]
    master.batchBlocks[1].status = "Cancelled"
    assert close_previous_session_render(master) is True
    statuses = [job.status for job in master.batchBlocks[0].generationJobs]
    assert statuses == ["completed", "cancelled"]
    assert master.batchBlocks[0].generationJobs[0].providerJobId == "fal-done"


def test_submit_next_waits_while_another_window_is_live(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch

    master = _two_window_master()
    master.batchBlocks[0].status = "QC_Pending"
    master.batchBlocks[1].status = "Queued"
    submitted: list[str] = []

    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.submit_identity.live_scene_batch_ids",
        lambda *_a, **_k: {"bb1"},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.submit_batch_generation",
        lambda *_a, **_k: submitted.append("submit") or {"ok": True},
    )

    result = submit_next_queued_batch(object(), "project-1", "scene-1")
    assert result["submitted"] is False
    assert result["reason"] == "generation_in_progress"
    assert submitted == []
