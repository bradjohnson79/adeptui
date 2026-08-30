"""Honesty: MiniMax H3 job duration matches ffprobe, not a 5-frame count written as 5.0s."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.completion import result_duration_seconds
from app.director_timeline_w46.generation.contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationResult,
)
from app.minimax_h3.route_a_adapter import (
    EXPERIMENTAL_CREATE_VIDEO_FPS,
    EXPERIMENTAL_LENGTH,
    build_t2va_graph,
    experimental_duration_seconds,
    measured_media_duration_seconds,
    validate_media,
)

LIVE_I2V_MP4 = Path(
    r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output\video"
    r"\Adept_H3_Private_I2V_c733c65f_00001_.mp4"
)


def _expected_experimental_seconds() -> float:
    return EXPERIMENTAL_LENGTH / EXPERIMENTAL_CREATE_VIDEO_FPS


def _job(generator_id: str) -> NormalizedJobSubmission:
    return NormalizedJobSubmission(
        internalJobId="job-h3-duration",
        providerJobId="job-h3-duration",
        queueJobId="job-h3-duration",
        generatorId=generator_id,
        status="completed",
        providerMetadata={"projectId": "p", "ltxUsed": False},
    )


def _completed_status(generator_id: str, media: dict) -> NormalizedJobStatus:
    return NormalizedJobStatus(
        internalJobId="job-h3-duration",
        providerJobId="job-h3-duration",
        queueJobId="job-h3-duration",
        generatorId=generator_id,
        status="completed",
        progress=1.0,
        providerMetadata={
            "media": media,
            "provenance": {"ltxUsed": False, "apiUsed": False, "modelId": "minimax-h3-route-a-local"},
            "ltxUsed": False,
        },
    )


def test_experimental_duration_is_length_over_create_video_fps():
    seconds = experimental_duration_seconds()
    assert seconds == _expected_experimental_seconds()
    assert seconds != 5.0
    assert 5.0 not in (seconds,)
    graph = build_t2va_graph("probe", seed=1, filename_prefix="Adept_H3")
    assert graph["13"]["inputs"]["fps"] == EXPERIMENTAL_CREATE_VIDEO_FPS
    assert graph["5"]["inputs"]["length"] == EXPERIMENTAL_LENGTH


def test_supported_durations_match_experimental_route_a_not_five_seconds():
    expected = experimental_duration_seconds()
    t2v = MiniMaxH3LocalAdapter.capabilities.supportedDurations
    i2v = MiniMaxH3I2VLocalAdapter.capabilities.supportedDurations
    assert t2v == [expected]
    assert i2v == [expected]
    assert 5.0 not in t2v
    assert 5.0 not in i2v
    for notes in (
        MiniMaxH3LocalAdapter.capabilities.notes,
        MiniMaxH3I2VLocalAdapter.capabilities.notes,
    ):
        lower = notes.lower()
        assert "not a 5s or 15s timeline generator" in lower
        assert "5.0s" not in lower
        assert "production-ready" not in lower


def test_measured_media_duration_seconds_rejects_missing_and_nonpositive():
    assert measured_media_duration_seconds(None) is None
    assert measured_media_duration_seconds({}) is None
    assert measured_media_duration_seconds({"durationSeconds": 0}) is None
    assert measured_media_duration_seconds({"durationSeconds": -1}) is None
    assert measured_media_duration_seconds({"durationSeconds": "nope"}) is None
    got = measured_media_duration_seconds({"durationSeconds": 0.208333})
    assert got == 0.208333


def _collect(adapter, media: dict):
    status = _completed_status(adapter.id, media)
    with patch.object(adapter, "get_status", return_value=status):
        return adapter.collect_result(_job(adapter.id))


def test_t2v_collect_result_uses_ffprobe_duration_not_five():
    adapter = MiniMaxH3LocalAdapter()
    live = 0.208333
    result = _collect(
        adapter,
        {
            "durationSeconds": live,
            "libraryImport": {"assetId": "asset-live"},
        },
    )
    assert result.status == "completed"
    assert result.duration == live
    assert result.duration != 5.0
    assert result.errorCode is None


def test_i2v_collect_result_uses_ffprobe_duration_not_five():
    adapter = MiniMaxH3I2VLocalAdapter()
    live = 0.208333
    result = _collect(
        adapter,
        {
            "durationSeconds": live,
            "libraryImport": {"assetId": "asset-live"},
        },
    )
    assert result.status == "completed"
    assert result.duration == live
    assert result.duration != 5.0


def test_t2v_collect_result_fails_if_duration_unmeasured():
    adapter = MiniMaxH3LocalAdapter()
    result = _collect(adapter, {"libraryImport": {"assetId": "asset-live"}})
    assert result.status == "failed"
    assert result.errorCode == "H3_DURATION_UNMEASURED"
    assert result.duration is None
    assert result.duration != 5.0


def test_i2v_collect_result_fails_if_duration_unmeasured():
    adapter = MiniMaxH3I2VLocalAdapter()
    result = _collect(adapter, {"libraryImport": {"assetId": "asset-live"}})
    assert result.status == "failed"
    assert result.errorCode == "H3_DURATION_UNMEASURED"


def test_collect_result_fails_if_duration_nonpositive():
    adapter = MiniMaxH3LocalAdapter()
    result = _collect(
        adapter,
        {"durationSeconds": 0, "libraryImport": {"assetId": "asset-live"}},
    )
    assert result.status == "failed"
    assert result.errorCode == "H3_DURATION_UNMEASURED"


def test_completion_does_not_invent_five_seconds_when_duration_missing():
    missing = TimelineGenerationResult(
        internalJobId="j",
        generatorId="minimax-h3-t2v-local",
        status="completed",
        outputAssetIds=["a"],
        duration=None,
    )
    assert result_duration_seconds(missing) == 0.0
    assert result_duration_seconds(missing) != 5.0
    measured = TimelineGenerationResult(
        internalJobId="j",
        generatorId="minimax-h3-t2v-local",
        status="completed",
        outputAssetIds=["a"],
        duration=0.208333,
    )
    assert result_duration_seconds(measured) == 0.208333


def _ffprobe_live(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=nb_frames,r_frame_rate,codec_type",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def test_live_i2v_mp4_ffprobe_and_collect_result_record_that_duration():
    assert LIVE_I2V_MP4.is_file(), f"live proof file missing: {LIVE_I2V_MP4}"
    probed = validate_media(LIVE_I2V_MP4)
    assert probed.get("ok") is True, probed
    live_seconds = float(probed["durationSeconds"])
    assert probed["frameCount"] == EXPERIMENTAL_LENGTH
    assert abs(live_seconds - experimental_duration_seconds()) < 1e-4
    assert live_seconds != 5.0

    raw = _ffprobe_live(LIVE_I2V_MP4)
    video = next(s for s in (raw.get("streams") or []) if s.get("codec_type") == "video")
    rate = video.get("r_frame_rate") or "0/1"
    num, den = rate.split("/")
    fps = float(num) / float(den or 1)
    assert abs(fps - EXPERIMENTAL_CREATE_VIDEO_FPS) < 1e-6
    assert abs(float((raw.get("format") or {}).get("duration") or 0) - live_seconds) < 1e-6

    adapter = MiniMaxH3I2VLocalAdapter()
    result = _collect(
        adapter,
        {
            "durationSeconds": live_seconds,
            "libraryImport": {"assetId": "asset-live-i2v"},
            "frameCount": probed["frameCount"],
        },
    )
    assert result.status == "completed"
    assert result.duration == live_seconds
    assert result.duration != 5.0
