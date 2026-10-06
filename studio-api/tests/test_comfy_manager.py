"""Comfy Manager correlation and safety. External Comfy state is injected."""

from app.comfy_manager.operations import (
    classify_header,
    correlate_queue,
    job_view,
    normalize_error,
    retry_blockers,
    source_label,
    stall_level,
)


def test_source_labels_follow_existing_job_kinds():
    assert source_label("imagegen") == "Image Generator"
    assert source_label("render_shot") == "Timeline"
    assert source_label("magi_upscale") == "MAGI"
    assert source_label("imagegen", {"purpose": "environment_reference_sheet"}) == "Environment Creator"


def test_queue_marks_unknown_prompts_external():
    rows = correlate_queue(
        {"queue_running": [[0, "adept-prompt"]], "queue_pending": [[1, "someone-else"]]},
        {"adept-prompt"},
    )
    assert rows[0]["ownership"] == "adept"
    assert rows[1]["ownership"] == "external"
    assert rows[1]["label"] == "External / Unknown"


def test_long_running_prompt_is_not_stalled_without_silence():
    assert stall_level(
        status="running",
        kind="render_shot",
        telemetry_stalled=False,
        prompt_running=True,
        prompt_pending=False,
        history_done=False,
        comfy_reachable=True,
    ) == "none"


def test_quiet_prompt_still_running_is_only_possible():
    assert stall_level(
        status="running",
        kind="render_shot",
        telemetry_stalled=True,
        prompt_running=True,
        prompt_pending=False,
        history_done=False,
        comfy_reachable=True,
    ) == "possible"


def test_quiet_prompt_gone_is_stalled():
    assert stall_level(
        status="running",
        kind="imagegen",
        telemetry_stalled=True,
        prompt_running=False,
        prompt_pending=False,
        history_done=False,
        comfy_reachable=True,
    ) == "stalled"


def test_header_states():
    assert classify_header(reachable=False, running=0, pending=0, stalled=0, latest_problem=None) == "COMFY_UNAVAILABLE"
    assert classify_header(reachable=True, running=1, pending=0, stalled=0, latest_problem=None) == "BUSY"
    assert classify_header(reachable=True, running=1, pending=4, stalled=0, latest_problem=None) == "QUEUE_BACKLOG"
    assert classify_header(reachable=True, running=1, pending=0, stalled=1, latest_problem=None) == "JOB_STALLED"
    assert classify_header(reachable=True, running=0, pending=0, stalled=0, latest_problem="VRAM_OOM") == "VRAM_OOM"


def test_error_normalization_keeps_raw_text():
    parsed = normalize_error("CUDA out of memory. Tried to allocate 20 GiB")
    assert parsed["code"] == "VRAM_OOM"
    assert "GPU memory" in parsed["summary"]
    assert "20 GiB" in parsed["technical"]


def test_retry_refuses_missing_reference_and_accepts_a_saved_request():
    params = {"generatorId": "minimax-h3-base-optimized", "referenceAssetIds": ["frame-a"]}
    assert "required reference missing" in retry_blockers(
        project_exists=True, params=params, present_asset_ids=set(), status="failed"
    )
    assert retry_blockers(
        project_exists=True, params=params, present_asset_ids={"frame-a"}, status="cancelled"
    ) is None
    assert retry_blockers(
        project_exists=False, params=params, present_asset_ids={"frame-a"}, status="failed"
    )


def test_job_view_names_the_project_instead_of_only_the_id():
    view = job_view(
        {
            "id": "job-1",
            "project_id": "proj",
            "scene_id": "scene",
            "kind": "render_shot",
            "status": "running",
            "stage": "sampling",
            "progress": 0.63,
            "message": "Generating",
            "comfy_prompt_id": "prompt-1",
            "output_path": "",
            "params": {"generatorId": "minimax-h3-base-optimized", "width": 1376, "height": 768, "durationSec": 15, "shotId": "shot-1"},
            "history": {"progressTelemetry": {"elapsedActiveTime": 272, "stalled": False, "currentNode": "86"}},
            "created_at": None,
            "updated_at": None,
        },
        project_name="Production Test",
        queue_running={"prompt-1"},
        queue_pending=set(),
        comfy_reachable=True,
    )
    assert view["source"] == "Timeline"
    assert view["projectName"] == "Production Test"
    assert view["model"] == "minimax-h3-base-optimized"
    assert view["width"] == 1376
    assert view["stall"] == "none"
    assert view["workspace"] == "timeline"


def test_pause_flag_holds_new_work_without_touching_comfy():
    from app.queue_worker import JobQueue

    queue = JobQueue()
    assert queue.adept_submissions_paused is False
    assert queue.pause_adept_submissions() == {"paused": True}
    assert queue.adept_submissions_paused is True
    assert queue.resume_adept_submissions() == {"paused": False}


def test_cleanup_preview_removes_nothing():
    from app.comfy_manager.router import cleanup_preview

    preview = cleanup_preview()
    assert preview["items"] == []
    assert preview["bytes"] == 0


def _reconcile(**overrides):
    from app.comfy_manager.operations import reconcile_state

    base = dict(
        status="running",
        prompt_running=False,
        prompt_pending=False,
        telemetry_stalled=False,
        comfy_reachable=True,
        history_present=None,
        history_completed=False,
        history_has_outputs=False,
        output_present=False,
        age_sec=10,
        kind="imagegen",
    )
    base.update(overrides)
    return reconcile_state(**base)


def test_reconciliation_matrix_does_not_invent_success():
    assert _reconcile(prompt_running=True)["relation"] == "normal"
    assert _reconcile(status="queued", prompt_pending=True)["relation"] == "normal"
    waiting = _reconcile(history_present=True, history_completed=True, history_has_outputs=True, output_present=True)
    assert waiting["relation"] == "mismatch"
    assert waiting["label"].startswith("State mismatch")
    missing = _reconcile(history_present=True, history_completed=True)
    assert missing["resultMissing"] is True
    assert missing["relation"] == "result_missing"
    assert _reconcile(history_present=False, age_sec=10)["relation"] == "normal"
    lost = _reconcile(history_present=False, age_sec=50)
    assert lost["stall"] == "stalled"
    assert _reconcile(status="done", prompt_running=True)["relation"] == "mismatch"
    assert _reconcile(status="cancelled", prompt_running=True)["relation"] == "mismatch"
    assert _reconcile(status="failed", history_present=True, history_completed=True)["relation"] == "mismatch"
    quiet_h3 = _reconcile(status="running", prompt_running=True, telemetry_stalled=True, kind="render_shot", age_sec=900)
    assert quiet_h3["stall"] == "possible"
    assert quiet_h3["relation"] != "stalled"


def test_result_missing_is_its_own_diagnostic_and_keeps_the_raw_text():
    samples = [
        "expected result missing: no output image",
        "output file missing after the workflow",
        "no output video was written",
        "expected artifact not found",
    ]
    for text in samples:
        parsed = normalize_error(text)
        assert parsed["code"] == "RESULT_MISSING"
        assert parsed["summary"] == "Generation completed without the expected output"
        assert text in parsed["technical"]
    assert normalize_error("Comfy reported an execution error")["code"] == "EXECUTION"
    assert normalize_error("CUDA out of memory. Tried to allocate 20 GiB")["code"] == "VRAM_OOM"


def test_job_view_keeps_running_when_comfy_finished_without_output():
    view = job_view(
        {
            "id": "job-1",
            "project_id": "proj",
            "kind": "imagegen",
            "status": "running",
            "message": "expected result missing: no output image",
            "comfy_prompt_id": "prompt-1",
            "output_path": "",
            "params": {},
            "history": {},
            "updated_at": "2026-10-06T03:00:00",
        },
        project_name="Production Test",
        queue_running=set(),
        queue_pending=set(),
        comfy_reachable=True,
        comfy_history={"present": True, "completed": True, "hasOutputs": False},
    )
    assert view["status"] == "running"
    assert view["statusLabel"] == "Running"
    assert view["resultMissing"] is True
    assert view["problem"]["code"] == "RESULT_MISSING"
    done = job_view(
        {
            "id": "job-2",
            "project_id": "proj",
            "kind": "imagegen",
            "status": "done",
            "comfy_prompt_id": "prompt-2",
            "output_path": "image.png",
            "params": {},
            "history": {},
        },
        project_name="Production Test",
        queue_running=set(),
        queue_pending=set(),
        comfy_reachable=True,
    )
    assert done["status"] == "done"
    assert done["statusLabel"] == "Completed"


def test_boot_and_manager_share_one_comfy_health_owner(monkeypatch):
    from pathlib import Path

    from app.comfy_health import authoritative_comfy_health
    from app.comfy_client import comfy

    root = Path(__file__).resolve().parents[1] / "app"
    boot = (root / "boot" / "live.py").read_text(encoding="utf-8")
    snap = (root / "comfy_manager" / "snapshot.py").read_text(encoding="utf-8")
    assert "authoritative_comfy_health" in boot
    assert "authoritative_comfy_health" in snap
    assert "/system_stats" not in boot
    assert "/system_stats" not in snap
    assert "urlopen" not in snap

    def fake_stats(timeout: float = 3.0):
        assert timeout == 2.0
        return 200, {"devices": [{"name": "GPU", "vram_total": 10, "vram_free": 4}]}

    monkeypatch.setattr(comfy, "read_system_stats", fake_stats)
    monkeypatch.setattr("runtime_supervisor.ports.listening_pids", lambda port: [31048] if port == 8188 else [])
    report = authoritative_comfy_health(timeout_sec=2.0)
    assert report["healthy"] is True
    assert report["pid"] == 31048
    assert report["httpStatus"] == 200
    assert str(report["endpoint"]).endswith("8188")
