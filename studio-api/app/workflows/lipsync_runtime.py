"""Runtime helpers for resilient ComfyUI lip-sync execution."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import settings


def json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _flatten(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [part for item in value.values() for part in _flatten(item)]
    if isinstance(value, (list, tuple, set)):
        return [part for item in value for part in _flatten(item)]
    return [] if value is None else [str(value)]


def summarize_comfy_failure(history_entry: dict) -> str | None:
    """Return a useful, bounded explanation of a ComfyUI failure."""
    if not isinstance(history_entry, dict):
        return None
    status = history_entry.get("status") or {}
    parts = _flatten(status.get("status_str")) + _flatten(status.get("messages"))
    outputs = history_entry.get("outputs") or {}
    if isinstance(outputs, dict):
        for node_output in outputs.values():
            if isinstance(node_output, dict):
                for key in ("text", "string"):
                    parts.extend(_flatten(node_output.get(key)))
    summary = " | ".join(part.strip() for part in parts if part.strip())
    if not summary:
        return None
    lower = summary.lower()
    if "modulenotfounderror" in lower or "decord" in lower:
        return "LatentSync dependency missing: install decord in the ComfyUI Python environment"
    if re.search(r"no face|face not found|unable to detect face", lower):
        return "Lip sync needs a face-forward speaking clip; the source video has no detectable face"
    # Successful Comfy status chatter is not a failure reason.
    if "execution_error" not in lower and "exception" not in lower and "error" not in lower:
        if "execution_success" in lower or status.get("status_str") == "success":
            return "Lip sync produced no discoverable output file after ComfyUI reported success"
    if "traceback" in lower:
        summary = summary.split("traceback", 1)[0].rstrip(" |:")
    return summary[:400]


def _candidate_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_candidate_strings(item))
        return result
    if isinstance(value, (list, tuple)):
        return [item for value_item in value for item in _candidate_strings(value_item)]
    if isinstance(value, str):
        return [value]
    return []


_WIN_OR_POSIX_MP4 = re.compile(
    r"(?:[A-Za-z]:\\(?:[^|<>:\"?*\n\r]+\\)*[^|<>:\"?*\n\r]+\.mp4)|(?:/(?:[^\s|]+\.mp4))",
    re.IGNORECASE,
)


def _output_roots() -> list[Path]:
    primary = Path(settings.comfy_output_dir)
    roots = [primary, Path.cwd() / "output"]
    parent = primary.parent
    if parent.name.lower() == "comfyui-shared":
        alt = parent.parent / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "output"
        if alt.is_dir():
            roots.append(alt)
    # Deduplicate
    seen: set[str] = set()
    out: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out


def _resolve_existing_video(raw: str) -> Path | None:
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        return None
    path = Path(raw)
    roots = _output_roots()
    candidates = [path] if path.is_absolute() else [root / path for root in roots]
    if path.name.lower().startswith("latentsync_") and path.suffix.lower() == ".mp4":
        candidates.extend(root / path.name for root in roots)
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.suffix.lower() in {".mp4", ".webm", ".mov"}:
                return candidate
        except OSError:
            continue
    return None


def extract_output_path_from_history(history_entry: dict) -> Path | None:
    """Find a materialized video path in common ComfyUI output representations."""
    if not isinstance(history_entry, dict):
        return None
    outputs = history_entry.get("outputs") or {}
    keys = {"video_path", "text", "string", "gifs", "videos"}
    if isinstance(outputs, dict):
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for key, value in node_output.items():
                if key not in keys:
                    continue
                values = value if isinstance(value, list) else [value]
                for item in values:
                    candidates = _candidate_strings(item)
                    if isinstance(item, dict) and item.get("filename"):
                        subfolder = item.get("subfolder") or ""
                        candidates.append(str(Path(subfolder) / item["filename"]))
                    for raw in candidates:
                        found = _resolve_existing_video(raw)
                        if found:
                            return found

    # D_LatentSyncNode / PreviewAny often echo the absolute path only in status.messages.
    try:
        blob = json_dumps_safe(history_entry)
    except Exception:
        blob = " | ".join(_flatten(history_entry.get("status")) + _flatten(outputs))
    for match in _WIN_OR_POSIX_MP4.findall(blob):
        found = _resolve_existing_video(match.replace("\\\\", "\\"))
        if found:
            return found

    # Last resort: newest latentsync_*_out.mp4 under Comfy output (recent success).
    out_dir = Path(settings.comfy_output_dir)
    try:
        recent = sorted(
            out_dir.glob("latentsync_*_out.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        recent = []
    if recent:
        return recent[0]
    return None


def prepare_still_face_video(
    *, image_path: Path, audio_path: Path, dest: Path, fps: int = 25
) -> Path:
    """Create a still-image H.264 video with the supplied audio track."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Cannot prepare still face video: ffmpeg is not installed or not on PATH")
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-shortest",
        str(dest),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"Failed to prepare still face video with ffmpeg: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else f"exit code {result.returncode}"
        raise RuntimeError(f"Failed to prepare still face video with ffmpeg: {reason[:300]}")
    return dest


def lipsync_no_output_error(history_entry: dict | None) -> RuntimeError:
    summary = summarize_comfy_failure(history_entry or {})
    return RuntimeError(summary or "Lip sync produced no output")


def _comfy_python() -> Path | None:
    override = os.environ.get("STUDIO_COMFY_PYTHON", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    # Comfy Desktop standalone env (current product install on this workstation).
    candidates = [
        Path.home()
        / "AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/standalone-env/python.exe",
        Path.home()
        / "AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/Scripts/python.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _latentsync_root() -> Path | None:
    override = os.environ.get("STUDIO_LATENTSYNC_ROOT", "").strip()
    if override and Path(override).is_dir():
        return Path(override)
    candidate = (
        Path.home()
        / "AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI/custom_nodes/ComfyUI_LatentSync"
    )
    return candidate if candidate.is_dir() else None


def run_latentsync_direct(
    *,
    video_path: Path,
    audio_path: Path,
    dest: Path,
    seed: int = 42,
) -> Path:
    """Run LatentSync inference.py directly (bypasses stale Comfy node module cache)."""
    py = _comfy_python()
    root = _latentsync_root()
    if not py or not root:
        raise RuntimeError(
            "Direct LatentSync runner unavailable: set STUDIO_COMFY_PYTHON and STUDIO_LATENTSYNC_ROOT"
        )
    infer = root / "scripts" / "inference.py"
    unet = root / "configs" / "unet" / "second_stage.yaml"
    ckpt = root / "checkpoints" / "latentsync_unet.pt"
    whisper = root / "checkpoints" / "whisper" / "tiny.pt"
    scheduler = root / "configs"
    for required in (infer, unet, ckpt, whisper, scheduler, video_path, audio_path):
        if not Path(required).exists():
            raise RuntimeError(f"LatentSync direct runner missing required path: {required}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["TORCHDYNAMO_DISABLE"] = "1"
    env["TORCH_COMPILE_DISABLE"] = "1"
    cmd = [
        str(py),
        str(infer),
        "--unet_config_path",
        str(unet),
        "--inference_ckpt_path",
        str(ckpt),
        "--video_path",
        str(video_path),
        "--audio_path",
        str(audio_path),
        "--video_out_path",
        str(dest),
        "--seed",
        str(seed),
        "--scheduler_config_path",
        str(scheduler),
        "--whisper_ckpt_path",
        str(whisper),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0 or not dest.is_file():
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else f"exit {result.returncode}"
        raise RuntimeError(f"Direct LatentSync inference failed: {reason[:400]}")
    return dest
