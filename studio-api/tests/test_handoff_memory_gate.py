"""Fail-closed multi-batch memory handoff. Unknown memory never admits a model."""

from __future__ import annotations

from app.codirector.video_intelligence import gpu_lease
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation import window_handoff
from app.runtime_session import current_runtime_session_id


def _probe(*, vram, ram, ok=True, reason=None, unknown_vram=False, unknown_ram=False):
    return {
        "ok": ok,
        "consumed": False,
        "freeVramGb": vram,
        "freeRamGb": ram,
        "reason": reason,
        "unknownVram": unknown_vram,
        "unknownRam": unknown_ram,
    }


def _safe():
    return _probe(vram=28.0, ram=20.0)


def setup_function():
    gpu_lease.reset_handoff_state()


def test_one_worker_process_answers_both_questions(tmp_path):
    import os
    import subprocess
    import sys

    out = tmp_path / "pair.json"
    worker = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "app"
        / "codirector"
        / "video_intelligence"
        / "worker.py"
    )
    env = os.environ.copy()
    env["ADEPT_ALLOW_PERCEPTION_STUB"] = "1"
    env["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "stub"
    proc = subprocess.run(
        [
            sys.executable,
            str(worker),
            "--video",
            "clip.mp4",
            "--question",
            "continuity question",
            "--question-b",
            "equipment question",
            "--out",
            str(out),
            "--model-id",
            "qwen2-5-omni",
            "--mode",
            "stub",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    payload = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert len(payload["answers"]) == 2
    assert payload["answers"][0]["question"] == "continuity question"
    assert payload["answers"][1]["question"] == "equipment question"


def test_unknown_vram_blocks():
    probe = _probe(vram=None, ram=20.0, ok=False, reason="VRAM_UNKNOWN", unknown_vram=True)
    gate = gpu_lease.admit_heavyweight("qwen-omni", probe)
    assert gate["ok"] is False
    assert gate["reason"] == "VRAM_UNKNOWN"


def test_unknown_ram_blocks():
    probe = _probe(vram=28.0, ram=None, ok=False, reason="RAM_UNKNOWN", unknown_ram=True)
    gate = gpu_lease.admit_heavyweight("qwen-omni", probe)
    assert gate["ok"] is False
    assert gate["reason"] == "RAM_UNKNOWN"


def test_generator_still_resident_blocks_qwen():
    gate = gpu_lease.admit_heavyweight("qwen-omni", _probe(vram=4.5, ram=20.0))
    assert gate["ok"] is False
    assert gate["reason"] == "GENERATOR_STILL_RESIDENT"


def test_released_generator_allows_qwen():
    gate = gpu_lease.admit_heavyweight("qwen-omni", _safe())
    assert gate["ok"] is True
    assert gate["admittedModel"] == "qwen-omni"


def test_previous_model_still_resident_blocks_minimax():
    gate = gpu_lease.admit_heavyweight("minimax", _probe(vram=10.0, ram=20.0))
    assert gate["ok"] is False
    assert gate["reason"] == "PREVIOUS_MODEL_STILL_RESIDENT"


def test_released_qwen_allows_minimax():
    gate = gpu_lease.admit_heavyweight("minimax", _safe())
    assert gate["ok"] is True


def test_probe_is_consumed_and_cannot_admit_the_next_model():
    probe = _safe()
    first = gpu_lease.admit_heavyweight("qwen-omni", probe)
    second = gpu_lease.admit_heavyweight("videochat", probe)
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason"] == "PROBE_REQUIRED"


def test_worker_success_without_a_probe_does_not_admit():
    gate = gpu_lease.admit_heavyweight("minimax", None)
    assert gate["ok"] is False
    assert gate["reason"] == "PROBE_REQUIRED"


def _master(blocks):
    return SceneTimelineMaster(
        renderSessionId=current_runtime_session_id(),
        batchBlocks=blocks,
    )


def _batch(batch_id, order, status):
    return BatchBlock(
        id=batch_id,
        sceneId="s1",
        order=order,
        status=status,
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                text=f"Window {order} continues the scene from the prior beat.",
                start=float(order) * 5.0,
                length=5.0,
            )
        ],
    )


def test_api_window_does_not_wait_on_local_memory(monkeypatch):
    master = _master([_batch("bb_a", 0, "CandidateReady"), _batch("bb_b", 1, "Queued")])
    master.batchBlocks[0].generatorId = "seedance-2.0-mini"
    master.batchBlocks[1].generatorId = "seedance-2.0-mini"

    def boom(*_args, **_kwargs):
        raise AssertionError("an API window must not probe or unload local memory")

    monkeypatch.setattr(window_handoff, "probe_handoff_memory", boom)
    monkeypatch.setattr(window_handoff, "release_generator_once", boom)
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert result["readyForNext"] is True
    assert result["spawns"]["omni"] == 0
    assert result["spawns"]["free"] == 0
    assert window_handoff.handoff_submit_block(master, master.batchBlocks[1]) is None
    assert not any(
        isinstance(ref, dict) and ref.get("kind") == "handoffGate"
        for ref in (master.batchBlocks[1].references or [])
    )


def test_api_next_window_submits_without_the_local_review(monkeypatch):
    """A 30s API scene is two planned windows. Window 2 submits when window 1 finishes."""
    from app.director_timeline_w46 import orchestrator
    from app.director_timeline_w46.contracts import ApprovedClip
    from app.runtime_session import current_runtime_session_id

    first = _batch("bb_a", 0, "QC_RetryRequired")
    second = _batch("bb_b", 1, "Queued")
    first.generatorId = "seedance-2.0-mini"
    second.generatorId = "seedance-2.0-mini"
    second.pendingSnapshotId = "snap-w2"
    first.approvedClip = ApprovedClip(assetId="asset-w1", executionSnapshotId="snap-w1", candidateId="cand-w1")
    master = _master([first, second])
    master.renderSessionId = current_runtime_session_id()

    monkeypatch.setattr(
        orchestrator.store,
        "load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(orchestrator.store, "save_master", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.submit_identity.live_scene_batch_ids",
        lambda *_a, **_k: set(),
    )

    def blocked(*_a, **_k):
        raise AssertionError("an API window must not wait on the local clip review")

    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.packet_blocks_submit",
        blocked,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        blocked,
    )
    sent: dict[str, str] = {}

    def fake_submit(_db, _project, _scene, batch_id, **_kwargs):
        sent["batch"] = batch_id
        return {"ok": True}

    monkeypatch.setattr(orchestrator, "submit_batch_generation", fake_submit)
    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert result["submitted"] is True
    assert result["batchBlockId"] == "bb_b"
    assert sent["batch"] == "bb_b"


def test_dialogue_qc_does_not_stop_the_next_api_window(monkeypatch):
    """Speech check stays on the window. It does not halt the next API window or mark the take ready."""
    from app.director_timeline_w46 import orchestrator
    from app.director_timeline_w46.contracts import ApprovedClip, SceneTake, SceneTakeBatchMember
    from app.runtime_session import current_runtime_session_id

    first = _batch("bb_a", 0, "QC_RetryRequired")
    second = _batch("bb_b", 1, "Queued")
    first.generatorId = "seedance-2.0-mini"
    second.generatorId = "seedance-2.0-mini"
    second.pendingSnapshotId = "snap-w2"
    first.approvedClip = ApprovedClip(assetId="asset-w1", executionSnapshotId="snap-w1", candidateId="cand-w1")
    first.references = [
        {"kind": "dialogueQcDiagnostics", "verdict": "UNCERTAIN", "reason": "OMNI_UNAVAILABLE"}
    ]
    take = SceneTake(
        id="stk_qc",
        label="A",
        letterIndex=1,
        status="rendering",
        batches=[
            SceneTakeBatchMember(batchId="bb_a", order=0, assetId="asset-w1", status="QC_RetryRequired"),
            SceneTakeBatchMember(batchId="bb_b", order=1, status="Queued"),
        ],
    )
    master = _master([first, second])
    master.renderSessionId = current_runtime_session_id()
    master.sceneTakes = [take]
    master.activeSceneTakeId = take.id
    saved: list[str] = []

    monkeypatch.setattr(
        orchestrator.store,
        "load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )

    def save(_db, _project, _scene, live, **_kwargs):
        saved.append(str(getattr(live.sceneTakes[0], "status", "") if live.sceneTakes else ""))

    monkeypatch.setattr(orchestrator.store, "save_master", save)
    monkeypatch.setattr(
        "app.director_timeline_w46.generation.submit_identity.live_scene_batch_ids",
        lambda *_a, **_k: set(),
    )

    def blocked(*_a, **_k):
        raise AssertionError("dialogue QC must not hold or halt an API window")

    monkeypatch.setattr(orchestrator, "halt_queued_batches_after_failure", blocked)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.packet_blocks_submit",
        blocked,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        blocked,
    )
    sent: dict[str, str] = {}

    def fake_submit(_db, _project, _scene, batch_id, **_kwargs):
        sent["batch"] = batch_id
        return {"ok": True}

    monkeypatch.setattr(orchestrator, "submit_batch_generation", fake_submit)
    result = orchestrator.submit_next_queued_batch(None, "p1", "s1")
    assert result["submitted"] is True
    assert sent["batch"] == "bb_b"
    assert take.status == "rendering"
    assert "ready" not in saved


def test_provider_failure_still_halts_a_staged_api_window(monkeypatch):
    from app.director_timeline_w46 import orchestrator

    first = _batch("bb_a", 0, "Failed")
    second = _batch("bb_b", 1, "Queued")
    first.generatorId = "seedance-2.0-mini"
    second.generatorId = "seedance-2.0-mini"
    second.pendingSnapshotId = "snap-w2"
    master = _master([first, second])

    monkeypatch.setattr(
        orchestrator.store,
        "load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    saved: list[str] = []

    def save(_db, _project, _scene, live, **_kwargs):
        saved.append(live.batchBlocks[1].status)
        saved.append(str(live.batchBlocks[1].pendingSnapshotId or ""))

    monkeypatch.setattr(orchestrator.store, "save_master", save)
    result = orchestrator.halt_queued_batches_after_failure(None, "p1", "s1")
    assert result["halted"] is True
    assert result["cancelledBatchIds"] == ["bb_b"]
    assert saved == ["Cancelled", ""]


def test_local_window_still_waits_for_the_memory_gate():
    master = _master([_batch("bb_a", 0, "CandidateReady"), _batch("bb_b", 1, "Queued")])
    assert window_handoff.handoff_submit_block(master, master.batchBlocks[1]) == "memory_gate_required"


def test_one_omni_spawn_covers_both_reviews_and_a_second_poll_does_not_repeat(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    calls = {"pair": 0, "free": 0, "temporal": 0}
    probes = [_safe(), _safe(), _safe()]

    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: probes.pop(0))
    monkeypatch.setattr(window_handoff, "release_generator_once", lambda key: calls.__setitem__("free", calls["free"] + 1) or {"ok": True, "comfyFreeRequested": True, "skipped": False})

    def pair(*_a, **_k):
        calls["pair"] += 1
        return {"ok": True, "answers": [{"ok": True, "summary": "same room"}, {"ok": True, "summary": "no crew"}]}

    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        pair,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._batch_video_path",
        lambda *_a, **_k: "clip.mp4",
    )

    def prepare(*_a, **kwargs):
        calls["temporal"] += 1
        calls.setdefault("flags", []).append(kwargs.get("run_temporal", True))
        return None

    monkeypatch.setattr("app.director_timeline_w46.continuity.prepare_outgoing_bridge", prepare)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.packet_blocks_submit",
        lambda *_a, **_k: False,
    )

    first = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    second = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert first["readyForNext"] is True
    assert calls["pair"] == 1
    assert calls["free"] == 1
    assert calls["temporal"] == 2
    assert calls["flags"] == [False, True]
    assert second.get("observe") is True
    assert calls["pair"] == 1
    assert calls["free"] == 1


def test_final_window_does_not_run_temporal_review(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending")])
    calls = {"temporal": 0, "pair": 0}
    probes = [_safe(), _safe()]
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: probes.pop(0))
    monkeypatch.setattr(window_handoff, "release_generator_once", lambda key: {"ok": True, "comfyFreeRequested": True})

    def pair(*_a, **_k):
        calls["pair"] += 1
        return {"ok": True, "answers": [{"ok": True, "summary": "a"}, {"ok": True, "summary": "b"}]}

    monkeypatch.setattr("app.codirector.video_intelligence.worker_client.run_av_perception_pair", pair)
    monkeypatch.setattr("app.codirector.video_intelligence.service._batch_video_path", lambda *_a, **_k: "clip.mp4")

    def prepare(*_a, **_k):
        calls["temporal"] += 1
        return None

    monkeypatch.setattr("app.director_timeline_w46.continuity.prepare_outgoing_bridge", prepare)
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert result["readyForNext"] is False
    assert calls["temporal"] == 0
    assert calls["pair"] == 1
    assert gpu_lease.handoff_state(gpu_lease.handoff_key("s1", "", "bb_a"))["state"] == "finished"


def test_failed_unload_leaves_the_next_window_queued(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch

    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    monkeypatch.setattr(window_handoff, "_recheck_wait", lambda: None)
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: _probe(vram=4.5, ram=20.0))
    monkeypatch.setattr(window_handoff, "release_generator_once", lambda key: {"ok": True, "comfyFreeRequested": True})
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Qwen must not load")),
    )
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert result["readyForNext"] is False
    submitted = []
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.submit_batch_generation",
        lambda *_a, **_k: submitted.append("submit") or {"ok": True},
    )
    chain = submit_next_queued_batch(None, "p1", "s1")
    assert chain["submitted"] is False
    assert chain["reason"] == "GENERATOR_STILL_RESIDENT"
    assert submitted == []
    assert master.batchBlocks[1].status == "Queued"


def test_successful_handoff_submits_once(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch

    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [_safe(), _safe(), _safe()]
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: probes.pop(0))
    monkeypatch.setattr(window_handoff, "release_generator_once", lambda key: {"ok": True, "comfyFreeRequested": True})
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        lambda *_a, **_k: {"ok": True, "answers": [{"ok": True, "summary": "a"}, {"ok": True, "summary": "b"}]},
    )
    monkeypatch.setattr("app.codirector.video_intelligence.service._batch_video_path", lambda *_a, **_k: "clip.mp4")
    monkeypatch.setattr("app.director_timeline_w46.continuity.prepare_outgoing_bridge", lambda *_a, **_k: None)
    monkeypatch.setattr("app.codirector.video_intelligence.service.packet_blocks_submit", lambda *_a, **_k: False)
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert result["readyForNext"] is True
    submitted = []
    submitted_flag = {"done": False}

    def load_master(*_a, **_k):
        if submitted_flag["done"]:
            master.batchBlocks[1].status = "Generating"
        return {"ok": True, "master": master.model_dump()}

    monkeypatch.setattr("app.director_timeline_w46.orchestrator.store.load_master", load_master)
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.save_master",
        lambda *_a, **_k: {"ok": True},
    )

    def submit(*_a, **_k):
        submitted_flag["done"] = True
        submitted.append("submit")
        return {"ok": True}

    monkeypatch.setattr("app.director_timeline_w46.orchestrator.submit_batch_generation", submit)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.packet_blocks_submit",
        lambda *_a, **_k: False,
    )
    first = submit_next_queued_batch(None, "p1", "s1")
    second = submit_next_queued_batch(None, "p1", "s1")
    assert first["submitted"] is True
    assert second["submitted"] is False
    assert second["reason"] == "generation_in_progress"
    assert submitted == ["submit"]


def _arm_reviews(monkeypatch, master, probes, *, on_wait=None):
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: probes.pop(0))
    monkeypatch.setattr(window_handoff, "_recheck_wait", on_wait or (lambda: None))
    frees = {"n": 0}

    def release(key):
        frees["n"] += 1
        return {"ok": True, "comfyFreeRequested": True}

    monkeypatch.setattr(window_handoff, "release_generator_once", release)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        lambda *_a, **_k: {"ok": True, "answers": [{"ok": True, "summary": "a"}, {"ok": True, "summary": "b"}]},
    )
    monkeypatch.setattr("app.codirector.video_intelligence.service._batch_video_path", lambda *_a, **_k: "clip.mp4")
    monkeypatch.setattr("app.director_timeline_w46.continuity.prepare_outgoing_bridge", lambda *_a, **_k: None)
    monkeypatch.setattr("app.codirector.video_intelligence.service.packet_blocks_submit", lambda *_a, **_k: False)
    return frees


def test_second_probe_safe_after_resident_continues(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [_probe(vram=4.5, ram=20.0), _safe(), _safe(), _safe()]
    _arm_reviews(monkeypatch, master, probes)
    result = window_handoff.run_completion_reviews(
        None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
    )
    assert result["readyForNext"] is True
    assert gpu_lease.handoff_state(gpu_lease.handoff_key("s1", "", "bb_a"))["state"] == "ready"


def test_second_probe_safe_after_unknown_continues(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [
        _probe(vram=None, ram=20.0, ok=False, reason="VRAM_UNKNOWN", unknown_vram=True),
        _safe(),
        _safe(),
        _safe(),
    ]
    _arm_reviews(monkeypatch, master, probes)
    result = window_handoff.run_completion_reviews(
        None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
    )
    assert result["readyForNext"] is True


def test_all_rechecks_unsafe_blocks_without_loading(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [_probe(vram=4.5, ram=20.0) for _ in range(3)]
    calls = {"pair": 0, "free": 0}
    monkeypatch.setattr(window_handoff, "_recheck_wait", lambda: None)
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: probes.pop(0))

    def release(key):
        calls["free"] += 1
        return {"ok": True, "comfyFreeRequested": True}

    monkeypatch.setattr(window_handoff, "release_generator_once", release)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        lambda *_a, **_k: calls.__setitem__("pair", calls["pair"] + 1),
    )
    result = window_handoff.run_completion_reviews(
        None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
    )
    assert result["readyForNext"] is False
    assert result["probes"] == 3
    assert calls == {"pair": 0, "free": 1}
    assert master.batchBlocks[1].status == "Queued"


def test_unload_posts_free_once_across_rechecks(monkeypatch):
    posts = {"n": 0}

    class _Resp:
        status_code = 200

    monkeypatch.setattr(gpu_lease, "_free_idle_route_a", lambda: {"ok": True})
    monkeypatch.setattr(gpu_lease.time, "sleep", lambda *_a, **_k: None)
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *_a, **_k: posts.__setitem__("n", posts["n"] + 1) or _Resp())
    key = gpu_lease.handoff_key("s1", "take", "bb_a")
    gpu_lease.begin_handoff(key)
    first = gpu_lease.release_generator_once(key)
    second = gpu_lease.release_generator_once(key)
    assert first["comfyFreeRequested"] is True
    assert second.get("skipped") is True
    assert posts["n"] == 1


def test_poll_during_recheck_does_not_start_another_schedule(monkeypatch):
    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [_probe(vram=4.5, ram=20.0), _safe(), _safe(), _safe()]
    seen = []

    def wait():
        seen.append(
            window_handoff.run_completion_reviews(
                None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
            )
        )

    frees = _arm_reviews(monkeypatch, master, probes, on_wait=wait)
    result = window_handoff.run_completion_reviews(
        None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
    )
    assert result["readyForNext"] is True
    assert seen and seen[0].get("observe") is True
    assert frees["n"] == 1


def test_later_safe_probe_submits_the_next_window_once(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch

    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    probes = [_probe(vram=4.5, ram=20.0), _safe(), _safe(), _safe()]
    _arm_reviews(monkeypatch, master, probes)
    result = window_handoff.run_completion_reviews(
        None, project_id="p1", scene_id="s1", asset_id="asset", batch=master.batchBlocks[0], master=master
    )
    assert result["readyForNext"] is True
    submitted = []
    flag = {"done": False}

    def load_master(*_a, **_k):
        if flag["done"]:
            master.batchBlocks[1].status = "Generating"
        return {"ok": True, "master": master.model_dump()}

    def submit(*_a, **_k):
        flag["done"] = True
        submitted.append("submit")
        return {"ok": True}

    monkeypatch.setattr("app.director_timeline_w46.orchestrator.store.load_master", load_master)
    monkeypatch.setattr("app.director_timeline_w46.orchestrator.store.save_master", lambda *_a, **_k: {"ok": True})
    monkeypatch.setattr("app.director_timeline_w46.orchestrator.submit_batch_generation", submit)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
        lambda *_a, **_k: None,
    )
    first = submit_next_queued_batch(None, "p1", "s1")
    second = submit_next_queued_batch(None, "p1", "s1")
    assert first["submitted"] is True
    assert second["submitted"] is False
    assert submitted == ["submit"]


def test_stale_probe_from_another_handoff_does_not_admit(monkeypatch):
    from app.director_timeline_w46.orchestrator import submit_next_queued_batch

    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    key = gpu_lease.handoff_key("s1", "take-new", "bb_a")
    gpu_lease.begin_handoff(key)
    stale = _safe()
    stale["handoffKey"] = ("s1", "take-old", "bb_a")
    stale["handoffId"] = "previous-handoff"
    gate = window_handoff.reading_admits_handoff(key, stale, "qwen-omni")
    assert gate["ok"] is False
    assert gate["reason"] == "STALE_PROBE"
    other = _safe()
    other["handoffKey"] = key
    other["handoffId"] = "not-this-handoff"
    assert window_handoff.reading_admits_handoff(key, other, "qwen-omni")["ok"] is False
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.orchestrator.submit_batch_generation",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("stale probe must not submit")),
    )
    master.batchBlocks[0].sceneId = "s1"
    # The running owner is take-new; this master has no active take, so its key differs.
    # Pin the master take so submit looks at the same owner and still refuses.
    master.activeSceneTakeId = "take-new"
    chain = submit_next_queued_batch(None, "p1", "s1")
    assert chain["submitted"] is False
    assert chain["reason"] == "handoff_in_progress"


def test_silent_clip_still_reviews_the_picture():
    from app.codirector.video_intelligence.worker import preprocess_omni_media

    def process(_conversation, use_audio_in_video):
        if use_audio_in_video:
            raise AssertionError("Video must has audio track when use_audio_in_video=True")
        return [], [], ["frames"]

    use_audio, _audios, _images, videos = preprocess_omni_media(process, [])
    assert use_audio is False
    assert videos == ["frames"]


def test_clip_with_audio_keeps_the_audio_path():
    from app.codirector.video_intelligence.worker import preprocess_omni_media

    def process(_conversation, use_audio_in_video):
        assert use_audio_in_video is True
        return ["audio"], [], ["frames"]

    use_audio, audios, _images, videos = preprocess_omni_media(process, [])
    assert use_audio is True
    assert audios == ["audio"]
    assert videos == ["frames"]


def test_perception_failure_is_not_recorded_as_unknown_memory(monkeypatch):
    from types import SimpleNamespace

    master = _master([_batch("bb_a", 0, "QC_Pending"), _batch("bb_b", 1, "Queued")])
    master.activeSceneTakeId = "take-live"
    bridge = SimpleNamespace(continuityState={}, lastFrameAssetId="frame-1")
    monkeypatch.setattr(window_handoff, "probe_handoff_memory", lambda: _safe())
    monkeypatch.setattr(
        window_handoff,
        "release_generator_once",
        lambda key: {"ok": True, "comfyFreeRequested": True},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._asset_path",
        lambda *_a, **_k: "clip.mp4",
    )

    def pair(*_a, **_k):
        raise RuntimeError("Video must has audio track when use_audio_in_video=True")

    monkeypatch.setattr("app.codirector.video_intelligence.worker_client.run_av_perception_pair", pair)
    monkeypatch.setattr(
        "app.director_timeline_w46.continuity.prepare_outgoing_bridge",
        lambda *_a, **_k: bridge,
    )
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p1",
        scene_id="s1",
        asset_id="asset",
        batch=master.batchBlocks[0],
        master=master,
    )
    assert result["readyForNext"] is False
    assert result["reason"] == "PERCEPTION_FAILED"
    assert result["reason"] != "MEMORY_UNKNOWN"
    assert bridge.continuityState["sceneTakeId"] == "take-live"
    assert bridge.continuityState["sourceBatchId"] == "bb_a"
    assert gpu_lease.handoff_state(gpu_lease.handoff_key("s1", "take-live", "bb_a"))["state"] == "blocked"


def test_previous_take_tail_cannot_feed_the_current_take(monkeypatch):
    from types import SimpleNamespace

    from app.director_timeline_w46.continuity import bridge_source_stale

    monkeypatch.setattr(
        "app.director_timeline_w46.continuity._source_take_asset_id",
        lambda *_a, **_k: "asset-1",
    )
    bridge = SimpleNamespace(
        continuityState={"sceneTakeId": "take-old", "sourceAssetId": "asset-1"},
        sourceTakeId="",
    )
    source = SimpleNamespace(activeTakeId="")
    master = SimpleNamespace(activeSceneTakeId="take-new", currentSceneTakeId="take-new")
    assert bridge_source_stale(bridge, source, master) is True
    bridge.continuityState = {"sceneTakeId": "take-new", "sourceAssetId": "asset-1"}
    assert bridge_source_stale(bridge, source, master) is False
