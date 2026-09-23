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


def _probe_has_audio(video: Path) -> bool:
    try:
        from app.editor_mix import probe_has_audio

        return bool(probe_has_audio(video))
    except Exception:
        return False


def stitch_needs_audio_remux(paths: list[Path], out_path: Path) -> bool:
    """True when concat-copy dropped a soundtrack that an input still has."""
    if not out_path.is_file():
        return False
    if _probe_has_audio(out_path):
        return False
    return any(_probe_has_audio(p) for p in paths)


def _audio_preserving_concat_args(paths: list[Path], out_path: Path, fps: int) -> list[str]:
    """Concat video+audio. Silent inputs get anullsrc so AAC is not dropped."""
    args: list[str] = []
    pairs: list[str] = []
    extra_inputs = 0
    for i, path in enumerate(paths):
        args.extend(["-i", str(path)])
        if _probe_has_audio(path):
            pairs.append(f"[{i}:v:0][{i}:a:0]")
        else:
            args.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    "0.1",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=32000",
                ]
            )
            silent = len(paths) + extra_inputs
            extra_inputs += 1
            pairs.append(f"[{i}:v:0][{silent}:a:0]")
    n = len(paths)
    joined = "".join(pairs)
    args.extend(
        [
            "-filter_complex",
            f"{joined}concat=n={n}:v=1:a=1[v][a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
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
    return args


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
        if stitch_needs_audio_remux(paths, out_path):
            remux = out_path.with_name(out_path.stem + "_audio" + out_path.suffix)
            run_ffmpeg(_audio_preserving_concat_args(paths, remux, fps))
            remux.replace(out_path)
    except Exception:
        # Re-encode fallback for mismatched codecs — keep AAC when any input has it.
        if any(_probe_has_audio(p) for p in paths):
            run_ffmpeg(_audio_preserving_concat_args(paths, out_path, fps))
        else:
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
