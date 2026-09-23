"""ffmpeg temporal clip extract. Reuses the last-frame ffmpeg binary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFMPEG_MISSING")
    return found


def extract_window(
    video_path: str,
    dest_path: str,
    *,
    start_sec: float,
    duration_sec: float,
) -> str:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-ss",
        f"{max(0.0, float(start_sec)):.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{max(0.1, float(duration_sec)):.3f}",
        "-c:v",
        "libx264",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "clip extract failed")[:500])
    return str(dest)


def extract_review_clip(
    video_path: str,
    dest_path: str,
    *,
    start_sec: float = 0.0,
    duration_sec: float = 3.0,
    width: int = 512,
    fps: int = 2,
) -> str:
    """Short low-res window for VideoChat3. Full-res clips OOM SDPA (~100GB)."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-ss",
        f"{max(0.0, float(start_sec)):.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{max(0.5, float(duration_sec)):.3f}",
        "-vf",
        f"scale={int(width)}:-2,fps={int(fps)}",
        "-c:v",
        "libx264",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "review clip extract failed")[:500])
    return str(dest)


def extract_av_clip(
    video_path: str,
    dest_path: str,
    *,
    start_sec: float = 0.0,
    duration_sec: float = 4.0,
    width: int = 512,
    fps: int = 2,
) -> str:
    """Audio-RETAINING review clip for Qwen2.5-Omni (Media Intelligence).

    Unlike extract_review_clip this does NOT pass ``-an``: the audio track is
    kept (re-encoded to 16 kHz mono AAC, exactly what Qwen's audio encoder
    consumes after resampling). Video gets the same low-res OOM guard. When the
    source has no audio stream the audio flags are harmless no-ops and the clip
    is video-only — the worker reports audioStreamCount=0 as evidence.
    """
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-ss",
        f"{max(0.0, float(start_sec)):.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{max(0.5, float(duration_sec)):.3f}",
        "-vf",
        f"scale={int(width)}:-2,fps={int(fps)}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "av clip extract failed")[:500])
    return str(dest)


def sample_timestamps_for_full_clip_review(
    duration_sec: float,
    *,
    broad_count: int = 6,
    dense_end_sec: float = 3.0,
    dense_fps: float = 2.0,
) -> list[float]:
    """Efficient sampling plan: broad temporal coverage + denser end-of-shot.

    Does not extract every frame. Callers may pass these stamps to perception
    helpers or record them on the packet for Continuity Challenge evidence.
    """
    dur = max(0.1, float(duration_sec))
    stamps: list[float] = []
    n = max(2, int(broad_count))
    for i in range(n):
        t = (i / (n - 1)) * max(0.0, dur - 0.05)
        stamps.append(round(t, 3))
    end_start = max(0.0, dur - float(dense_end_sec))
    step = 1.0 / max(0.5, float(dense_fps))
    t = end_start
    while t < dur - 0.01:
        stamps.append(round(t, 3))
        t += step
    stamps.append(round(max(0.0, dur - 0.05), 3))
    out: list[float] = []
    seen: set[float] = set()
    for s in sorted(stamps):
        key = round(s, 2)
        if key in seen:
            continue
        seen.add(key)
        out.append(float(s))
    return out


def extract_full_clip_review(
    video_path: str,
    dest_path: str,
    *,
    duration_sec: float,
    width: int = 512,
    fps: int = 2,
) -> str:
    """Low-res full-clip extract for ~15s Temporal Continuity review (OOM guard)."""
    return extract_review_clip(
        video_path,
        dest_path,
        start_sec=0.0,
        duration_sec=max(0.5, float(duration_sec)),
        width=width,
        fps=fps,
    )


def continuity_sample_times(duration_sec: float, count: int) -> list[float]:
    """Even stamps from the start of this window through its last moment.

    The count is chosen by benchmark. The first stamp is the opening and the
    last stamp is the end of this same clip, not another take.
    """
    dur = max(0.1, float(duration_sec))
    n = max(2, min(16, int(count)))
    # Stay inside the clip. A seek on the final timestamp can land past the last frame.
    last = max(0.0, dur - min(0.25, dur / 2.0))
    return [round((i / (n - 1)) * last, 3) for i in range(n)]


def extract_continuity_frames(
    video_path: str,
    dest_dir: str,
    *,
    duration_sec: float,
    count: int,
    height: int,
) -> tuple[list[str], list[float]]:
    """Disposable stills for Omni. The source take file is not modified.

    The proxy directory must not be the take's own folder. Audio is not copied.
    """
    source = Path(video_path)
    if not source.is_file():
        raise RuntimeError("SOURCE_VIDEO_MISSING")
    dest = Path(dest_dir)
    if dest.resolve() == source.resolve().parent:
        raise RuntimeError("REVIEW_PROXY_MUST_NOT_SIT_BESIDE_TAKE")
    dest.mkdir(parents=True, exist_ok=True)
    times = continuity_sample_times(duration_sec, count)
    height_px = int(height)
    if height_px < 144 or height_px > 720:
        raise RuntimeError("REVIEW_PROXY_HEIGHT_OUT_OF_RANGE")
    paths: list[str] = []
    for index, stamp in enumerate(times):
        frame = dest / f"frame_{index:02d}.jpg"
        cmd = [
            ffmpeg_bin(),
            "-y",
            "-ss",
            f"{max(0.0, float(stamp)):.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale=-2:{height_px}",
            "-q:v",
            "3",
            "-update",
            "1",
            str(frame),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0 or not frame.is_file() or frame.stat().st_size < 32:
            # The end stamp can sit past the last decodable frame. Step back once.
            earlier = max(0.0, float(stamp) - 0.2)
            cmd[cmd.index("-ss") + 1] = f"{earlier:.3f}"
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            times[index] = round(earlier, 3)
        if proc.returncode != 0 or not frame.is_file() or frame.stat().st_size < 32:
            detail = (proc.stderr or proc.stdout or "frame extract failed")
            raise RuntimeError(detail[-500:])
        paths.append(str(frame.resolve()))
    return paths, times


def cleanup_extracted_clip(path: str | None, *, source_path: str | None = None) -> bool:
    """Remove a review/window extract. Never deletes the source approved MP4."""
    if not path:
        return False
    dest = Path(path)
    if source_path and Path(source_path).resolve() == dest.resolve():
        return False
    if dest.suffix.lower() != ".mp4":
        return False
    name = dest.name
    if (
        ".review512." not in name
        and ".avreview512." not in name
        and "_interval_" not in name
        and "_automatic" not in name
        and "_fullclip" not in name
        and "_every_batch" not in name
    ):
        # Cadence windows are named {batchId}_{cadence}.mp4 under assets/.../temporal/
        if "temporal" not in dest.parts:
            return False
    try:
        dest.unlink(missing_ok=True)
        return not dest.exists()
    except OSError:
        return False
