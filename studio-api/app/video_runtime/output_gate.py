"""Output validation gate — jobs are not completed until media is playable."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class OutputGateResult:
    passed: bool
    status: str
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "checks": dict(self.checks),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "message": self.message,
        }


def _ffprobe_json(path: Path) -> dict[str, Any] | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration,size:stream=codec_type,codec_name,width,height,nb_frames",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return json.loads(proc.stdout or "{}")
    except Exception:  # noqa: BLE001
        return None


def wait_file_stable(path: Path, *, settle_sec: float = 0.6, rounds: int = 3) -> bool:
    if not path.is_file():
        return False
    last = -1
    for _ in range(rounds):
        size = path.stat().st_size
        if size > 0 and size == last:
            return True
        last = size
        time.sleep(settle_sec)
    return path.is_file() and path.stat().st_size > 0


def comfy_output_predates_job(
    path: Path | str,
    job_created_at: datetime | None,
    *,
    slack_sec: float = 2.0,
) -> bool:
    """True when media is older than the job — leftover / cached Comfy output.

    shutil.copy2 preserves source mtime, so a dest copied from a prior take
    still fails this check. A file written for this job does not.
    """
    if job_created_at is None:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    try:
        mtime = p.stat().st_mtime
        created = (
            job_created_at.replace(tzinfo=timezone.utc).timestamp()
            if job_created_at.tzinfo is None
            else job_created_at.timestamp()
        )
    except (OSError, OverflowError, ValueError):
        return False
    return mtime < created - max(0.0, slack_sec)


def validate_video_output(
    path: Path | str,
    *,
    asset_registered: bool = False,
    preview_ready: bool = False,
    expect_min_duration: float = 0.05,
) -> OutputGateResult:
    p = Path(path)
    checks: dict[str, bool] = {
        "FILE_EXISTS": p.is_file(),
        "FILE_STABLE": False,
        "NONZERO_SIZE": False,
        "CONTAINER_VALID": False,
        "VIDEO_STREAM_PRESENT": False,
        "AUDIO_STREAM_PRESENT": False,  # WARNING only — not required for gate pass
        "DURATION_VALID": False,
        "DIMENSIONS_VALID": False,
        "FRAME_COUNT_VALID": True,  # optional when ffprobe omits nb_frames
        "CODEC_PLAYABLE": False,
        "ASSET_REGISTERED": asset_registered,
        "PREVIEW_READY": preview_ready or True,  # preview optional for gate pass
    }
    warnings: list[str] = []
    meta: dict[str, Any] = {}

    if not checks["FILE_EXISTS"]:
        return OutputGateResult(
            passed=False,
            status="output_missing",
            checks=checks,
            message="Output file does not exist.",
        )

    checks["FILE_STABLE"] = wait_file_stable(p)
    size = p.stat().st_size if p.is_file() else 0
    checks["NONZERO_SIZE"] = size > 0
    meta["sizeBytes"] = size
    if not checks["NONZERO_SIZE"]:
        return OutputGateResult(
            passed=False,
            status="output_invalid",
            checks=checks,
            message="Output file is zero bytes.",
            metadata=meta,
        )

    probe = _ffprobe_json(p)
    playable_ext = p.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv", ".gif"}
    if probe is None:
        # Soft pass with warning when ffprobe unavailable — still require nonzero stable file.
        checks["CONTAINER_VALID"] = playable_ext
        checks["VIDEO_STREAM_PRESENT"] = playable_ext
        checks["DURATION_VALID"] = playable_ext
        checks["DIMENSIONS_VALID"] = playable_ext
        checks["CODEC_PLAYABLE"] = playable_ext
        warnings.append("ffprobe unavailable; container checks are extension-based only.")
    else:
        fmt = probe.get("format") or {}
        streams = probe.get("streams") or []
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        checks["CONTAINER_VALID"] = True
        checks["VIDEO_STREAM_PRESENT"] = bool(video_streams)
        checks["AUDIO_STREAM_PRESENT"] = bool(audio_streams)
        duration = float(fmt.get("duration") or 0) if fmt.get("duration") else 0.0
        meta["durationSec"] = duration
        checks["DURATION_VALID"] = duration >= expect_min_duration
        if audio_streams:
            aus = audio_streams[0]
            meta["audioCodec"] = aus.get("codec_name")
            meta["audioChannels"] = aus.get("channels")
            meta["audioSampleRate"] = aus.get("sample_rate")
            if aus.get("nb_frames") not in (None, "N/A"):
                try:
                    meta["audioFrameCount"] = int(aus.get("nb_frames"))
                except (TypeError, ValueError):
                    pass
        else:
            # No audio stream — warn so silent outputs are visible. This is
            # NOT a gate failure: generators without native audio may
            # legitimately produce video-only output.
            warnings.append("No audio stream present in the output file.")
        if video_streams:
            vs = video_streams[0]
            w = int(vs.get("width") or 0)
            h = int(vs.get("height") or 0)
            meta["width"] = w
            meta["height"] = h
            meta["codec"] = vs.get("codec_name")
            checks["DIMENSIONS_VALID"] = w > 0 and h > 0
            codec = str(vs.get("codec_name") or "").lower()
            checks["CODEC_PLAYABLE"] = codec in {
                "h264",
                "avc1",
                "vp8",
                "vp9",
                "av1",
                "hevc",
                "h265",
                "mpeg4",
                "gif",
            } or playable_ext
            nb = vs.get("nb_frames")
            if nb not in (None, "N/A"):
                try:
                    frames = int(nb)
                    meta["frameCount"] = frames
                    checks["FRAME_COUNT_VALID"] = frames > 0
                except (TypeError, ValueError):
                    pass
        else:
            checks["DIMENSIONS_VALID"] = False
            checks["CODEC_PLAYABLE"] = False

    required = [
        "FILE_EXISTS",
        "FILE_STABLE",
        "NONZERO_SIZE",
        "CONTAINER_VALID",
        "VIDEO_STREAM_PRESENT",
        "DURATION_VALID",
        "DIMENSIONS_VALID",
        "CODEC_PLAYABLE",
    ]
    failed = [k for k in required if not checks.get(k)]
    if failed:
        status = "output_unplayable" if "CODEC_PLAYABLE" in failed or "VIDEO_STREAM_PRESENT" in failed else "output_invalid"
        return OutputGateResult(
            passed=False,
            status=status,
            checks=checks,
            warnings=warnings,
            metadata=meta,
            message="Output gate failed: " + ", ".join(failed),
        )

    if not asset_registered:
        warnings.append("Asset not yet registered.")
        return OutputGateResult(
            passed=True,
            status="completed_with_warning",
            checks=checks,
            warnings=warnings,
            metadata=meta,
            message="Media validated; asset registration pending.",
        )

    status = "completed_with_warning" if warnings else "completed"
    return OutputGateResult(
        passed=True,
        status=status,
        checks=checks,
        warnings=warnings,
        metadata=meta,
        message="Output gate passed.",
    )


def maybe_create_poster(path: Path, dest: Path | None = None) -> Path | None:
    """Best-effort poster frame via ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not path.is_file():
        return None
    out = dest or path.with_suffix(".poster.jpg")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-ss",
                "00:00:00.5",
                "-vframes",
                "1",
                str(out),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        return out if out.is_file() and out.stat().st_size > 0 else None
    except Exception:  # noqa: BLE001
        return None


def maybe_create_proxy(path: Path, dest: Path | None = None) -> Path | None:
    """Best-effort lower-bitrate H.264 proxy for browser playback."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not path.is_file():
        return None
    if path.suffix.lower() == ".mp4" and path.stat().st_size < 40_000_000:
        return path  # master already small enough
    out = dest or path.with_name(path.stem + "_proxy.mp4")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(out),
            ],
            capture_output=True,
            timeout=600,
            check=False,
        )
        return out if out.is_file() and out.stat().st_size > 0 else None
    except Exception:  # noqa: BLE001
        return None
