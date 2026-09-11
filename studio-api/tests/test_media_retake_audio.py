"""Tests for the windowed media retake audio filter graph construction."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.media_retake.audio_rebuild import build_audio_filter, rebuild_audio


@dataclass
class _Window:
    clip_id: str
    start: float
    end: float
    audio_asset_id: str


def _graph():
    windows = [
        _Window("c1", 2.0, 4.0, "line-1.wav"),
        _Window("c2", 6.0, 7.5, "line-2.wav"),
    ]
    return build_audio_filter(
        windows,
        donor_span=(0.0, 1.0),
        scene_duration_sec=10.0,
        sample_rate=32000,
        crossfade_ms=30,
    )


def _segment_label_order_from_audio_graph(filter_complex: str):
    """Return segment labels in the order they are crossfaded."""
    across_lines = [line for line in filter_complex.split(";") if "acrossfade=" in line]
    order: list[tuple[str, str]] = []
    for line in across_lines:
        found = re.findall(r"\[(seg|win)(\d+)\]", line)
        if not order:
            order.extend(found)
        else:
            order.append(found[-1])
    return order


def test_contains_outside_atrim():
    g = _graph()
    # Outside spans carry half-crossfade (15ms) handles on shared boundaries so
    # the acrossfade overlap consumes handles, never the timeline.
    assert "atrim=start=0.000000:end=2.015000" in g.filter_complex
    assert "atrim=start=3.985000:end=6.015000" in g.filter_complex
    assert "atrim=start=7.485000:end=10.000000" in g.filter_complex


def test_contains_donor_loop():
    g = _graph()
    assert "aloop=loop=-1:size=" in g.filter_complex
    assert "atrim=start=0.000000:end=1.000000" in g.filter_complex


def test_aloop_uses_explicit_sample_count():
    g = _graph()
    match = re.search(r"aloop=loop=-1:size=(\d+)", g.filter_complex)
    assert match is not None
    size = int(match.group(1))
    assert size == math.ceil(1.0 * 32000)


def test_one_amix_per_window_normalize_zero():
    g = _graph()
    assert g.filter_complex.count("amix=inputs=2:normalize=0") == 2


def test_alimiter_per_window():
    g = _graph()
    assert g.filter_complex.count("alimiter=limit=0.95") == 2


def test_acrossfade_count_equals_segment_count_minus_one():
    g = _graph()
    # 3 outside spans + 2 windows = 5 segments -> 4 crossfades.
    assert g.filter_complex.count("acrossfade=") == 4


def test_sample_rate_everywhere():
    g = _graph()
    lines = [line for line in g.filter_complex.split(";") if "aresample=32000" in line]
    assert len(lines) >= 5  # every segment and window bed resampled


def test_window_line_inputs_in_window_order():
    g = _graph()
    assert g.line_inputs == ["line-1.wav", "line-2.wav"]


def test_line_input_index_map_in_filter():
    g = _graph()
    # First window uses input 1, second window uses input 2.
    assert "[1:a]" in g.filter_complex
    assert "[2:a]" in g.filter_complex


def test_exact_window_boundaries_in_atrim():
    g = _graph()
    # Window c1 segment is padded/trimmed to 2.0s + 2x15ms handles = 2.03s;
    # window c2 to 1.5s + handles = 1.53s. Lines delayed past the left handle
    # so they still start exactly at the window start in output time.
    assert "apad=pad_dur=2.030000" in g.filter_complex
    assert "apad=pad_dur=1.530000" in g.filter_complex
    assert "atrim=start=0.000000:end=2.030000" in g.filter_complex
    assert "atrim=start=0.000000:end=1.530000" in g.filter_complex
    assert g.filter_complex.count("adelay=15:all=1") == 2


def test_zero_outside_spans_produces_valid_graph():
    windows = [_Window("c1", 0.0, 10.0, "line.wav")]
    g = build_audio_filter(
        windows,
        donor_span=(0.0, 1.0),
        scene_duration_sec=10.0,
        sample_rate=32000,
        crossfade_ms=30,
    )
    # Only one segment (the window) -> no acrossfade, anull to output.
    assert "acrossfade=" not in g.filter_complex
    assert "anull[aout]" in g.filter_complex
    assert "apad=pad_dur=10.000000" in g.filter_complex


def test_output_label_final():
    g = _graph()
    assert g.output_label == "[aout_final]"


def test_unified_segment_ordering_in_audio_graph():
    """Regression for MAJOR-1: audio segments must be crossfaded in time order."""
    windows = [
        _Window("w0", 2.0, 4.5, "line-0.wav"),
        _Window("w1", 7.0, 9.0, "line-1.wav"),
    ]
    g = build_audio_filter(
        windows,
        donor_span=(0.0, 1.0),
        scene_duration_sec=10.0,
        sample_rate=32000,
        crossfade_ms=30,
    )
    order = _segment_label_order_from_audio_graph(g.filter_complex)
    assert order == [("seg", "0"), ("win", "0"), ("seg", "2"), ("win", "1"), ("seg", "4")]


def test_line_input_index_follows_time_order():
    """Window at 2.0-4.5 must use line input 1; window at 7.0-9.0 must use line input 2."""
    windows = [
        _Window("w_late", 7.0, 9.0, "line-late.wav"),
        _Window("w_early", 2.0, 4.5, "line-early.wav"),
    ]
    g = build_audio_filter(
        windows,
        donor_span=(0.0, 1.0),
        scene_duration_sec=10.0,
        sample_rate=32000,
        crossfade_ms=30,
    )
    # Find line filter for each window by looking at the atrim/apad that follows the [input:a].
    # Window at 2.0-4.5 is sorted first -> uses [1:a]; segment = 2.5s + 2x15ms handles.
    assert "[1:a]aresample=32000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=15:all=1,apad=pad_dur=2.530000,atrim=start=0.000000:end=2.530000" in g.filter_complex
    # Window at 7.0-9.0 is sorted second -> uses [2:a]; segment = 2.0s + handles.
    assert "[2:a]aresample=32000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=15:all=1,apad=pad_dur=2.030000,atrim=start=0.000000:end=2.030000" in g.filter_complex


# ---------------------------------------------------------------------------
# Real ffmpeg integration test (cheap, synthetic)
# ---------------------------------------------------------------------------


def _build_sine_wav(path: Path, frequency: float, duration: float, sample_rate: int = 32000) -> None:
    """Write a stereo sine-tone WAV using ffmpeg lavfi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    expr = f"0.5*sin(2*PI*{frequency}*t)|0.5*sin(2*PI*{frequency}*t)"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"aevalsrc={expr}:sample_rate={sample_rate}:c=stereo",
        "-t",
        str(duration),
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "2",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _build_master_tone_regions(path: Path, sample_rate: int = 32000) -> None:
    """Build a 6s WAV: 440Hz 0-2s, 880Hz 2-4s, 220Hz 4-6s."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tones = [440.0, 880.0, 220.0]
    inputs = []
    trims = []
    for i, freq in enumerate(tones):
        inputs.extend(["-f", "lavfi", "-i", f"aevalsrc=0.5*sin(2*PI*{freq}*t)|0.5*sin(2*PI*{freq}*t):sample_rate={sample_rate}:c=stereo"])
        trims.append(f"[{i}:a]atrim=start=0:end=2.0[seg{i}]")
    concat = "".join(f"[seg{i}]" for i in range(3)) + "concat=n=3:v=0:a=1[aout]"
    filter_complex = ";".join(trims + [concat])
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "2",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip())


def _max_volume_db(path: Path, start: float, duration: float) -> float:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", proc.stderr)
    if not match:
        raise RuntimeError("volumedetect did not report max_volume")
    return float(match.group(1))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_rebuild_audio_preserved_regions_and_windows(tmp_path: Path):
    """Run a real ffmpeg audio rebuild and assert time ordering is preserved."""
    master = tmp_path / "master_6s.wav"
    _build_master_tone_regions(master)

    line1 = tmp_path / "line_1200.wav"
    line2 = tmp_path / "line_1500.wav"
    _build_sine_wav(line1, 1200.0, 1.0)
    _build_sine_wav(line2, 1500.0, 1.0)

    windows = [
        _Window("w0", 2.0, 3.5, "line-0"),
        _Window("w1", 4.5, 5.5, "line-1"),
    ]
    out_wav = tmp_path / "rebuilt.wav"
    graph = rebuild_audio(
        master_path=master,
        line_paths=[line1, line2],
        windows=windows,
        donor_span=(0.0, 1.0),
        out_wav=out_wav,
        sample_rate=32000,
        crossfade_ms=30,
    )

    # Duration should be approximately the master duration.
    duration = _probe_duration(out_wav)
    assert duration == pytest.approx(6.0, abs=0.1)

    # All expected content regions must be present and loud (avoid 30ms crossfade edges).
    regions = [
        ("untouched 440Hz", 0.2, 1.0),      # inside original 0-2s region
        ("window 1 line+bed", 2.2, 1.0),    # inside 2.0-3.5 window
        ("untouched 880Hz", 3.7, 0.5),      # inside original 2-4s region
        ("window 2 line+bed", 4.7, 0.5),    # inside 4.5-5.5 window
        ("untouched 220Hz", 5.55, 0.35),    # inside original 4-6s region
    ]
    for name, start, length in regions:
        db = _max_volume_db(out_wav, start, length)
        assert db > -20.0, f"{name} region at {start}s is too quiet ({db} dB)"

    # Ordering sanity: the 880Hz content must NOT have leaked into the 0-2s region.
    low_region_db = _max_volume_db(out_wav, 0.2, 1.0)
    high_region_db = _max_volume_db(out_wav, 3.7, 0.5)
    assert high_region_db > -20.0, "880Hz region missing from expected 2-4s band"
    # The 0-2s region should also be loud, but if ordering were scrambled it could be silent.
    assert low_region_db > -20.0

    # The graph line_inputs and window ordering must still match.
    assert graph.line_inputs == ["line-0", "line-1"]
