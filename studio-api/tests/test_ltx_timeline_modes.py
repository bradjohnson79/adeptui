"""LTX 2.5 Timeline modes follow the installed sound-on workflow."""

from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.film_timeline.orchestrator import FilmTimelineError, _fold_legacy_production, plan_ltx_generation
from app.video_runtime.legal_canvas import ltx_execution_frames


def _request(**kwargs) -> TimelineGenerationRequest:
    body = dict(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="e",
        generatorId="ltx-2.5-distilled",
        prompt="a lantern swings",
        duration=4,
        generationMode="text_to_video",
    )
    body.update(kwargs)
    return TimelineGenerationRequest(**body)


def test_ltx_capabilities_match_the_sound_on_path():
    caps = Ltx25LocalAdapter().capabilities
    assert caps.supportsTextToVideo is True
    assert caps.supportsImageToVideo is True
    assert caps.supportsStartFrame is True
    assert caps.supportsThreeFrame is False
    assert caps.supportsReferenceToVideo is False
    assert caps.supportsEndFrame is True
    assert caps.continuationMode == "hard"
    assert caps.maximumReferenceImages == 0


def test_text_mode_needs_no_image_and_three_frames_fail_closed():
    adapter = Ltx25LocalAdapter()
    text = adapter.validate(_request(providerOptions={"ltxMode": "text"}))
    assert not any(err.startswith("LTX_START_FRAME_REQUIRED") for err in text.errors)
    missing = adapter.validate(_request(generationMode="image_to_video", providerOptions={"ltxMode": "one_frame"}))
    assert any(err.startswith("LTX_START_FRAME_REQUIRED") for err in missing.errors)
    three = adapter.validate(_request(providerOptions={"ltxMode": "three_frame"}))
    assert any(err.startswith("LTX_THREE_FRAME_UNSUPPORTED") for err in three.errors)
    missing_end = adapter.validate(
        _request(
            generationMode="image_to_video",
            startImageAssetId="still-1",
            providerOptions={"ltxMode": "start_end"},
        )
    )
    assert any(err.startswith("LTX_END_FRAME_REQUIRED") for err in missing_end.errors)


def test_plan_drops_semantic_refs_and_uses_one_start_image():
    slots = [
        {"role": "character", "assetId": "hero"},
        {"role": "place", "assetId": "room"},
        {"role": "prop", "assetId": "lantern"},
    ]
    text = plan_ltx_generation(
        ltx_mode="text",
        ltx_start_asset_id="hero",
        opening_still="",
        slots=slots,
        start="hero",
    )
    assert text["mode"] == "text_to_video"
    assert text["start"] is None
    assert text["slots"] == []

    one = plan_ltx_generation(
        ltx_mode="one_frame",
        ltx_start_asset_id="still-1",
        opening_still="",
        slots=slots,
        start=None,
    )
    assert one["mode"] == "image_to_video"
    assert one["start"] == "still-1"
    assert one["slots"] == []

    continued = plan_ltx_generation(
        ltx_mode="text",
        ltx_start_asset_id="",
        opening_still="tail-frame",
        slots=slots,
        start=None,
    )
    assert continued["mode"] == "image_to_video"
    assert continued["start"] == "tail-frame"
    assert continued["ltxMode"] == "one_frame"
    assert continued["end"] is None

    paired = plan_ltx_generation(
        ltx_mode="start_end_frame",
        ltx_start_asset_id="open",
        ltx_end_asset_id="close",
        opening_still="",
        slots=slots,
        start=None,
    )
    assert paired["ltxMode"] == "start_end"
    assert paired["start"] == "open"
    assert paired["end"] == "close"
    assert paired["slots"] == []

    continued_with_end = plan_ltx_generation(
        ltx_mode="start_end",
        ltx_start_asset_id="stale",
        ltx_end_asset_id="close",
        opening_still="tail-frame",
        slots=[],
        start=None,
    )
    assert continued_with_end["start"] == "tail-frame"
    assert continued_with_end["end"] == "close"
    assert continued_with_end["ltxMode"] == "start_end"

    continued_without_end = plan_ltx_generation(
        ltx_mode="one_frame",
        ltx_start_asset_id="stale",
        ltx_end_asset_id="close",
        opening_still="tail-frame",
        slots=[],
        start=None,
    )
    assert continued_without_end["end"] is None
    assert continued_without_end["ltxMode"] == "one_frame"


def test_plan_refuses_a_missing_start_and_three_frames():
    try:
        plan_ltx_generation(ltx_mode="one_frame", ltx_start_asset_id="", opening_still="", slots=[], start=None)
    except FilmTimelineError as exc:
        assert exc.code == "LTX_START_FRAME_REQUIRED"
    else:
        raise AssertionError("missing start frame must fail")
    try:
        plan_ltx_generation(ltx_mode="three_frame", ltx_start_asset_id="", opening_still="", slots=[], start=None)
    except FilmTimelineError as exc:
        assert exc.code == "LTX_THREE_FRAME_UNSUPPORTED"
    else:
        raise AssertionError("three-frame must fail")


def test_legacy_production_ids_write_as_ltx():
    model, options = _fold_legacy_production("text-to-video", None)
    assert model == "ltx-2.5-distilled"
    assert options == {"ltxMode": "text"}
    model, options = _fold_legacy_production("one-frame", {"ltxMode": "start_end"})
    assert model == "ltx-2.5-distilled"
    assert options["ltxMode"] == "start_end"
    model, options = _fold_legacy_production("three-frame", None)
    assert options["ltxMode"] == "three_frame"
    kept, same = _fold_legacy_production("minimax-h3-i2v-local", None)
    assert kept == "minimax-h3-i2v-local"
    assert same is None


def test_timeline_whole_seconds_use_the_nearest_legal_frame_count():
    assert ltx_execution_frames(4, 24) == 97
    assert ltx_execution_frames(5, 24) == 121
    assert ltx_execution_frames(97 / 24, 24) == 97
