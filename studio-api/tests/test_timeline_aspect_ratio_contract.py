"""Timeline V2 Aspect Ratio contract — owner-certified D1 aspect unify (2026-09-28).

Stamp history: the Timeline Aspect Ratio Bot A-stamp "HARD-REFUSE H3 non-16:9" is
SUPERSEDED for H3 callers by the owner-certified D1 aspect unify. Proof:
  theme_walk/timeline_v2_h3_director_aspect_unify/00_AUDIT.md:8
      "Timeline Aspect Ratio Bot A-stamp HARD-REFUSE H3 non-16:9 is SUPERSEDED for H3 callers"
  theme_walk/timeline_v2_h3_director_aspect_unify/FYI_TIMELINE_ASPECT_RATIO_BOT.md:3-6
      H3_SUPPORTED_ASPECTS = production ∩ ResolutionSelector; do not reintroduce 16:9-only refuse
  theme_walk/timeline_v2_h3_director_aspect_unify/STATUS.json:4-13
      dim_authority=D1_ResolutionSelector, verdict=COMPLETE,
      supported_shapes = 1:1, 4:3, 16:9, 9:16, 21:9

Current certified contract lives in app/video_runtime/legal_canvas.py:
  H3_SUPPORTED_ASPECTS        legal_canvas.py:890  = 1:1, 4:3, 16:9, 9:16, 21:9
  H3_CAPABILITY_ASPECT_RATIOS legal_canvas.py:896  = ["≈16:9", *H3_SUPPORTED_ASPECTS]
  require_h3_timeline_aspect  legal_canvas.py:928-955 (accepts those, refuses others)
  resolve_h3_resolution_selector legal_canvas.py:699-741 (D1 dim authority, multiple=32)
  check_h3_resolution         legal_canvas.py:849-868 (Scene-canvas passthrough still refused)
"""

from __future__ import annotations

import pytest

from app.video_runtime.legal_canvas import (
    H3_CAPABILITY_ASPECT_RATIOS,
    H3_SUPPORTED_ASPECTS,
    TIMELINE_PRODUCTION_ASPECTS,
    SpecFidelityError,
    assert_h3_legal_resolution,
    check_h3_resolution,
    compile_timeline_canvas,
    require_h3_timeline_aspect,
    require_timeline_aspect,
    resolve_generation_dimensions,
    resolve_h3_megapixel_canvas,
    resolve_h3_resolution_selector,
    resolve_legal_canvas,
)


def test_require_timeline_aspect_accepts_production():
    assert require_timeline_aspect("16:9") == "16:9"
    assert require_timeline_aspect("9:16") == "9:16"


def test_require_timeline_aspect_refuses_empty_custom_unknown():
    with pytest.raises(SpecFidelityError) as ei:
        require_timeline_aspect("")
    assert ei.value.code == "ASPECT_REQUIRED"
    with pytest.raises(SpecFidelityError) as ei:
        require_timeline_aspect("custom")
    assert ei.value.code == "ASPECT_CUSTOM_REFUSED"
    with pytest.raises(SpecFidelityError) as ei:
        require_timeline_aspect("7:5")
    assert ei.value.code == "UNKNOWN_ASPECT"


def test_h3_16_9_megapixel_table_0_7():
    label, w, h = resolve_h3_megapixel_canvas(0.7)
    assert (w, h) == (1152, 640)
    dims = resolve_generation_dimensions(model="minimax-h3", requested_aspect="16:9")
    assert dims["width"] == 1152
    assert dims["height"] == 640
    assert dims["aspect"] == "16:9"


def test_h3_aspect_9_16_is_supported_not_silent_16_9():
    """9:16 is a first-class H3 shape and resolves to its D1 legal canvas 640x1152 @0.7 MP.

    Supersedes the Bot A-stamp assertion (was: H3_ASPECT_UNSUPPORTED for 9:16) —
    proof: FYI_TIMELINE_ASPECT_RATIO_BOT.md:3-6, 00_AUDIT.md:8, STATUS.json:7-13,
    legal_canvas.py:890-896. Intent preserved: 9:16 is never silently coerced to
    16:9 (dims are portrait, not 1152x640).
    """
    assert require_h3_timeline_aspect("9:16") == "9:16"

    dims = resolve_generation_dimensions(model="minimax-h3", requested_aspect="9:16")
    assert dims["aspect"] == "9:16"
    assert (dims["width"], dims["height"]) == (640, 1152)  # D1 @0.7 MP, NOT 1152x640
    assert dims["megapixels"] == 0.7

    canvas = compile_timeline_canvas("minimax-h3", aspect_ratio="9:16")
    assert canvas["aspect"] == "9:16"
    assert (canvas["width"], canvas["height"]) == (640, 1152)

    label, w, h = resolve_h3_megapixel_canvas(0.7, aspect="9:16")
    assert label == "0.7 MP"
    assert (w, h) == (640, 1152)


def test_h3_supports_every_production_shape_and_refuses_the_rest():
    """D1 unify: all five Adept production shapes are legal H3 shapes; others fail closed.

    Proof: legal_canvas.py:885-896 (TIMELINE_PRODUCTION_ASPECTS ∩
    H3_RESOLUTION_SELECTOR_ASPECTS -> H3_SUPPORTED_ASPECTS).
    """
    assert H3_SUPPORTED_ASPECTS == ("1:1", "4:3", "16:9", "9:16", "21:9")
    assert set(H3_SUPPORTED_ASPECTS) == set(TIMELINE_PRODUCTION_ASPECTS)
    for shape in H3_SUPPORTED_ASPECTS:
        assert require_h3_timeline_aspect(shape) == shape
        # Every production shape compiles to an exact D1 legal canvas @0.7 MP.
        dims = resolve_generation_dimensions(model="minimax-h3", requested_aspect=shape)
        assert dims["aspect"] == shape
        assert (dims["width"], dims["height"]) == resolve_h3_resolution_selector(shape, 0.7, multiple=32)
        assert check_h3_resolution(dims["width"], dims["height"]).ok is True

    # Unsupported / non-production shapes still fail closed (no silent mapping).
    for bad in ("2.39:1", "3:2", "2:3", "3:4"):
        with pytest.raises(SpecFidelityError) as ei:
            require_h3_timeline_aspect(bad)
        assert ei.value.code == "H3_ASPECT_UNSUPPORTED"
        with pytest.raises(SpecFidelityError) as ei:
            resolve_generation_dimensions(model="minimax-h3", requested_aspect=bad)
        assert ei.value.code == "H3_ASPECT_UNSUPPORTED"
        with pytest.raises(SpecFidelityError):
            compile_timeline_canvas("minimax-h3", aspect_ratio=bad)


def test_h3_never_accepts_scene_canvas_passthrough():
    """Scene / project canvas is still banned as H3 output (00_AUDIT.md:136-139, 211, 249).

    Kept against the D1 unify so widening H3 shapes never reopens passthrough.
    """
    assert check_h3_resolution(1920, 824).ok is False  # Scene 21:9 canvas
    assert check_h3_resolution(1344, 576).ok is False  # production-pixels 21:9 intent
    with pytest.raises(SpecFidelityError) as ei:
        assert_h3_legal_resolution(1920, 824)
    assert ei.value.code == "H3_RESOLUTION_UNSUPPORTED"
    # A legal H3 21:9 canvas is a D1 ResolutionSelector output, not the Scene canvas.
    assert check_h3_resolution(1312, 576).ok is True
    assert (1920, 824) != (1312, 576)


def test_ltx_9_16_720p_is_704x1248():
    legal = resolve_legal_canvas("ltx-2.5", tier="720p", aspect="9:16")
    assert (legal.width, legal.height) == (704, 1248)
    assert legal.aspect == "9:16"
    dims = compile_timeline_canvas("ltx-2.5", aspect_ratio="9:16", ltx_quality="720p")
    assert (dims["width"], dims["height"]) == (704, 1248)
    assert dims["aspect"] == "9:16"


def test_h3_adapter_supported_aspects_unified():
    from app.director_timeline_w46.generation.adapters.minimax_h3_local import (
        MiniMaxH3LocalAdapter,
    )
    from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import (
        MiniMaxH3I2VLocalAdapter,
    )

    local = list(MiniMaxH3LocalAdapter.capabilities.supportedAspectRatios)
    i2v = list(MiniMaxH3I2VLocalAdapter.capabilities.supportedAspectRatios)
    # Intent preserved: both H3 adapters are unified on ONE aspect list.
    assert local == i2v
    # That list is the single D1 owner (no cloned per-adapter AR table):
    # adapters/minimax_h3_local.py:30-33 and minimax_h3_i2v_local.py:30-33 both
    # return list(H3_CAPABILITY_ASPECT_RATIOS) from legal_canvas.py:896.
    assert local == list(H3_CAPABILITY_ASPECT_RATIOS)
    for shape in H3_SUPPORTED_ASPECTS:
        assert shape in local, f"D1 production shape {shape} missing from H3 caps"
    # Superseded Bot A-stamp asserted 9:16/21:9 NOT in the list — FYI:3-8 forbids that.
    assert "9:16" in local
    assert "21:9" in local
    # Shapes outside the D1 set are still absent (fail closed at capability level).
    assert "2.39:1" not in local
    assert "3:2" not in local


def test_resolution_for_request_h3_9_16_compiles_unsupported_fails_closed():
    """H3 request compile now returns the D1 9:16 canvas; non-production shapes still refuse.

    Supersedes the Bot A-stamp (was: 9:16 -> ValueError). Proof: FYI:3-6, 00_AUDIT.md:8,
    STATUS.json:7-13, legal_canvas.py:890-896 +
    request_builder.py:354-363 (_resolution_for_request H3 -> require_h3_timeline_aspect
    -> resolve_h3_timeline_canvas).
    """
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.registry import get_registry
    from app.director_timeline_w46.generation import request_builder as rb

    caps = get_registry().get("minimax-h3-t2v-local").capabilities
    batch = BatchBlock(id="bb_test", sceneId="sc_test", generatorId="minimax-h3-t2v-local")

    assert rb._resolution_for_request(caps, "9:16", batch, draft_mode=False) == "640x1152"
    assert rb._resolution_for_request(caps, "16:9", batch, draft_mode=False) == "1152x640"
    assert rb._resolution_for_request(caps, "21:9", batch, draft_mode=False) == "1312x576"

    # Unsupported shape (not an Adept production shape) still fails closed.
    with pytest.raises(ValueError, match="does not support picture shape 2.39:1"):
        rb._resolution_for_request(caps, "2.39:1", batch, draft_mode=False)


def test_resolution_for_request_ltx_9_16():
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.registry import get_registry
    from app.director_timeline_w46.generation import request_builder as rb

    # Prefer a known LTX adapter id from registry
    reg = get_registry()
    adapter = None
    for cand in ("ltx-2.5-distilled", "ltx-2.5", "ltx-2.5-full", "ltx-2.5-comfy"):
        try:
            adapter = reg.get(cand)
            break
        except Exception:
            continue
    if adapter is None:
        pytest.skip("no LTX adapter registered")
    caps = adapter.capabilities
    batch = BatchBlock(id="bb_ltx", sceneId="sc_test", generatorId=caps.id, ltxQuality="720p")
    res = rb._resolution_for_request(caps, "9:16", batch, draft_mode=False)
    assert res == "704x1248"
