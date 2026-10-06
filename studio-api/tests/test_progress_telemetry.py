"""Grounded H3/Comfy progress telemetry — never invent a percent from the clock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.video_runtime.progress_telemetry import (
    STALL_THRESHOLD_SEC,
    apply_heartbeat,
    comfy_progress_percent,
    comfy_step_fraction,
    format_elapsed_clock,
    format_last_activity,
    format_render_status_line,
    infer_creator_phase,
    is_grounded_progress_message,
    merge_progress_telemetry,
    extract_progress_telemetry,
)


def test_h3_nodes_map_to_creator_phases():
    assert infer_creator_phase(node="127") == "preparing_model"
    assert infer_creator_phase(node="137") == "loading_references"
    assert infer_creator_phase(node="136") == "encoding_prompt"
    assert infer_creator_phase(node="125") == "sampling"
    assert infer_creator_phase(node="122") == "decoding"
    assert infer_creator_phase(node="92") == "finalizing"
    assert infer_creator_phase(node="200") == "loading_references"


def test_sampling_step_is_grounded_single_tick_is_not():
    assert is_grounded_progress_message("Sampling step 4/20") is True
    assert is_grounded_progress_message("Node progress 1/1") is False
    assert is_grounded_progress_message("Executing node 127") is False
    assert is_grounded_progress_message("running in ComfyUI · still running (90s)") is False


def test_format_line_never_appends_zero_percent():
    line = format_render_status_line(
        batch_index=1,
        total_batches=1,
        scene_status="generating",
        progress=0.0,
        progress_grounded=False,
        phase="preparing_model",
    )
    assert "0%" not in line
    assert "Preparing model" in line


def test_format_line_shows_elapsed_and_sampling_activity():
    line = format_render_status_line(
        batch_index=1,
        total_batches=2,
        scene_status="generating",
        progress=0.0,
        progress_grounded=False,
        phase="sampling",
        phase_label="Generating",
        elapsed_active_time=522,
        last_runtime_event_at="2026-09-16T12:08:30Z",
        now=datetime(2026, 9, 16, 12, 8, 42, tzinfo=timezone.utc),
    )
    assert "Generating — Sampling" in line
    assert "Elapsed: 08:42" in line
    assert "Runtime active" in line
    assert "Last runtime event: 12 seconds ago" in line
    assert "0%" not in line
    assert format_elapsed_clock(522) == "08:42"


def test_comfy_step_fraction_is_raw_value_over_max():
    assert comfy_step_fraction("Sampling step 9/20") == (9.0, 20.0)
    assert comfy_progress_percent("Sampling step 9/20") == 45
    assert comfy_step_fraction("Node 10 4/8") == (4.0, 8.0)
    assert comfy_step_fraction("Node progress 1/1") is None
    assert comfy_step_fraction("Executing node 125") is None


def test_format_line_reads_percent_from_comfy_message():
    line = format_render_status_line(
        batch_index=1,
        total_batches=1,
        scene_status="generating",
        progress=0.05,
        progress_grounded=False,
        phase="sampling",
        phase_label="Generating",
        message="Sampling step 9/20",
    )
    assert "45%" in line
    assert "0%" not in line


def test_format_line_appends_grounded_percent_only():
    line = format_render_status_line(
        batch_index=1,
        total_batches=2,
        scene_status="generating",
        progress=0.42,
        progress_grounded=True,
        phase="sampling",
        phase_label="Generating",
    )
    assert "42%" in line
    assert "Generating" in line


def test_heartbeat_stall_after_threshold():
    start = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    first = apply_heartbeat(
        {},
        progress=0.0,
        message="Preparing model",
        stage="preparing_model",
        node="127",
        job_status="running",
        grounded=False,
        now_iso=start.isoformat().replace("+00:00", "Z"),
    )
    later = apply_heartbeat(
        first,
        progress=0.0,
        message="running in ComfyUI · still running (120s)",
        stage="preparing_model",
        node="127",
        job_status="running",
        grounded=False,
        now_iso=(start + timedelta(seconds=STALL_THRESHOLD_SEC + 5)).isoformat().replace("+00:00", "Z"),
    )
    assert later["stalled"] is True
    assert later["progressGrounded"] is False
    assert "stalled" in (later.get("stallLabel") or "").lower()


def test_heartbeat_does_not_invent_progress_from_elapsed():
    tel = apply_heartbeat(
        {},
        progress=0.0,
        message="running in ComfyUI · still running (180s)",
        stage="sampling",
        job_status="running",
        grounded=False,
        now_iso="2026-09-16T12:03:00Z",
    )
    assert tel["progressGrounded"] is False
    assert tel.get("progress") in (None, 0, 0.0)


def test_grounded_sampler_tick_records_progress():
    tel = apply_heartbeat(
        {},
        progress=0.47,
        message="Sampling step 8/20",
        stage="sampling",
        node="125",
        job_status="running",
        grounded=True,
        now_iso="2026-09-16T12:04:00Z",
    )
    assert tel["progressGrounded"] is True
    assert abs(float(tel["progress"]) - 0.47) < 1e-9
    assert tel["phase"] == "sampling"
    assert tel["stalled"] is False


def test_merge_round_trip():
    hist = merge_progress_telemetry("{}", {"phase": "sampling", "progressGrounded": True})
    tel = extract_progress_telemetry(hist)
    assert tel["phase"] == "sampling"
    assert tel["progressGrounded"] is True


def test_executing_sampler_does_not_false_stall():
    """H3 Quality can sit on SamplerCustomAdvanced for many minutes."""
    start = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    first = apply_heartbeat(
        {},
        progress=0.0,
        message="Executing node 125",
        stage="sampling",
        node="125",
        job_status="running",
        grounded=False,
        now_iso=start.isoformat().replace("+00:00", "Z"),
    )
    later = apply_heartbeat(
        first,
        progress=0.0,
        message="Executing node 125",
        stage="sampling",
        node="125",
        job_status="running",
        grounded=False,
        now_iso=(start + timedelta(minutes=12)).isoformat().replace("+00:00", "Z"),
    )
    assert later["stalled"] is False
    assert later["phase"] == "sampling"
    assert later["progressGrounded"] is False
    assert later["lastProgressAt"] == first["lastProgressAt"]


def test_fast_graph_sampler_is_generating_and_route_a_mux_stays_finalizing():
    assert infer_creator_phase(node="13", graph="h3_fast", job_status="running") == "sampling"
    assert infer_creator_phase(node="13", job_status="running") == "finalizing"


def test_fast_kernel_clears_a_frozen_first_step():
    start = datetime(2026, 10, 4, 6, 0, tzinfo=timezone.utc)
    first = apply_heartbeat(
        {},
        progress=1 / 6,
        message="Sampling step 1/6",
        stage="sampling",
        node="13",
        job_status="running",
        grounded=True,
        graph="h3_fast",
        sage_attention="auto",
        now_iso=start.isoformat().replace("+00:00", "Z"),
    )
    assert first["phase"] == "sampling"
    assert first["phaseLabel"] == "Generating"
    assert first.get("initStalled") is not True
    frozen = apply_heartbeat(
        first,
        progress=1 / 6,
        message="Sampling step 1/6 · still running (200s)",
        stage="sampling",
        node="13",
        job_status="running",
        grounded=True,
        graph="h3_fast",
        sage_attention="auto",
        now_iso=(start + timedelta(seconds=STALL_THRESHOLD_SEC + 5)).isoformat().replace("+00:00", "Z"),
    )
    assert frozen["initStalled"] is True
    assert frozen["phaseLabel"] == "Generation stalled during model initialization."
    assert frozen["progressGrounded"] is False
    assert frozen["clearProgress"] is True


def test_safe_continuation_profile_is_not_watched():
    start = datetime(2026, 10, 4, 6, 0, tzinfo=timezone.utc)
    first = apply_heartbeat(
        {},
        progress=1 / 6,
        message="Sampling step 1/6",
        stage="sampling",
        node="13",
        job_status="running",
        grounded=True,
        graph="h3_fast",
        sage_attention="disabled",
        now_iso=start.isoformat().replace("+00:00", "Z"),
    )
    later = apply_heartbeat(
        first,
        progress=1 / 6,
        message="Sampling step 1/6",
        stage="sampling",
        node="13",
        job_status="running",
        grounded=True,
        graph="h3_fast",
        sage_attention="disabled",
        now_iso=(start + timedelta(seconds=STALL_THRESHOLD_SEC + 30)).isoformat().replace("+00:00", "Z"),
    )
    assert later.get("initStalled") is not True
    assert later["phase"] == "sampling"


def test_last_activity_copy():
    now = datetime(2026, 9, 16, 12, 10, tzinfo=timezone.utc)
    assert "3 minutes ago" in format_last_activity("2026-09-16T12:07:00Z", now=now)
