"""Tests for MAGI video upscaling module."""

from __future__ import annotations

import pytest
from app.magi.upscaling import (
    _parse_resolution,
    _realesrgan_bin,
    upscale_frame,
    upscale_asset,
)


class TestResolutionParsing:
    """Verify resolution string parsing."""

    def test_720p(self):
        assert _parse_resolution("720p") == (1280, 720)
        assert _parse_resolution("720P") == (1280, 720)

    def test_1080p(self):
        assert _parse_resolution("1080p") == (1920, 1080)
        assert _parse_resolution("1080P") == (1920, 1080)

    def test_1440p(self):
        assert _parse_resolution("1440p") == (2560, 1440)

    def test_4k(self):
        assert _parse_resolution("4K") == (3840, 2160)
        assert _parse_resolution("4k") == (3840, 2160)

    def test_8k(self):
        assert _parse_resolution("8K") == (7680, 4320)

    def test_custom_resolution(self):
        assert _parse_resolution("1920x1080") == (1920, 1080)
        assert _parse_resolution("1280x720") == (1280, 720)
        assert _parse_resolution("3840x2160") == (3840, 2160)

    def test_invalid_resolution_defaults(self):
        """Invalid resolution strings should return 1920x1080 default."""
        assert _parse_resolution("") == (1920, 1080)
        assert _parse_resolution("invalid") == (1920, 1080)
        assert _parse_resolution("abcxdef") == (1920, 1080)

    def test_malformed_custom(self):
        """Malformed custom strings should default."""
        assert _parse_resolution("x") == (1920, 1080)
        assert _parse_resolution("1920x") == (1920, 1080)
        assert _parse_resolution("x1080") == (1920, 1080)


class TestRealesrganBinary:
    """Verify Real-ESRGAN binary discovery."""

    def test_binary_discovery(self):
        """Binary may or may not be found; function should not crash."""
        result = _realesrgan_bin()
        # Either None or a valid path string
        assert result is None or isinstance(result, str)

    def test_binary_path_valid(self):
        """If found, path must point to an existing file."""
        result = _realesrgan_bin()
        if result is not None:
            from pathlib import Path
            assert Path(result).is_file(), f"Binary not found at {result}"


class TestUpscaleFrame:
    """Verify upscale_frame function dispatch."""

    def test_gpu_request_does_not_silently_become_ffmpeg(self, tmp_path, monkeypatch):
        from app.magi import realesrgan_runtime
        from app.magi.upscaling import ENGINE_GPU, CREATOR_GPU_UNAVAILABLE

        monkeypatch.setattr(realesrgan_runtime, "readiness", lambda: {"realesrganReady": False})
        dest = tmp_path / "out.mp4"
        with pytest.raises(RuntimeError, match="unavailable"):
            upscale_frame(str(tmp_path / "missing.mp4"), str(dest), engine=ENGINE_GPU)
        assert not dest.exists()
        assert "unavailable" in CREATOR_GPU_UNAVAILABLE.lower()


class TestUpscaleAsset:
    """Verify upscale_asset function."""

    def test_requires_valid_asset(self):
        from app.db import SessionLocal, init_db
        from app.magi.upscaling import upscale_asset

        init_db()
        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="not found"):
                upscale_asset(db, "no-project", "missing-asset", "ffmpeg-scale", "lanczos", "1920x1080")
        finally:
            db.close()
