"""Regression tests for media_retake executor internals."""

from __future__ import annotations

import re

import pytest

import shutil
import subprocess

from app.media_retake.executor import (
    _build_composite_filter,
    _build_splice_filter,
    _face_crop_rect,
    _probe_video,
)
from app.media_retake.planner import WindowPlan


def _video_segment_order_from_filter(filter_complex: str):
    """Return video segment labels in the order they are concatenated."""
    concat_line = next((line for line in filter_complex.split(";") if "concat=" in line), "")
    return re.findall(r"\[(vseg|vwin)(\d+)\]", concat_line)


def test_splice_filter_orders_segments_in_time():
    """Regression for MAJOR-1: video segments must be concat'd in time order."""
    windows = [
        WindowPlan("w0", "t", 1, None, None, "a", 2.0, 4.5),
        WindowPlan("w1", "t", 1, None, None, "a", 7.0, 9.0),
    ]
    filter_complex, output_label = _build_splice_filter(windows, scene_duration_sec=10.0, segment_count=2)

    order = _video_segment_order_from_filter(filter_complex)
    assert order == [
        ("vseg", "0"),  # outside 0-2
        ("vwin", "1"),  # window 2-4.5
        ("vseg", "2"),  # outside 4.5-7
        ("vwin", "3"),  # window 7-9
        ("vseg", "4"),  # outside 9-10
    ]
    assert output_label == "[vout]"


def test_splice_filter_input_indices_map_to_window_time_order():
    """The first window in time must use input 1, the second input 2, etc."""
    windows = [
        WindowPlan("w_late", "t", 1, None, None, "a", 7.0, 9.0),
        WindowPlan("w_early", "t", 1, None, None, "a", 2.0, 4.5),
    ]
    filter_complex, _ = _build_splice_filter(windows, scene_duration_sec=10.0, segment_count=2)
    # After sorting, early window is input 1, late window is input 2.
    assert "[1:v]setpts=PTS-STARTPTS" in filter_complex
    assert "[2:v]setpts=PTS-STARTPTS" in filter_complex


def test_face_crop_rect_expands_mouth_roi_and_stays_even():
    """Speaker targeting: crop must contain the whole face, even dims, in frame."""
    x, y, w, h = _face_crop_rect((0.66, 0.38, 0.07, 0.05), 1152, 640)
    assert (x, y, w, h) == (598, 66, 402, 256)
    assert x % 2 == 0 and y % 2 == 0 and w % 2 == 0 and h % 2 == 0
    assert x >= 0 and y >= 0 and x + w <= 1152 and y + h <= 640


def test_face_crop_rect_clamps_to_frame_edges():
    x, y, w, h = _face_crop_rect((0.0, 0.0, 0.1, 0.1), 1152, 640)
    assert x == 0 and y == 0
    assert x + w <= 1152 and y + h <= 640
    assert w >= 256 and h >= 256


def test_face_crop_rect_enforces_minimum_detector_size():
    x, y, w, h = _face_crop_rect((0.5, 0.5, 0.01, 0.01), 1152, 640)
    assert w >= 256 and h >= 256


def test_composite_filter_feathered_overlay_structure():
    f = _build_composite_filter(634, 32, 404, 256, 24.0)
    assert "alphamerge" in f
    assert "boxblur=14" in f
    assert "overlay=634:32" in f
    assert f.endswith("[vout]")
    # matte built at crop size so alphamerge dimensions match
    assert "s=404x256" in f


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_probe_video_real_file(tmp_path):
    """Regression: _probe_video must find the video stream in a real mp4.

    The original show_entries list omitted codec_type, so the stream selector
    (codec_type == "video") never matched and every live run failed with
    "No video stream found". Unit mocks never caught it.
    """
    clip = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=24:d=0.5",
            "-pix_fmt", "yuv420p", str(clip),
        ],
        check=True,
    )
    info = _probe_video(clip)
    assert info["width"] == 64 and info["height"] == 64
    assert info["fps"] == 24.0
    assert 0.4 < info["duration"] < 0.7
