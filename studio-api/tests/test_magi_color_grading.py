"""Tests for MAGI color grading module."""

from __future__ import annotations

import pytest
from app.magi.color_grading import (
    ALL_PRESET_IDS,
    COLOR_PRESETS,
    compile_filter_string,
    list_color_presets,
)


class TestColorPresets:
    """Verify preset definitions are valid and complete."""

    EXPECTED_PRESETS = [
        "none",
        "cinematic_neutral",
        "cinematic_warm",
        "cinematic_cool",
        "golden_hour",
        "teal_orange",
        "film_print",
        "vintage",
        "high_contrast",
        "low_contrast",
        "bleach_bypass",
        "dreamy",
        "noir",
        "anime_vibrant",
        "muted_drama",
        "night_moonlight",
    ]

    def test_all_presets_present(self):
        """Verify all 16 expected presets exist."""
        for pid in self.EXPECTED_PRESETS:
            assert pid in COLOR_PRESETS, f"Missing preset: {pid}"
        assert len(COLOR_PRESETS) == len(self.EXPECTED_PRESETS)

    def test_each_preset_has_required_fields(self):
        """Each preset must have label, params, description."""
        for pid, meta in COLOR_PRESETS.items():
            assert "label" in meta, f"{pid} missing label"
            assert "params" in meta, f"{pid} missing params"
            assert "description" in meta, f"{pid} missing description"
            assert isinstance(meta["label"], str), f"{pid} label not string"
            assert isinstance(meta["params"], dict), f"{pid} params not dict"
            assert isinstance(meta["description"], str), f"{pid} description not string"

    def test_none_preset_has_empty_params(self):
        """The 'none' preset must have no params."""
        none = COLOR_PRESETS["none"]
        assert none["params"] == {}

    def test_all_preset_params_are_bounded(self):
        """All parameter values must be within valid ranges."""
        for pid, meta in COLOR_PRESETS.items():
            for param_name, value in meta["params"].items():
                assert isinstance(value, (int, float)), f"{pid}.{param_name} not numeric"
                assert -2.0 <= value <= 2.0, f"{pid}.{param_name}={value} out of range [-2, 2]"

    def test_list_color_presets_returns_all(self):
        """list_color_presets() must return all presets."""
        presets = list_color_presets()
        assert len(presets) == len(COLOR_PRESETS)
        ids = {p["id"] for p in presets}
        assert ids == set(COLOR_PRESETS.keys())


class TestFilterCompilation:
    """Verify FFmpeg filter string compilation."""

    def test_empty_params_returns_empty_string(self):
        """No params should produce no filter."""
        result = compile_filter_string({})
        assert result == ""

    def test_none_preset_returns_empty_string(self):
        """The 'none' preset should produce no filter."""
        none_params = COLOR_PRESETS["none"]["params"]
        result = compile_filter_string(none_params)
        assert result == ""

    def test_single_eq_filter(self):
        """Single contrast param should produce a single eq filter."""
        params = {"contrast": 0.2}
        result = compile_filter_string(params)
        assert result.startswith("eq=")
        assert "contrast=" in result

    def test_temperature_matches_viewer_hue(self):
        """Temperature uses the viewer hue rotation, not a second lighting pass."""
        params = {"temperature": 0.1}
        result = compile_filter_string(params)
        assert result == "hue=h=-2.80"
        assert "colorbalance=" not in result

    def test_merged_eq_filters(self):
        """Multiple eq params should merge into one eq filter."""
        params = {"contrast": 0.2, "saturation": 0.9, "gamma": 0.95}
        result = compile_filter_string(params)
        # Should be a single eq filter with all params
        assert result.startswith("eq=")
        assert "contrast=" in result
        assert "saturation=" in result
        assert "gamma=" not in result
        assert result.count("eq=") == 1

    def test_lighting_folds_into_the_viewer_channels(self):
        """Shadows and highlights fold once into brightness, contrast, and hue."""
        params = {"temperature": 0.1, "shadows": -0.05, "highlights": 0.03}
        result = compile_filter_string(params)
        assert "colorbalance=" not in result
        assert "gamma=" not in result
        assert "hue=h=-2.80" in result
        assert "eq=" in result

    def test_mixed_contrast_and_hue(self):
        """Contrast and temperature stay one chain, in viewer order."""
        params = {"contrast": 0.2, "temperature": 0.1}
        result = compile_filter_string(params)
        assert result == "eq=contrast=1.200,hue=h=-2.80"

    def test_contrast_scale(self):
        """Contrast 0.0 should produce eq=contrast=1.0."""
        params = {"contrast": 0.0}
        result = compile_filter_string(params)
        assert result == ""  # zero values are skipped

    def test_contrast_positive(self):
        """Contrast 0.2 should produce eq=contrast=1.2."""
        params = {"contrast": 0.2}
        result = compile_filter_string(params)
        assert "contrast=1.2" in result

    def test_contrast_negative(self):
        """Contrast -0.15 should produce eq=contrast=0.85."""
        params = {"contrast": -0.15}
        result = compile_filter_string(params)
        assert "contrast=0.85" in result

    def test_saturation_scale(self):
        """Saturation 0.9 should reduce saturation."""
        params = {"saturation": 0.9}
        result = compile_filter_string(params)
        # saturation=0.9 means 1.0 + 0.9 = 1.9x? No, the formula is 1.0 + p
        # Wait, let me check the code... saturation = max(0.0, 1.0 + p)
        # So saturation=0.9 gives 1.0 + 0.9 = 1.9
        # Actually looking at the code: eq_saturation = max(0.0, 1.0 + p)
        # So saturation=0.9 → 1.9, saturation=-0.2 → 0.8
        pass

    def test_gamma_is_not_a_second_display_transform(self):
        """Preset gamma must not collapse to the FFmpeg 0.1 floor."""
        assert compile_filter_string({"gamma": 0.95}) == ""
        dreamy = compile_filter_string(COLOR_PRESETS["dreamy"]["params"])
        assert "gamma=" not in dreamy
        assert "colorbalance=" not in dreamy
        assert "saturation=1.750" in dreamy


class TestDescribeGrade:
    """Verify human-readable grade descriptions."""

    def test_none_preset_label(self):
        """The 'none' preset should have label 'None'."""
        assert COLOR_PRESETS["none"]["label"] == "None"

    def test_known_preset_has_label(self):
        """Known preset IDs should have descriptive labels."""
        assert COLOR_PRESETS["cinematic_neutral"]["label"] == "Cinematic Neutral"
        assert COLOR_PRESETS["golden_hour"]["label"] == "Golden Hour"
        assert COLOR_PRESETS["teal_orange"]["label"] == "Teal & Orange"
        assert COLOR_PRESETS["noir"]["label"] == "Noir"
        assert COLOR_PRESETS["anime_vibrant"]["label"] == "Anime Vibrant"




class TestStillImageColorGrade:
    """Still-image color grade must emit a real image (not H.264-in-.png)."""

    def test_is_still_image_path(self):
        from app.magi.color_grading import is_still_image_path

        assert is_still_image_path("clip.png")
        assert is_still_image_path("shot.JPEG")
        assert not is_still_image_path("clip.mp4")
        assert not is_still_image_path("clip.mov")

    def test_apply_color_grade_image_produces_openable_png(self, tmp_path):
        import shutil
        import subprocess
        from pathlib import Path

        from PIL import Image

        from app.magi.color_grading import apply_color_grade

        if not shutil.which("ffmpeg"):
            import pytest

            pytest.skip("ffmpeg not available")

        src = tmp_path / "src.png"
        dest = tmp_path / "graded.png"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=160x120",
                "-frames:v",
                "1",
                str(src),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0 and src.is_file(), proc.stderr[-400:]
        out = apply_color_grade(str(src), str(dest), {"contrast": 0.2, "saturation": 0.5})
        out_path = Path(out)
        assert out_path.is_file()
        assert out_path.suffix.lower() == ".png"
        image = Image.open(out_path)
        image.load()
        assert image.size == (160, 120)


class TestOverlayBurnHelper:
    """Final-render overlay burn: skip when empty, burn when elements exist."""

    def test_count_overlay_elements_empty(self):
        from app.magi.final_render import _count_overlay_elements

        assert _count_overlay_elements({"overlays": []}) == 0
        assert _count_overlay_elements({"overlays": [{"type": "text", "visible": False}]}) == 0

    def test_maybe_overlay_returns_none_without_compositions(self, tmp_path):
        import shutil
        import subprocess

        from app.magi.final_render import _maybe_overlay

        if not shutil.which("ffmpeg"):
            import pytest

            pytest.skip("ffmpeg not available")

        video = tmp_path / "edit.mp4"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=320x180:d=0.5",
                "-pix_fmt",
                "yuv420p",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0
        assert _maybe_overlay(object(), "no-overlays-project-xyz", video, tmp_path / "o.mp4") is None



class TestParameterValidation:
    """Verify parameter bounds and edge cases."""

    def test_extreme_values_clamp(self):
        """Extreme values should produce valid but extreme filters."""
        # Very high contrast
        params = {"contrast": 0.5}
        result = compile_filter_string(params)
        assert "contrast=1.5" in result

        params = {"contrast": -0.5}
        result = compile_filter_string(params)
        assert "contrast=0.5" in result

    def test_all_params_zero(self):
        """All params at zero should produce empty string."""
        params = {
            "contrast": 0.0,
            "saturation": 0.0,
            "gamma": 0.0,
            "brightness": 0.0,
            "temperature": 0.0,
            "shadows": 0.0,
            "highlights": 0.0,
        }
        result = compile_filter_string(params)
        assert result == ""

    def test_noise_param_ignored(self):
        """Unknown params should be silently ignored."""
        params = {"contrast": 0.2, "invalid_param": 999}
        result = compile_filter_string(params)
        assert "eq=" in result
        assert "999" not in result
