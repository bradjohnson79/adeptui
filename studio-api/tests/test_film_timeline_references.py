"""Film Timeline reference tags and cancelled-render continuity."""

from __future__ import annotations

import pytest

from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_base_optimized import MiniMaxH3BaseOptimizedAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.film_timeline.contracts import FilmTimeline, ReferenceAsset, Segment, Shot
from app.film_timeline.orchestrator import legal_timeline_resolution
from app.film_timeline.publish_media import ready_stitch_id
from app.film_timeline.references import (
    apply_cancelled_segment,
    canonical_tag,
    duplicate_tag,
    generation_role,
    provider_reference_slots,
)


def test_film_timeline_uses_a_legal_h3_canvas_not_the_scene_size():
    token = legal_timeline_resolution("minimax-h3-i2v-local")
    assert token == "1152x640"
    width, height = (int(part) for part in token.split("x"))
    assert width % 32 == 0 and height % 32 == 0


def test_v1_tag_grammar():
    assert canonical_tag("character", "cade") == "@Cade"
    assert canonical_tag("environment", "#Stars") == "#Stars"
    assert canonical_tag("prop", "lantern") == "%Lantern"
    assert canonical_tag("video", "plate") == "*Plate"
    assert canonical_tag("audio", "voice") == "&Voice"


def test_empty_and_duplicate_tags():
    with pytest.raises(ValueError):
        canonical_tag("character", "   ")
    rows = [ReferenceAsset(id="a", type="character", assetId="1", tag="@Cade")]
    assert duplicate_tag(rows, "@Cade") is not None
    assert duplicate_tag(rows, "@Cade", except_id="a") is None


def test_ltx_does_not_receive_unsupported_video_or_audio():
    refs = [
        ReferenceAsset(type="character", assetId="c", tag="@Cade"),
        ReferenceAsset(type="video", assetId="v", tag="*Plate"),
        ReferenceAsset(type="audio", assetId="a", tag="&Voice"),
    ]
    ltx = provider_reference_slots(refs, Ltx25LocalAdapter().capabilities)
    assert [item.assetId for item in ltx] == ["c"]
    h3 = provider_reference_slots(refs, MiniMaxH3I2VLocalAdapter().capabilities)
    assert [item.assetId for item in h3] == ["c", "v", "a"]


def test_storyboard_frames_reach_h3_as_ordered_place_pictures():
    frames = [
        "a2a91531-bbc3-4861-afca-341bb642bcd6",
        "6a4c073c-5ff8-45b9-941c-4befd998e2da",
        "01a66d02-c541-466a-a909-bf7f4e38a6ef",
    ]
    refs = [
        ReferenceAsset(
            type="environment",
            assetId=asset_id,
            tag=f"#Storyboard{index}",
            source="storyboard:board-1",
            role=f"frame:{index}",
        )
        for index, asset_id in enumerate(frames, start=1)
    ]
    caps = MiniMaxH3BaseOptimizedAdapter().capabilities
    assert caps.maximumReferenceImages >= len(refs)
    kept = provider_reference_slots(refs, caps)
    assert [item.assetId for item in kept] == frames
    assert [generation_role(item.type) for item in kept] == ["place", "place", "place"]
    assert {item.source for item in kept} == {"storyboard:board-1"}


def test_one_completed_clip_is_the_publishable_scene():
    segment = Segment(status="completed", assetId="video-1", durationSec=15)
    film = FilmTimeline(shots=[Shot(segments=[segment])])
    assert ready_stitch_id(film) == "video-1"
    stitched = Segment(status="completed", assetId="video-1")
    other = Segment(status="completed", assetId="video-2")
    multi = FilmTimeline(shots=[Shot(segments=[stitched, other])])
    multi.shots[0].state.stitchStatus = "ready"
    multi.shots[0].state.stitchAssetId = "stitch-1"
    assert ready_stitch_id(multi) == "stitch-1"


def test_cancelled_segment_drops_continuity_and_keeps_the_neighbor():
    cancelled = Segment(status="generating", assetId="partial", lastFrameAssetId="frame")
    cancelled.generationMetadata["continuity"] = {"fingerprint": "v1:partial"}
    kept = Segment(status="completed", assetId="done")
    kept.generationMetadata["continuity"] = {"fingerprint": "v1:done"}
    apply_cancelled_segment(cancelled)
    assert cancelled.status == "cancelled"
    assert cancelled.assetId is None
    assert "continuity" not in cancelled.generationMetadata
    assert kept.generationMetadata["continuity"]["fingerprint"] == "v1:done"
