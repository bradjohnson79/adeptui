"""Validated FFmpeg operations; arbitrary command execution is not exposed."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..media_ops import mux_audio, stitch_videos


class FFmpegAdapter(Protocol):
    def stitch(self, paths: list[Path], out_path: Path, fps: int = 24) -> Path: ...

    def mux(self, video: Path, audio: Path, out_path: Path) -> Path: ...


class ExistingFFmpegAdapter:
    """Delegate only validated media operations to the existing helpers."""

    def stitch(
        self, paths: list[Path], out_path: Path, fps: int = 24
    ) -> Path:
        return stitch_videos(paths, out_path, fps)

    def mux(self, video: Path, audio: Path, out_path: Path) -> Path:
        return mux_audio(video, audio, out_path)
