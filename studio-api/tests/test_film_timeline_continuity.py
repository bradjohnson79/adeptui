"""Film Timeline continuity packet, duration honesty, and prompt authority."""

from __future__ import annotations

import shutil
import subprocess

from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.film_timeline.continuity import (
    _omni_boundary_text,
    cached_packet,
    continuation_anchor_kind,
    continuation_opening_frame,
    continuity_clause,
    fingerprint,
    invalidate_segment_continuity,
    notes_for_prompt,
    opening_frame_clause,
)
from app.film_timeline.contracts import Segment, Shot
from app.film_timeline.duration import DurationUnsupported, plan_duration
from app.media_clip import extract_frame_png
from app.film_timeline.orchestrator import LOCAL_H3_R2V, _canonical_generator, _last_completed
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
    assert second.generationMetadata["continuity"]["seam"]["status"] == "stale"
    assert "new ending" in second.generationMetadata["continuity"]["seam"]["warning"]
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


class _Packet:
    def __init__(self, summary: str, availability: str = "ready", reason: str | None = None):
        self.summary = summary
        self.availability = availability
        self.reason = reason
        self.modelEvidence = None


def test_omni_boundary_reads_the_packet_model():
    text, reason = _omni_boundary_text(_Packet("Renkoka is present at the table."))
    assert reason is None
    assert text == "Renkoka is present at the table."
    empty, why = _omni_boundary_text(_Packet("", availability="unavailable", reason="GENERATION_ACTIVE"))
    assert empty == ""
    assert why == "GENERATION_ACTIVE"


class _Raw:
    def __init__(self, raw: str):
        self.rawText = raw


class _Evidence:
    def __init__(self, raw: str):
        self.qwenOmni = _Raw(raw)


def test_omni_boundary_uses_prose_when_the_summary_is_empty():
    packet = _Packet("", availability="low_confidence")
    packet.modelEvidence = _Evidence("Renkoka is present, standing at the table, facing the camera.")
    text, reason = _omni_boundary_text(packet)
    assert reason is None
    assert "standing at the table" in text


def test_continue_locks_the_previous_last_frame_and_a_new_shot_does_not():
    previous = Segment(status="completed", assetId="video-1", lastFrameAssetId="frame-1")
    assert continuation_opening_frame(previous) == "frame-1"
    assert continuation_opening_frame(None) == ""
    assert continuation_opening_frame(previous, prepend=True) == ""
    assert continuation_opening_frame(previous, interior_retake=True) == ""
    clause = opening_frame_clause(seedance_reference=True)
    assert clause.startswith("@Image1 is the visual state")
    assert "Motion starts there" in opening_frame_clause(seedance_reference=False)
    assert "@Image1" not in opening_frame_clause(seedance_reference=False)
    assert continuation_anchor_kind(local_h3=True, supports_start_frame=False) == "reference_tail"
    assert continuation_anchor_kind(local_h3=False, supports_start_frame=True) == "start_image"
    assert continuation_anchor_kind(local_h3=False, supports_start_frame=False) == "reference_image"


def test_base_optimized_continuation_uses_the_standard_h3_inputs():
    """BO keeps the turbo profile. The last frame and ending clip match Standard H3."""

    from app.film_timeline.contracts import FilmTimeline, ReferenceAsset
    from app.film_timeline.h3_fast_renderer import plan_references
    from app.film_timeline.orchestrator import _build_request
    from app.video_runtime.local_video_profiles import H3_BO_CONTINUATION_SAFE, bo_execution_profile

    previous = Segment(
        order=0,
        status="completed",
        assetId="shot-n-take",
        lastFrameAssetId="shot-n-last-frame",
        timedPrompt="Renkoka holds the cup.",
        durationSec=15,
        generatorId="minimax-h3-i2v-local",
    )
    previous.generationMetadata["continuity"] = {
        "fingerprint": fingerprint("shot-n-take"),
        "lastFrameAssetId": "shot-n-last-frame",
    }
    film = FilmTimeline(
        references=[ReferenceAsset(type="character", assetId="renkoka", label="Renkoka", tag="@Renkoka")]
    )

    def _request(generator_id: str):
        shot = Shot(timedPrompt="She turns toward the arch.")
        shot.state.references = [
            ReferenceAsset(type="environment", assetId="mess-hall", label="Mess hall", tag="@MessHall")
        ]
        segment = Segment(order=1, durationSec=15, timedPrompt="She turns toward the arch.", generatorId=generator_id)
        return _build_request(
            None,
            "project",
            "scene",
            shot,
            segment,
            generator_id,
            "reference_video",
            previous,
            film,
        )

    standard = _request("minimax-h3-i2v-local")
    optimized = _request("minimax-h3-base-optimized")

    def _continuity_shape(request):
        slots = request.providerOptions["directorRefs"]["slots"]
        pictures = [
            (slot["role"], slot["assetId"], slot["label"])
            for slot in slots
            if slot.get("role") not in {"video", "audio"}
        ]
        videos = [(slot["role"], slot["assetId"], slot["label"]) for slot in slots if slot.get("role") == "video"]
        mode = dict(request.providerOptions["continuity"]["h3Continuity"])
        return {
            "pictures": pictures,
            "videos": videos,
            "mode": mode,
            "lastFrame": request.lastFrameAssetId,
            "video": request.videoReferenceAssetId,
            "prompt": request.prompt,
        }

    standard_shape = _continuity_shape(standard)
    optimized_shape = _continuity_shape(optimized)
    assert standard_shape == optimized_shape
    assert ("prior_frame", "shot-n-last-frame", "Last frame") in standard_shape["pictures"]
    assert ("video", "shot-n-take", "Previous segment") in standard_shape["videos"]
    assert standard_shape["mode"] == {
        "tailSeconds": 2,
        "includeLastFrame": False,
        "pairAudio": True,
        "includeOmni": True,
        "continuation": True,
    }
    assert "@Image1 is the visual state" in standard.prompt
    assert "Begin from that pose" in standard.prompt
    planned = plan_references(
        standard.providerOptions["directorRefs"]["slots"],
        standard.providerOptions["continuity"],
    )
    assert [item["assetId"] for item in planned["images"]] == ["renkoka", "mess-hall", "shot-n-last-frame"]
    assert planned["images"][-1]["label"] == "Last frame"
    assert planned["videos"][0]["assetId"] == "shot-n-take"
    assert optimized.generatorId == "minimax-h3-base-optimized"
    assert standard.generatorId == "minimax-h3-i2v-local"
    assert bo_execution_profile(has_ending_clip=True)["profile"] == H3_BO_CONTINUATION_SAFE


def test_continue_uses_the_last_finished_batch_not_list_order():
    shot = Shot(
        segments=[
            Segment(order=1, status="completed", assetId="selected-ending"),
            Segment(order=2, status="failed", assetId="abandoned-render"),
            Segment(order=0, status="completed", assetId="opening"),
        ]
    )
    chosen = _last_completed(shot)
    assert chosen is not None
    assert chosen.assetId == "selected-ending"
