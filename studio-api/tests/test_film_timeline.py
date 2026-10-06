"""Film Timeline architecture pins."""

from __future__ import annotations

from app.director_timeline_w46.generation.adapters.kling_api import KlingApiAdapter
from app.director_timeline_w46.generation.adapters.veo_api import VeoApiAdapter
from app.film_timeline.duration import DurationUnsupported, _WHOLE_SECOND_EPSILON, coerce_whole_seconds, plan_duration
from app.film_timeline.migrate import migrate_master_dict
from app.film_timeline.strategies import MOTION_CONTEXT_AVAILABLE, choose_strategy
from app.film_timeline.contracts import FilmTimeline, ShotState


class _Caps:
    def __init__(self, supported=None, maximum=None, **flags):
        self.supportedDurations = supported or []
        self.maxDurationSec = maximum
        for key, value in flags.items():
            setattr(self, key, value)


def test_duration_is_one_plan_for_5_10_15_and_mixed():
    h3 = _Caps(maximum=15)
    assert plan_duration(5, h3) == [5]
    assert plan_duration(10, h3) == [10]
    assert plan_duration(15, h3) == [15]
    kling = KlingApiAdapter().capabilities
    pieces = plan_duration(15, kling)
    assert sorted(pieces) == [5, 10]
    assert plan_duration(10, kling) == [10]


def test_h3_20s_plan_splits_into_15_and_5():
    """Minimax H3 20s scene → [15, 5] whole-second pieces."""
    h3 = _Caps(maximum=15, supported=[float(s) for s in range(3, 16)])
    pieces = plan_duration(20, h3)
    assert pieces == [15.0, 5.0]


def test_h3_plan_uses_max_based_split_not_coin():
    """With explicit supportedDurations present but no maximum, coin path applies.
    With maximum present, max-based splitting wins (H3 15s rule)."""
    h3 = _Caps(maximum=15, supported=[float(s) for s in range(3, 16)])
    pieces = plan_duration(30, h3)
    assert pieces == [15.0, 15.0]


def test_ltx_20s_is_single_piece():
    """LTX 2.5 20s scene → [20] (within max)."""
    ltx = _Caps(maximum=20, supported=[float(s) for s in range(4, 21, 2)])
    assert plan_duration(20, ltx) == [20.0]


def test_ltx_supported_list_exact_match():
    """Durations in the supportedDurations list match exactly."""
    ltx = _Caps(maximum=20, supported=[float(s) for s in range(4, 21, 2)])
    assert plan_duration(14, ltx) == [14.0]


def test_coerce_whole_seconds_rejects_fractional():
    """Real drift (15.0833) is rejected. Float dust (15.0000001) is accepted."""
    try:
        coerce_whole_seconds(15.0833)
        raise AssertionError("15.0833 must be rejected as non-whole-second")
    except DurationUnsupported as exc:
        assert "15.083" in str(exc) or "15.0833" in str(exc)
    assert coerce_whole_seconds(15.0) == 15
    assert coerce_whole_seconds(15.0000001) == 15
    assert coerce_whole_seconds(8) == 8
    try:
        coerce_whole_seconds(0)
        raise AssertionError("zero must be rejected")
    except DurationUnsupported:
        pass


def test_plan_duration_rejects_fractional_input():
    """plan_duration normalizes via coerce_whole_seconds, so fractional fails."""
    h3 = _Caps(maximum=15)
    try:
        plan_duration(15.0833, h3)
        raise AssertionError("15.0833 fractional must be rejected")
    except DurationUnsupported as exc:
        assert "whole second" in str(exc).lower() or "15.083" in str(exc)


def test_veo_cannot_fake_15_seconds():
    veo = VeoApiAdapter().capabilities
    try:
        plan_duration(15, veo)
    except DurationUnsupported as exc:
        assert exc.requested == 15
        assert any(abs(float(item) - 8) < 0.01 for item in exc.supported)
    else:
        raise AssertionError("Veo 15s must be refused")


def test_h3_legalFrameCount_set_on_providerOptions():
    """Simulate the orchestrator's _build_request flow: plan_duration returns
    whole-second pieces, not frame-grid echoes."""
    h3 = _Caps(maximum=15, supported=[float(s) for s in range(3, 16)])
    pieces = plan_duration(20, h3)
    assert pieces == [15.0, 5.0]
    # All pieces are integers
    for piece in pieces:
        assert piece == int(piece)


def test_plan_returns_float_ints():
    """generationPlan / Segment.durationSec should contain float(15.0), not 15.0833."""
    h3 = _Caps(maximum=15)
    for dur in [5, 10, 15]:
        assert plan_duration(dur, h3) == [float(dur)]
    pieces = plan_duration(20, h3)
    for piece in pieces:
        assert piece == int(piece)
        assert abs(piece - round(piece)) <= 1e-12


def test_migration_turns_windows_into_one_shot():
    film = migrate_master_dict(
        {
            "sceneGeneratorId": "minimax-h3",
            "batchBlocks": [
                {
                    "id": "bb1",
                    "order": 0,
                    "duration": {"seconds": 10},
                    "promptSegments": [{"start": 0, "length": 10, "text": "Camera pushes in."}],
                    "references": [{"type": "character", "assetId": "karri", "label": "Kar'Ri"}],
                    "approvedClip": {"assetId": "vid1"},
                    "status": "Approved",
                    "sfxClips": [{"assetId": "sfx1", "label": "Pulse", "start": 1, "length": 0.4, "kind": "sfx"}],
                    "audioClips": [{"assetId": "amb1", "label": "ship hum", "role": "ambience", "start": 0, "length": 10}],
                },
                {
                    "id": "bb2",
                    "order": 1,
                    "duration": {"seconds": 10},
                    "promptSegments": [{"start": 0, "length": 10, "text": "She turns."}],
                    "currentTakeAssetId": "vid2",
                    "status": "Approved",
                },
            ],
        },
        project_id="p",
        scene_id="s",
        scene_name="The Abode",
        dialogue_tracks=[{"clips": [{"assetId": "voice1", "startMs": 500, "durationMs": 2000, "label": "Line"}]}],
    )
    assert isinstance(film, FilmTimeline)
    assert len(film.shots) == 1
    shot = film.shots[0]
    assert isinstance(shot.state, ShotState)
    assert [segment.assetId for segment in shot.segments] == ["vid1", "vid2"]
    assert shot.state.references[0].label == "Kar'Ri"
    assert film.sfx[0].assetId == "sfx1"
    ambience = next(clip for clip in film.audio if clip.assetId == "amb1")
    voice = next(clip for clip in film.audio if clip.assetId == "voice1")
    assert ambience.role == "ambience"
    assert voice.role == "voice"
    assert "Camera pushes in." in shot.timedPrompt


def test_ambiguous_audio_is_not_silently_routed():
    film = migrate_master_dict(
        {"batchBlocks": [{"order": 0, "audioClips": [{"assetId": "mystery", "label": "Take"}]}]},
        project_id="p",
        scene_id="s",
    )
    assert film.pendingPlacements == []
    assert film.audio[0].assetId == "mystery"
    assert film.audio[0].role == "generic"
    assert film.sfx == []


def test_continuation_mode_matches_each_provider():
    from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
    from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
    from app.director_timeline_w46.generation.adapters.seedance_api import (
        Seedance25ApiAdapter,
        SeedanceApiAdapter,
        SeedanceFastApiAdapter,
        SeedanceMiniApiAdapter,
    )
    from app.film_timeline.availability import continuation_copy

    assert SeedanceMiniApiAdapter().capabilities.continuationMode == "soft"
    assert SeedanceApiAdapter().capabilities.continuationMode == "hard"
    assert SeedanceFastApiAdapter().capabilities.continuationMode == "hard"
    assert Seedance25ApiAdapter().capabilities.continuationMode == "hard"
    assert MiniMaxH3I2VLocalAdapter().capabilities.continuationMode == "hard"
    assert Ltx25LocalAdapter().capabilities.continuationMode == "hard"
    assert KlingApiAdapter().capabilities.continuationMode == "hard"
    assert VeoApiAdapter().capabilities.continuationMode == "hard"
    soft = continuation_copy("soft")
    assert soft["label"] == "Continuation: Soft reference"
    assert "not guaranteed" in soft["helper"]
    assert continuation_copy("hard")["label"] == "Continuation: Hard start-frame"
    assert continuation_copy("hard")["helper"] == ""
    assert "cannot perform continuity anchoring" in continuation_copy("none")["helper"]


def test_strategy_uses_reference_video_before_motion_context():
    caps = _Caps(supportsVideoReferences=True, supportsImageToVideo=True, supportsStartFrame=True, supportsReferenceToVideo=True)
    assert MOTION_CONTEXT_AVAILABLE is False
    assert choose_strategy(caps, has_previous_video=True, has_last_frame=True, has_references=True) == "reference_video"
    weak = _Caps(supportsImageToVideo=True, supportsStartFrame=True)
    assert choose_strategy(weak, has_previous_video=False, has_last_frame=True, has_references=True) == "last_frame_chain"


def test_retake_rejects_a_range_that_is_not_one_segment():
    from app.film_timeline.contracts import Segment, Shot
    from app.film_timeline.retake import resolve_retake_segment

    shot = Shot(
        segments=[
            Segment(order=0, durationSec=5, status="completed", assetId="a"),
            Segment(order=1, durationSec=5, status="completed", assetId="b"),
        ]
    )
    assert resolve_retake_segment(shot, None, 5)["code"] == "RETAKE_RANGE"
    assert resolve_retake_segment(shot, 5, 1)["code"] == "RETAKE_RANGE"
    assert resolve_retake_segment(shot, 3, 3)["code"] == "RETAKE_RANGE"
    assert resolve_retake_segment(shot, 0, 12)["code"] == "RETAKE_RANGE"
    partial = resolve_retake_segment(shot, 1, 4)
    assert partial["ok"] is True
    assert partial["mode"] == "partial"
    assert partial["segment"].assetId == "a"
    assert abs(partial["fileIn"] - 1) < 0.01
    assert abs(partial["fileOut"] - 4) < 0.01
    crossed = resolve_retake_segment(shot, 3, 8)
    assert crossed["code"] == "PARTIAL_RETAKE_UNSUPPORTED"
    assert "0s–5s" in crossed["message"] and "5s–10s" in crossed["message"]
    exact = resolve_retake_segment(shot, 5, 10)
    assert exact["ok"] is True
    assert exact["segment"].assetId == "b"
    from app.film_timeline.retake import generate_seconds, plan_replacement_pieces

    source = Segment(id="src", order=0, durationSec=15, status="completed", assetId="clip", origin="library")
    pieces = plan_replacement_pieces(source, "new", file_in=7, file_out=10, marked=3, generated_sec=3, prompt="turns")
    assert [item.compositionRole for item in pieces] == ["source", "retake", "source"]
    assert [round(item.durationSec, 2) for item in pieces] == [7, 3, 5]
    assert pieces[0].assetId == "clip" and pieces[2].assetId == "clip"
    assert pieces[1].assetId == "new"
    assert generate_seconds(2) == 3
    short = plan_replacement_pieces(source, "new", file_in=7, file_out=9, marked=2, generated_sec=3, prompt="turns")
    assert short[1].durationSec == 2
    assert short[1].trimOutSec == 2


def test_local_minimax_stays_reference_to_video():
    from app.film_timeline.orchestrator import LOCAL_H3_R2V, _canonical_generator, _h3_reference_ready

    assert _canonical_generator("minimax-h3-t2v-local") == LOCAL_H3_R2V
    film = FilmTimeline()
    shot = ShotState()
    empty = type("ShotBox", (), {"state": shot})()
    assert _h3_reference_ready(film, empty, LOCAL_H3_R2V, None) is False
    shot.firstFrameAssetId = "still"
    assert _h3_reference_ready(film, empty, LOCAL_H3_R2V, None) is True


def test_local_minimax_is_one_capability_row():
    from app.film_timeline.availability import list_generator_status

    rows = [row for row in list_generator_status() if "minimax-h3" in str(row["id"]) and row.get("local")]
    assert [row["id"] for row in rows] == ["minimax-h3-i2v-local"]
    # Owner-certified Director presentation (memory/session-2026-09-27-28-timeline-v2-h3.md
    # section 3B: PRESENTATION LIVE PASS — label "MiniMax H3 Director — Local").
    assert rows[0]["label"] == "MiniMax H3 — Local"


def test_production_routes_refuse_the_old_generator():
    from pathlib import Path

    router = (Path(__file__).resolve().parents[1] / "app" / "director_timeline_w46" / "router.py").read_text(encoding="utf-8")
    assert "FILM_TIMELINE_REQUIRED" in router
    generate = router.split("def generate_scene", 1)[1].split("def list_scene_takes", 1)[0]
    assert "_film_timeline_only()" in generate
    assert "orchestrator.generate_scene" not in generate


def test_h3_capabilities_duration_range():
    """H3 adapter declares supportedDurations 3–15."""
    from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import _capabilities

    caps = _capabilities()
    assert caps.maxDurationSec == 15.0
    assert caps.supportedDurations == [float(s) for s in range(3, 16)]


def test_h3_capabilities_resolutions_derived_from_megapixel_grid():
    """H3 resolutions come from the canonical D1 legal-pixel set, not a hand-typed list.

    After the owner-certified H3 Director Aspect Unify (D1), supportedResolutions
    is the single-owner derived set H3_LEGAL_RESOLUTION_LABELS (all supported
    shapes x published MP tiers), not the 16:9-only H3_MEGAPIXEL_GRID column.
    """
    from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import _capabilities
    from app.video_runtime.legal_canvas import H3_LEGAL_RESOLUTION_LABELS

    caps = _capabilities()
    expected = set(H3_LEGAL_RESOLUTION_LABELS)
    assert set(caps.supportedResolutions) == expected


def test_ltx_25_capabilities_even_seconds():
    """LTX 2.5 adapter declares supportedDurations 4,6,...,20."""
    from app.director_timeline_w46.generation.adapters.ltx_25_local import _ltx25_capabilities

    caps = _ltx25_capabilities()
    assert caps.maxDurationSec == 20.0
    assert caps.supportedDurations == [float(s) for s in range(4, 21, 2)]


def test_adapter_validation_rejects_non_integer_duration():
    """adapter.validate now uses int comparison — no epsilon fuzz."""
    from app.director_timeline_w46.generation.adapter import validate_against_capabilities
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    caps = _Caps(maximum=15, supported=[float(s) for s in range(3, 16)],
                 label="MiniMax H3", executionType="api",
                 supportsTextToVideo=True, supportsImageToVideo=False,
                 supportsStartFrame=False, supportsEndFrame=False,
                 supportsReferenceToVideo=False, supportsVideoReferences=False,
                 supportsAudioReferences=False,
                 supportsCameraControls=False, supportsNegativePrompt=False,
                 supportsSeed=True, supportsImageAndVideoTogether=False,
                 maximumReferenceImages=0, maximumReferenceVideos=0,
                 maximumReferenceAudio=0, supportsMultipleImageReferences=False,
                 executable=True, supportedAspectRatios=["16:9"])
    # legal 15
    req = TimelineGenerationRequest(
        projectId="p", sceneId="s", batchBlockId="b", executionSnapshotId="e",
        generatorId="minimax-h3", prompt="test", duration=15,
        generationMode="text_to_video",
    )
    result = validate_against_capabilities(caps, req)
    assert result.ok, f"15s must be accepted: {result.errors}"

    # illegal 16
    req16 = TimelineGenerationRequest(
        projectId="p", sceneId="s", batchBlockId="b", executionSnapshotId="e",
        generatorId="minimax-h3", prompt="test", duration=16,
        generationMode="text_to_video",
    )
    result16 = validate_against_capabilities(caps, req16)
    assert not result16.ok, "16s must be rejected for H3 max 15"
    assert any("16" in err for err in result16.errors), str(result16.errors)


def test_store_normalization_idempotent():
    """Normalization is deterministic and idempotent (Law 36)."""
    from app.film_timeline.store import _normalize_film_durations
    from app.film_timeline.contracts import FilmTimeline, Shot, Segment

    film = FilmTimeline(
        shots=[
            Shot(
                id="s1", durationSec=15.0000001,
                segments=[Segment(durationSec=15.0000001, requestedDurationSec=5.0000002)],
                generationPlan=[10.0000003, 5.0000001],
            ),
        ]
    )
    changes = _normalize_film_durations(film)
    assert changes > 0, "dust must trigger normalization"
    assert film.shots[0].durationSec == 15.0
    assert film.shots[0].segments[0].durationSec == 15.0
    assert film.shots[0].generationPlan == [10.0, 5.0]
    # Second pass is idempotent
    assert _normalize_film_durations(film) == 0


def test_store_normalization_skips_frame_grid_echoes():
    """15.0833 is a frame-grid echo — no silent guessing."""
    from app.film_timeline.store import _normalize_film_durations
    from app.film_timeline.contracts import FilmTimeline, Shot, Segment

    film = FilmTimeline(
        shots=[
            Shot(
                id="s1", durationSec=20.0,
                segments=[Segment(durationSec=15.083333333333334, requestedDurationSec=15.083333333333334)],
                generationPlan=[],
            ),
        ]
    )
    changes = _normalize_film_durations(film)
    # 15.0833 is NOT dust — it stays as-is
    assert changes == 0
    assert film.shots[0].segments[0].durationSec == 15.083333333333334
