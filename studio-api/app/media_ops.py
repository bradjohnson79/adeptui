from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Optional


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-2000:]}")


def stitch_videos(paths: list[Path], out_path: Path, fps: int = 24) -> Path:
    if not paths:
        raise ValueError("No videos to stitch")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(paths) == 1:
        out_path.write_bytes(paths[0].read_bytes())
        return out_path

    list_file = out_path.parent / f"_concat_{uuid.uuid4().hex}.txt"
    try:
        lines = []
        for p in paths:
            # ffmpeg concat demuxer requires escaped single quotes
            escaped = str(p.resolve()).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(out_path),
            ]
        )
    except Exception:
        # Re-encode fallback for mismatched codecs
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(out_path),
            ]
        )
    finally:
        if list_file.exists():
            list_file.unlink(missing_ok=True)
    return out_path


def mux_audio(video: Path, audio: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ]
    )
    return out_path


def export_pack(project_json: dict, asset_paths: list[Path], video_paths: list[Path], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project.json").write_text(json.dumps(project_json, indent=2), encoding="utf-8")
    assets_dir = out_dir / "assets"
    videos_dir = out_dir / "videos"
    assets_dir.mkdir(exist_ok=True)
    videos_dir.mkdir(exist_ok=True)
    for p in asset_paths:
        if p.exists():
            (assets_dir / p.name).write_bytes(p.read_bytes())
    for p in video_paths:
        if p.exists():
            (videos_dir / p.name).write_bytes(p.read_bytes())
    return out_dir
