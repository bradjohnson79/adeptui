"""H3 legal canvas: table membership, not mere /32 alignment.

Proves Scene canvas 1920x824 and other /32-but-not-table sizes are rejected
with H3_RESOLUTION_UNSUPPORTED before any Comfy submit.
"""

from __future__ import annotations

import pytest

from app.video_runtime.legal_canvas import (
    H3_MEGAPIXEL_GRID,
    SpecFidelityError,
    assert_h3_legal_resolution,
    check_canvas,
    check_h3_resolution,
    is_h3_legal_pixels,
    resolve_generation_dimensions,
)


class TestH3TableMembership:
    def test_every_table_entry_validates(self):
        for mp, (w, h) in H3_MEGAPIXEL_GRID:
            assert is_h3_legal_pixels(w, h)
            assert check_h3_resolution(w, h).ok
            assert check_canvas("minimax-h3", w, h).ok
            assert check_canvas("minimax-h3-i2v-local", w, h).ok
            assert assert_h3_legal_resolution(w, h) == (w, h)

    def test_1920x824_rejected_not_div32_enough(self):
        # Brad confirmed Scene 21:9 canvas — 1920x824 is NOT /32 and not in table.
        assert 1920 % 32 == 0
        assert 824 % 32 != 0
        checked = check_h3_resolution(1920, 824)
        assert not checked.ok
        assert "1920x824" in checked.message
        with pytest.raises(SpecFidelityError) as exc:
            assert_h3_legal_resolution(1920, 824)
        assert exc.value.code == "H3_RESOLUTION_UNSUPPORTED"

    def test_div32_but_not_in_table_fails(self):
        # 1280x704 is /32 and was historically a "720p class" canvas, but it is
        # NOT an H3 ResolutionSelector entry (table has 1280x736 @ 0.9 MP).
        assert 1280 % 32 == 0 and 704 % 32 == 0
        assert not is_h3_legal_pixels(1280, 704)
        # Certified H3 routing (gate-removal REPORT 3.1): check_canvas routes all
        # minimax-h3* tokens to the H3 table validator, so 1280x704 is rejected
        # with the H3-specific message - never the generic /32 text.
        h3_canvas = check_canvas("minimax-h3", 1280, 704)
        assert not h3_canvas.ok
        assert "MiniMax H3" in h3_canvas.message
        assert "multiples of 32" not in h3_canvas.message
        checked = check_h3_resolution(1280, 704)
        assert not checked.ok
        assert checked.suggestions
        with pytest.raises(SpecFidelityError) as exc:
            assert_h3_legal_resolution(1280, 704)
        assert exc.value.code == "H3_RESOLUTION_UNSUPPORTED"

    def test_1920x1088_is_legal_2mp(self):
        assert check_h3_resolution(1920, 1088).ok

    def test_1152x640_is_default_quality(self):
        dims = resolve_generation_dimensions(model="minimax-h3-i2v-local", draft_mode=False)
        assert (dims["width"], dims["height"]) == (1152, 640)
        assert dims["megapixels"] == 0.7

    def test_project_canvas_ignored_for_h3(self):
        dims = resolve_generation_dimensions(
            model="minimax-h3",
            project_canvas=(1920, 824),
            draft_mode=False,
        )
        assert (dims["width"], dims["height"]) == (1152, 640)
        assert dims["projectCanvasIgnored"] == [1920, 824]

    def test_explicit_illegal_wxh_raises(self):
        with pytest.raises(SpecFidelityError) as exc:
            resolve_generation_dimensions(
                model="minimax-h3-i2v-local",
                requested_quality="1920x824",
            )
        assert exc.value.code == "H3_RESOLUTION_UNSUPPORTED"

    def test_ltx_keeps_own_table(self):
        dims = resolve_generation_dimensions(model="ltx-2.5-distilled", requested_quality="720p")
        assert (dims["width"], dims["height"]) == (1280, 704)
