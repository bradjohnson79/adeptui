"""Timeline 9:16 — per-generator legal canvas compile / honest refuse."""

import pytest

from app.aspect_fps import PRODUCTION_ASPECTS, normalize_production_aspect
from app.director_timeline_w46.contracts import BatchBlock
from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_local import _capabilities as h3_caps
from app.director_timeline_w46.generation.adapters.seedance_api import SeedanceApiAdapter
from app.director_timeline_w46.generation.adapter import validate_against_capabilities
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.request_builder import _resolution_for_request


def test_production_aspects_order():
    assert list(PRODUCTION_ASPECTS) == ["1:1", "4:3", "16:9", "9:16", "21:9"]
    assert normalize_production_aspect("9:16") == "9:16"


def test_ltx_9_16_compiles_704x1248():
    caps = Ltx25LocalAdapter().capabilities
    batch = BatchBlock(id="b", sceneId="s", generatorId="ltx-2.5-distilled")
    assert _resolution_for_request(caps, "16:9", batch, draft_mode=False) == "1280x704"
    assert _resolution_for_request(caps, "9:16", batch, draft_mode=False) == "704x1248"
    assert "704x1248" in (caps.supportedResolutions or [])


def test_h3_9_16_compiles_legal_vertical():
    caps = h3_caps()
    batch = BatchBlock(id="b", sceneId="s", generatorId="minimax-h3-t2v-local")
    assert _resolution_for_request(caps, "16:9", batch, draft_mode=False) == "1152x640"
    assert _resolution_for_request(caps, "9:16", batch, draft_mode=False) == "704x1248"
    assert _resolution_for_request(caps, "9:16", batch, draft_mode=True) == "480x832"
    assert "9:16" in (caps.supportedAspectRatios or [])


def test_seedance_9_16_keeps_label():
    caps = SeedanceApiAdapter().capabilities
    batch = BatchBlock(id="b", sceneId="s", generatorId=caps.id)
    # cheap_preview pathway returns tier labels; aspect survives separately on the request
    assert _resolution_for_request(caps, "9:16", batch, draft_mode=False) in ("720p", caps.finalResolution)
    assert "9:16" in (caps.supportedAspectRatios or [])


def test_wan_is_retired_and_unresolvable():
    from app.director_timeline_w46.generation.registry import get_registry

    reg = get_registry()
    with pytest.raises(Exception):
        reg.resolve_id("wan-local")
