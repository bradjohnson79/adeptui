"""Regression: H3 Render Shot must not hit generic Scene-canvas /32 gate."""

from __future__ import annotations

import json

from app.video_runtime.h3_resolved_generation import resolve_h3_job_dimensions, stamp_resolved_generation
from app.video_runtime.legal_canvas import check_canvas, check_h3_resolution, preflight_spec, resolve_generation_dimensions


def test_h3_check_canvas_never_emits_generic_div32_scene_message():
    checked = check_canvas("minimax-h3", 1920, 824)
    assert not checked.ok
    assert "multiples of 32" not in checked.message
    assert "Adept will not change your canvas" not in checked.message
    assert "MiniMax H3" in checked.message


def test_ltx_still_emits_generic_div32_for_scene_canvas():
    checked = check_canvas("ltx-2.5", 1920, 824)
    assert not checked.ok
    assert "multiples of 32" in checked.message
    assert "Adept will not change your canvas" in checked.message


def test_scene_1920x824_h3_0_7_resolves_1152x640_allowed():
    dims = resolve_generation_dimensions(
        model="minimax-h3-i2v-local",
        project_canvas=(1920, 824),
        draft_mode=False,
    )
    assert (dims["width"], dims["height"]) == (1152, 640)
    assert dims["megapixels"] == 0.7
    # Canvas gate only — duration uses the H3 17k+5 grid elsewhere.
    assert check_h3_resolution(int(dims["width"]), int(dims["height"])).ok
    assert check_canvas("minimax-h3", int(dims["width"]), int(dims["height"])).ok
    # Legal H3 duration: 124 frames = 17*7 + 5 at 24 fps.
    spec = preflight_spec(
        "minimax-h3",
        width=int(dims["width"]),
        height=int(dims["height"]),
        length_seconds=124 / 24,
        fps=24,
        surface="r2v",
    )
    assert spec["ok"], spec["message"]
    assert "multiples of 32" not in (spec["message"] or "")
    assert "Adept will not change your canvas" not in (spec["message"] or "")


def test_resolve_h3_job_dimensions_ignores_scene_shaped_job_params():
    params = {
        "generatorId": "minimax-h3-i2v-local",
        "width": 1920,
        "height": 824,
        "resolution": "1920x824",
        "timelineGeneration": True,
    }
    resolved = resolve_h3_job_dimensions(params, resolved_engine="minimax-h3")
    assert (resolved["width"], resolved["height"]) == (1152, 640)
    assert params["width"] == 1152
    assert params["height"] == 640
    assert params["resolution"] == "1152x640"
    assert params["resolvedGeneration"]["width"] == 1152
    assert params["resolvedGeneration"]["projectCanvasIgnored"] == [1920, 824]
    spec = preflight_spec(
        "minimax-h3",
        width=params["width"],
        height=params["height"],
        length_seconds=124 / 24,
        fps=24,
        surface="r2v",
    )
    assert spec["ok"], spec["message"]
    assert "multiples of 32" not in (spec["message"] or "")


def test_stamp_resolved_generation_single_object():
    dims = resolve_generation_dimensions(model="minimax-h3", draft_mode=False)
    params: dict = {}
    resolved = stamp_resolved_generation(params, dims)
    assert params["resolvedGeneration"] == resolved
    assert json.loads(json.dumps(resolved))["width"] == 1152
