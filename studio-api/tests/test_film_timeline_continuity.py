"""Film Timeline continuity packet, duration honesty, and prompt authority."""

from __future__ import annotations

import shutil
import subprocess

from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.film_timeline.continuity import (
    cached_packet,
    continuity_clause,
    fingerprint,
    invalidate_segment_continuity,
    notes_for_prompt,
)
from app.film_timeline.contracts import Segment, Shot
from app.film_timeline.duration import DurationUnsupported, plan_duration
from app.media_clip import extract_frame_png
from app.film_timeline.orchestrator import LOCAL_H3_R2V, _canonical_generator
from app.film_timeline.strategies import MOTION_CONTEXT_AVAILABLE, choose_strategy


def test_extract_frame_png_writes_the_continuity_still(tmp_path):
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    assert ffmpeg
    video = tmp_path / "clip.mp4"
    subprocess.check_call(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1", "-pix_fmt", "yuv420p", str(video)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    dest = tmp_path / "last.png"
    extract_frame_png(video, dest, at_seconds=0.4)
    assert dest.exists()
    assert dest.stat().st_size > 32


def test_packet_cache_matches_asset_and_version():
    segment = Segment(status="completed", assetId="asset-1")
    segment.generationMetadata["continuity"] = {"fingerprint": fingerprint("asset-1"), "lastFrameAssetId": "frame-1"}
    assert cached_packet(segment)["lastFrameAssetId"] == "frame-1"
    segment.assetId = "asset-2"
    assert cached_packet(segment) is None


def test_retake_invalidates_that_segment_and_the_next_seam_only():
    first = Segment(id="a", order=0, status="completed", assetId="v1", lastFrameAssetId="f1")
    second = Segment(id="b", order=1, status="completed", assetId="v2")
    third = Segment(id="c", order=2, status="completed", assetId="v3")
    first.generationMetadata["continuity"] = {"fingerprint": fingerprint("v1"), "lastFrameAssetId": "f1"}
    second.generationMetadata["continuity"] = {"fingerprint": fingerprint("v2"), "seam": {"status": "ok"}}
    third.generationMetadata["continuity"] = {"fingerprint": fingerprint("v3"), "seam": {"status": "ok"}}
    shot = Shot(segments=[first, second, third])
    invalidate_segment_continuity(shot, "a")
    assert "continuity" not in first.generationMetadata
    assert first.lastFrameAssetId is None
    assert second.generationMetadata["continuity"].get("seam") is None
    assert second.generationMetadata["continuity"]["seamStale"] is True
    assert third.generationMetadata["continuity"]["seam"]["status"] == "ok"


def test_duration_3_through_20_and_ltx_refusal():
    h3 = MiniMaxH3I2VLocalAdapter().capabilities
    assert plan_duration(3, h3) == [3]
    assert plan_duration(20, h3) == [15, 5]
    ltx = Ltx25LocalAdapter().capabilities
    assert plan_duration(20, ltx) == [20]
    try:
        plan_duration(17, ltx)
    except DurationUnsupported as exc:
        assert exc.requested == 17
    else:
        raise AssertionError("LTX 17s must be refused")


def test_minimax_stays_reference_video_only():
    assert MOTION_CONTEXT_AVAILABLE is False
    assert _canonical_generator("minimax-h3-t2v-local") == LOCAL_H3_R2V
    caps = MiniMaxH3I2VLocalAdapter().capabilities
    assert choose_strategy(caps, has_previous_video=True, has_last_frame=True, has_references=True) == "reference_video"
    assert caps.supportsTextToVideo is False
    assert caps.supportsImageToVideo is False


def test_omni_notes_are_reused_from_the_cached_packet():
    previous = Segment(status="completed", assetId="asset-1")
    previous.generationMetadata["continuity"] = {
        "fingerprint": fingerprint("asset-1"),
        "notes": {"camera": "slow forward push", "light": "warm practicals"},
    }
    assert cached_packet(previous) is previous.generationMetadata["continuity"]
    clause = continuity_clause("She crosses the room.", previous)
    assert "slow forward push" in clause
    assert continuity_clause("She crosses the room.", previous) == clause


def test_timed_prompt_beats_an_omni_camera_note():
    notes = {"camera": "slow forward push", "light": "warm practicals"}
    kept = notes_for_prompt("The camera cranes upward over the table.", notes)
    assert "camera" not in kept
    assert kept["light"] == "warm practicals"
    previous = Segment(status="completed", assetId="asset-1")
    previous.generationMetadata["continuity"] = {"fingerprint": fingerprint("asset-1"), "notes": notes}
    clause = continuity_clause("The camera cranes upward over the table.", previous)
    assert "slow forward push" not in clause
    assert "warm practicals" in clause
