"""Picture-cut transitions: adjacency, duration-preserving xfade, no audio crossfade."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from app.magi.media import probe_media, run_ffmpeg
from app.magi.transitions import (
    adjacency_tolerance_frames,
    edge_fade_filter,
    join_picture_parts,
    max_transition_seconds,
    next_adjacent,
    xfade_chain_filter,
)


def test_adjacent_cut_accepts_snap_window_and_rejects_a_gap():
    assert adjacency_tolerance_frames(24) == 5
    left = {"id": "a", "trackId": "v", "startFrame": 0, "durationFrames": 360}
    meeting = {"id": "b", "trackId": "v", "startFrame": 360, "durationFrames": 360}
    assert next_adjacent([left, meeting], left, fps=24)["id"] == "b"
    near = {"id": "b", "trackId": "v", "startFrame": 365, "durationFrames": 360}
    assert next_adjacent([left, near], left, fps=24)["id"] == "b"
    gap = {"id": "b", "trackId": "v", "startFrame": 360 + 48, "durationFrames": 360}
    assert next_adjacent([left, gap], left, fps=24) is None
    other_track = {"id": "b", "trackId": "a", "startFrame": 360, "durationFrames": 360}
    assert next_adjacent([left, other_track], left, fps=24) is None
    assert next_adjacent([left, meeting], meeting, fps=24) is None
    assert max_transition_seconds(48, 48, 24) >= 0.1
    assert max_transition_seconds(2, 48, 24) == 0.0


def test_picture_blend_does_not_crossfade_audio_or_shorten_the_cut():
    graph = xfade_chain_filter([2.0, 2.0], [{"kind": "dissolve", "xfade": 1.0}])
    assert "offset=1.500" in graph
    assert "acrossfade" not in graph
    assert "concat=n=2:v=0:a=1" in graph


def _color_clip(path: Path, color: str, frequency: int) -> None:
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:d=2:r=24",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=2",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ]
    )


def _frame(video: Path, dest: Path, at: float) -> Image.Image:
    run_ffmpeg(["-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", str(dest)])
    return Image.open(dest).convert("RGB")


def _mean_volume(video: Path, start: float, duration: float, frequency: int) -> float:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(video),
            "-af",
            f"highpass=f={frequency - 40},lowpass=f={frequency + 40},volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in (proc.stderr or "").splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    raise AssertionError(proc.stderr[-500:])


def _join(kind: str, dest: Path, work: Path) -> None:
    left = work / "left.mp4"
    right = work / "right.mp4"
    if not left.exists():
        _color_clip(left, "red", 440)
        _color_clip(right, "blue", 880)
    join_picture_parts(
        [
            {"path": left, "duration": 2.0, "kind": kind, "xfade": 1.0},
            {"path": right, "duration": 2.0, "kind": "", "xfade": 0},
        ],
        dest,
    )


def test_rendered_transitions_keep_duration_audio_and_distinct_pictures():
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        dissolve = work / "dissolve.mp4"
        fade = work / "fade.mp4"
        wipe = work / "wipe.mp4"
        _join("dissolve", dissolve, work)
        _join("fade", fade, work)
        _join("wipe", wipe, work)

        for path in (dissolve, fade, wipe):
            probe = probe_media(path)
            assert abs(probe["duration"] - 4.0) < 0.2, probe
            assert probe["hasAudio"] is True
            # Dialogue stays a hard cut: 440 Hz before the cut, 880 Hz after.
            before_a = _mean_volume(path, 1.6, 0.25, 440)
            before_b = _mean_volume(path, 1.6, 0.25, 880)
            after_a = _mean_volume(path, 2.15, 0.25, 440)
            after_b = _mean_volume(path, 2.15, 0.25, 880)
            assert before_a > before_b
            assert after_b > after_a

        mixed = _frame(dissolve, work / "dissolve.png", 2.0)
        red = mixed.getpixel((160, 90))
        assert red[0] > 80 and red[2] > 80, red

        black = _frame(fade, work / "fade.png", 1.7)
        center = black.getpixel((160, 90))
        assert max(center) < 20, center
        rising = _frame(fade, work / "fade-mid.png", 2.0).getpixel((160, 90))
        assert rising[0] < 30 and 20 < rising[2] < 140, rising

        wiped = _frame(wipe, work / "wipe.png", 2.0)
        left = wiped.getpixel((40, 90))
        right = wiped.getpixel((280, 90))
        # wipeleft keeps the outgoing picture on the left and reveals the incoming picture from the right.
        assert left[0] > left[2], left
        assert right[2] > right[0], right


def test_open_ends_fade_through_black_without_a_neighbor():
    assert edge_fade_filter(10, 1.5, 0) == "fade=t=in:st=0:d=1.500"
    assert edge_fade_filter(10, 0, 2) == "fade=t=out:st=8.000:d=2.000"
    assert edge_fade_filter(4, 1, 1) == "fade=t=in:st=0:d=1.000,fade=t=out:st=3.000:d=1.000"
    assert edge_fade_filter(10, 0, 0) == ""
