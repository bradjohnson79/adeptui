"""Film Timeline reference tags and cancelled-render continuity."""

from __future__ import annotations

import pytest

from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.film_timeline.contracts import ReferenceAsset, Segment
from app.film_timeline.orchestrator import legal_timeline_resolution
from app.film_timeline.references import (
    apply_cancelled_segment,
    canonical_tag,
    duplicate_tag,
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
