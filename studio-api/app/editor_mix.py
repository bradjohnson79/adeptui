"""M3.2g Phase 6 — Editor Suite final mix (video + music/sfx/dialogue stems).

Muxes Editor track audio (dialogue / sfx / ambience / music) onto a primary
video with per-clip gain and timeline offset via ffmpeg. Missing or
placeholder clips are skipped; silent video is replaced by the stem mix.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .media_ops import run_ffmpeg

AUDIO_TRACK_KEYS = ("dialogue", "sfx", "ambience", "music")

PathResolver = Callable[[Optional[str], Optional[str]], Optional[Path]]


@dataclass
class MixStem:
    track: str
    clip_id: str
    path: Path
    start_sec: float
    length_sec: float
    trim_start: float
    gain: float
    asset_id: Optional[str] = None
    label: str = ""


@dataclass
class MixPlan:
    """Pure description of an ffmpeg filter graph (unit-testable)."""

    stems: list[MixStem]
    video_has_audio: bool
    filter_complex: str
    audio_map_label: str  # e.g. "[aout]" or "1:a" when single stem copy
    skipped: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MixResult:
    out_path: Path
    stems_used: list[MixStem]
    skipped: list[dict[str, Any]]
    video_has_audio: bool
    filter_complex: str
    prompt_meta: dict[str, Any]


def probe_has_audio(video: Path) -> bool:
    """Return True when ffprobe reports an audio stream; False on any failure."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0 and "audio" in (proc.stdout or "").lower()
    except Exception:
        return False


def _clip_gain(clip: dict[str, Any]) -> float:
    for key in ("gain", "volume", "vol"):
        if key in clip and clip[key] is not None:
            try:
                g = float(clip[key])
                return max(0.0, g)
            except (TypeError, ValueError):
                pass
    return 1.0


def collect_mix_stems(
    editor_data: dict[str, Any],
    resolve_path: PathResolver,
) -> tuple[list[MixStem], list[dict[str, Any]]]:
    """Gather resolvable audio stems from editor tracks; skip missing gracefully."""
    tracks = editor_data.get("tracks") or {}
    stems: list[MixStem] = []
    skipped: list[dict[str, Any]] = []

    for track_key in AUDIO_TRACK_KEYS:
        for clip in tracks.get(track_key) or []:
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id") or "")
            label = str(clip.get("label") or track_key)
            if clip.get("placeholder"):
                skipped.append(
                    {
                        "track": track_key,
                        "clip_id": clip_id,
                        "reason": "placeholder",
                        "label": label,
                    }
                )
                continue
            asset_id = clip.get("asset_id")
            output_path = clip.get("output_path") or clip.get("path")
            path = resolve_path(
                str(asset_id) if asset_id else None,
                str(output_path) if output_path else None,
            )
            if path is None or not path.is_file():
                skipped.append(
                    {
                        "track": track_key,
                        "clip_id": clip_id,
                        "reason": "missing_file",
                        "asset_id": asset_id,
                        "label": label,
                    }
                )
                continue
            try:
                start = float(clip.get("start") or 0.0)
            except (TypeError, ValueError):
                start = 0.0
            try:
                length = float(clip.get("length") or 0.0)
            except (TypeError, ValueError):
                length = 0.0
            try:
                trim_start = float(clip.get("trim_start") or 0.0)
            except (TypeError, ValueError):
                trim_start = 0.0
            stems.append(
                MixStem(
                    track=track_key,
                    clip_id=clip_id,
                    path=path,
                    start_sec=max(0.0, start),
                    length_sec=max(0.0, length),
                    trim_start=max(0.0, trim_start),
                    gain=_clip_gain(clip),
                    asset_id=str(asset_id) if asset_id else None,
                    label=label,
                )
            )
    return stems, skipped


def _adelay_ms(start_sec: float) -> int:
    return max(0, int(round(start_sec * 1000)))


def build_mix_plan(stems: list[MixStem], *, video_has_audio: bool) -> MixPlan:
    """Construct an ffmpeg filter_complex for video + timed/gained stems.

    Input 0 is always the primary video. Stem files are inputs 1..N in order.
    """
    if not stems:
        return MixPlan(
            stems=[],
            video_has_audio=video_has_audio,
            filter_complex="",
            audio_map_label="0:a?" if video_has_audio else "",
            skipped=[],
        )

    filters: list[str] = []
    labels: list[str] = []

    if video_has_audio:
        filters.append("[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[va]")
        labels.append("[va]")

    for i, stem in enumerate(stems):
        inp = i + 1  # input index
        delay = _adelay_ms(stem.start_sec)
        # Dual-channel adelay (stereo); mono is upmixed by aformat below.
        chain = (
            f"[{inp}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        )
        if stem.trim_start > 0 or stem.length_sec > 0:
            # atrim uses seconds; end is exclusive when length set
            if stem.length_sec > 0:
                end = stem.trim_start + stem.length_sec
                chain += f",atrim=start={stem.trim_start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS"
            elif stem.trim_start > 0:
                chain += f",atrim=start={stem.trim_start:.6f},asetpts=PTS-STARTPTS"
        if delay > 0:
            chain += f",adelay={delay}|{delay}"
        if abs(stem.gain - 1.0) > 1e-6:
            chain += f",volume={stem.gain:.6f}"
        label = f"[s{i}]"
        chain += label
        filters.append(chain)
        labels.append(label)

    n = len(labels)
    if n == 1:
        # Single audio stream — rename to [aout]
        only = labels[0]
        if only != "[aout]":
            filters.append(f"{only}anull[aout]")
        audio_map = "[aout]"
    else:
        mixed = "".join(labels)
        filters.append(
            f"{mixed}amix=inputs={n}:duration=longest:dropout_transition=0:normalize=0[aout]"
        )
        audio_map = "[aout]"

    return MixPlan(
        stems=list(stems),
        video_has_audio=video_has_audio,
        filter_complex=";".join(filters),
        audio_map_label=audio_map,
        skipped=[],
    )


def mix_editor_onto_video(
    *,
    primary_video: Path,
    editor_data: dict[str, Any],
    out_path: Path,
    resolve_path: PathResolver,
    video_has_audio: Optional[bool] = None,
) -> MixResult:
    """Mux Editor stems onto primary_video and write out_path.

    If there are no usable stems, copies the primary video (bytes) so callers
    still get a playable file. When the video has no audio track and stems
    exist, the mix becomes the sole audio.
    """
    if not primary_video.is_file():
        raise FileNotFoundError(f"primary video not found: {primary_video}")

    stems, skipped = collect_mix_stems(editor_data, resolve_path)
    has_audio = probe_has_audio(primary_video) if video_has_audio is None else bool(video_has_audio)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not stems:
        # Nothing to mix — pass through video unchanged.
        out_path.write_bytes(primary_video.read_bytes())
        meta = {
            "op": "editor_mix",
            "primaryVideo": str(primary_video),
            "stems": [],
            "skipped": skipped,
            "videoHasAudio": has_audio,
            "passthrough": True,
        }
        return MixResult(
            out_path=out_path,
            stems_used=[],
            skipped=skipped,
            video_has_audio=has_audio,
            filter_complex="",
            prompt_meta=meta,
        )

    plan = build_mix_plan(stems, video_has_audio=has_audio)
    args: list[str] = ["-i", str(primary_video)]
    for stem in stems:
        args.extend(["-i", str(stem.path)])
    args.extend(
        [
            "-filter_complex",
            plan.filter_complex,
            "-map",
            "0:v:0",
            "-map",
            plan.audio_map_label,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(out_path),
        ]
    )
    run_ffmpeg(args)

    meta = {
        "op": "editor_mix",
        "primaryVideo": str(primary_video),
        "stems": [
            {
                "track": s.track,
                "clip_id": s.clip_id,
                "asset_id": s.asset_id,
                "path": str(s.path),
                "start_sec": s.start_sec,
                "length_sec": s.length_sec,
                "trim_start": s.trim_start,
                "gain": s.gain,
                "label": s.label,
            }
            for s in stems
        ],
        "skipped": skipped,
        "videoHasAudio": has_audio,
        "filterComplex": plan.filter_complex,
        "passthrough": False,
    }
    return MixResult(
        out_path=out_path,
        stems_used=stems,
        skipped=skipped,
        video_has_audio=has_audio,
        filter_complex=plan.filter_complex,
        prompt_meta=meta,
    )


def resolve_editor_path_factory(db: Any, project_id: str) -> PathResolver:
    """Build a PathResolver that looks up Asset rows, then falls back to output_path."""

    def resolve(asset_id: Optional[str], output_path: Optional[str]) -> Optional[Path]:
        if asset_id:
            try:
                from .codirector.m29.audio.service import resolve_real_audio_path

                p = resolve_real_audio_path(db, asset_id)
                if p is not None and p.is_file():
                    return p
            except Exception:
                pass
            try:
                from .db import Asset

                asset = db.get(Asset, asset_id)
                if asset and getattr(asset, "path", None):
                    candidate = Path(asset.path)
                    if candidate.is_file():
                        return candidate
            except Exception:
                pass
        if output_path:
            candidate = Path(output_path)
            if candidate.is_file():
                return candidate
        return None

    return resolve


def default_primary_video(
    db: Any,
    project_id: str,
    editor_data: dict[str, Any],
    params: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """Pick a primary video for editor_mix without re-rendering scenes."""
    params = params or {}
    for key in ("primary_video_path", "video_path", "source_video_path"):
        raw = params.get(key)
        if raw and Path(str(raw)).is_file():
            return Path(str(raw))

    # Latest completed timeline stitch
    try:
        from .db import Job

        jobs = (
            db.query(Job)
            .filter(
                Job.project_id == project_id,
                Job.kind == "render_timeline",
                Job.status == "done",
            )
            .order_by(Job.updated_at.desc())
            .limit(5)
            .all()
        )
        for job in jobs:
            if job.output_path and Path(job.output_path).is_file():
                return Path(job.output_path)
    except Exception:
        pass

    # Editor video track clips (first resolvable)
    tracks = editor_data.get("tracks") or {}
    resolve = resolve_editor_path_factory(db, project_id)
    for clip in tracks.get("video") or []:
        if not isinstance(clip, dict) or clip.get("placeholder"):
            continue
        p = resolve(
            str(clip["asset_id"]) if clip.get("asset_id") else None,
            str(clip.get("output_path") or clip.get("path") or "") or None,
        )
        if p is not None:
            return p

    # Scene lipsync / output fallback
    try:
        from .db import Scene

        scenes = (
            db.query(Scene)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.index.asc())
            .all()
        )
        for scene in scenes:
            for attr in ("lipsync_output_path", "output_path"):
                p = getattr(scene, attr, None)
                if p and Path(p).is_file():
                    return Path(p)
    except Exception:
        pass
    return None


def new_mix_output_path(project_id: str, data_dir: Path) -> Path:
    out_dir = data_dir / "projects" / project_id / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"editor_mix_{uuid.uuid4().hex[:8]}.mp4"


def editor_data_from_json(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}
