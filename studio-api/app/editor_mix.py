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


def probe_duration(video: Path) -> float:
    """Return video duration in seconds via ffprobe; 0.0 on failure."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return float((proc.stdout or "").strip())
    except Exception:
        pass
    return 0.0


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


def mix_stems_onto_video(
    *,
    primary_video: Path,
    stems: list[MixStem],
    out_path: Path,
    video_has_audio: Optional[bool] = None,
) -> MixResult:
    """Mux pre-collected audio stems onto primary_video and write out_path.

    Reuses the same ffmpeg filter graph construction as Editor mix. If there
    are no usable stems, copies the primary video (bytes) unchanged so callers
    still get a playable file.
    """
    if not primary_video.is_file():
        raise FileNotFoundError(f"primary video not found: {primary_video}")

    has_audio = probe_has_audio(primary_video) if video_has_audio is None else bool(video_has_audio)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not stems:
        # Nothing to mix — pass through video unchanged.
        out_path.write_bytes(primary_video.read_bytes())
        meta = {
            "op": "stem_mix",
            "primaryVideo": str(primary_video),
            "stems": [],
            "videoHasAudio": has_audio,
            "filterComplex": "",
            "passthrough": True,
        }
        return MixResult(
            out_path=out_path,
            stems_used=[],
            skipped=[],
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
        "op": "stem_mix",
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
        "videoHasAudio": has_audio,
        "filterComplex": plan.filter_complex,
        "passthrough": False,
    }
    return MixResult(
        out_path=out_path,
        stems_used=stems,
        skipped=[],
        video_has_audio=has_audio,
        filter_complex=plan.filter_complex,
        prompt_meta=meta,
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
    stems, skipped = collect_mix_stems(editor_data, resolve_path)
    result = mix_stems_onto_video(
        primary_video=primary_video,
        stems=stems,
        out_path=out_path,
        video_has_audio=video_has_audio,
    )
    # Merge Editor-specific skip reasons into the shared result.
    result.skipped = skipped
    result.prompt_meta["skipped"] = skipped
    result.prompt_meta["op"] = "editor_mix"
    return result


def _normalized_clip_fields(clip: Any) -> dict[str, Any]:
    """Normalize BatchClip or legacy TimelineClip into a plain dict."""
    asset_id = getattr(clip, "assetId", None) or getattr(clip, "asset_id", None)
    trim_start = getattr(clip, "trimStart", None)
    if trim_start is None:
        trim_start = getattr(clip, "trim_start", 0.0)
    raw_volume = getattr(clip, "volume", None)
    volume = 1.0 if raw_volume is None else float(raw_volume)
    return {
        "id": getattr(clip, "id", ""),
        "asset_id": asset_id,
        "start": float(getattr(clip, "start", 0.0) or 0.0),
        "length": float(getattr(clip, "length", 0.0) or 0.0),
        "trim_start": float(trim_start or 0.0),
        "label": getattr(clip, "label", "") or "",
        "volume": volume,
        "muted": bool(getattr(clip, "muted", False)),
    }


def _iter_timeline_audio_clips(
    scene_director_json: str | None,
    scene_id: str,
    fallback_duration: float,
    fallback_prompt: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Yield (track, normalized_clip) for a scene's audio/sfx clips.

    Reads the legacy DirectorTimeline tracks first, then falls back to / appends
    BatchBlock audioClips/sfxClips when they are not represented in the legacy
    tracks. This follows the real W46 shape where either or both may hold
    clip-level audio state.
    """
    from .director_timeline import parse_director_timeline
    from .director_timeline_w46.migration import load_or_migrate_scene_master

    out: list[tuple[str, dict[str, Any]]] = []
    seen_ids: set[str] = set()

    tl = parse_director_timeline(
        scene_director_json,
        fallback_duration=fallback_duration,
        fallback_prompt=fallback_prompt,
    )
    for clip in tl.audio_clips:
        seen_ids.add(str(clip.id))
        out.append(("music", _normalized_clip_fields(clip)))
    for clip in tl.sfx_clips:
        seen_ids.add(str(clip.id))
        out.append(("sfx", _normalized_clip_fields(clip)))

    master, _, _ = load_or_migrate_scene_master(
        scene_director_json,
        scene_id=scene_id,
        fallback_duration=fallback_duration,
        fallback_prompt=fallback_prompt,
    )
    for batch in getattr(master, "batchBlocks", []) or []:
        for clip in getattr(batch, "audioClips", []) or []:
            legacy_id = str(getattr(clip, "legacyClipId", "") or "")
            cid = str(getattr(clip, "id", ""))
            # Migrated batch clips mirror legacy timeline clips; avoid duplicates.
            if legacy_id and legacy_id in seen_ids:
                continue
            if cid not in seen_ids:
                seen_ids.add(cid)
                out.append(("music", _normalized_clip_fields(clip)))
        for clip in getattr(batch, "sfxClips", []) or []:
            legacy_id = str(getattr(clip, "legacyClipId", "") or "")
            cid = str(getattr(clip, "id", ""))
            if legacy_id and legacy_id in seen_ids:
                continue
            if cid not in seen_ids:
                seen_ids.add(cid)
                out.append(("sfx", _normalized_clip_fields(clip)))

    return out


def collect_timeline_mix_stems(
    db: Any,
    project: Any,
    scenes: list[Any],
    scene_outputs: list[Path],
    resolve_path: PathResolver,
) -> tuple[list[MixStem], list[dict[str, Any]]]:
    """Collect music/SFX stems from scene DirectorTimelines for timeline export.

    Each scene output is probed for duration; clip.start is offset by the
    cumulative duration of all previous scene outputs. Muted or zero-volume
    clips are skipped (documented as gain 0). Missing/unresolvable assets are
    recorded in skipped rather than failing the render.
    """
    stems: list[MixStem] = []
    skipped: list[dict[str, Any]] = []
    cursor_sec = 0.0

    for scene, output in zip(scenes, scene_outputs):
        scene_duration = probe_duration(output) if output and output.is_file() else 0.0
        fallback_duration = float(getattr(scene, "duration_sec", None) or 5.0)
        fallback_prompt = getattr(scene, "prompt", "") or ""

        for track, clip in _iter_timeline_audio_clips(
            getattr(scene, "director_json", None),
            getattr(scene, "id", ""),
            fallback_duration,
            fallback_prompt,
        ):
            clip_id = str(clip.get("id") or "")
            asset_id = clip.get("asset_id")
            label = str(clip.get("label") or track)
            raw_volume = clip.get("volume")
            volume = 1.0 if raw_volume is None else float(raw_volume)
            muted = bool(clip.get("muted", False))

            # 0-skip rule: muted or zero volume clips are omitted entirely.
            if muted or volume <= 0:
                skipped.append(
                    {
                        "track": track,
                        "clip_id": clip_id,
                        "reason": "muted_or_zero_gain",
                        "label": label,
                        "volume": volume,
                        "muted": muted,
                    }
                )
                continue

            path = resolve_path(str(asset_id) if asset_id else None, None)
            if path is None or not path.is_file():
                skipped.append(
                    {
                        "track": track,
                        "clip_id": clip_id,
                        "reason": "missing_file",
                        "asset_id": asset_id,
                        "label": label,
                    }
                )
                continue

            start = float(clip.get("start") or 0.0)
            length = float(clip.get("length") or 0.0)
            trim_start = float(clip.get("trim_start") or 0.0)
            gain = max(0.0, min(1.0, volume))

            stems.append(
                MixStem(
                    track=track,
                    clip_id=clip_id,
                    path=path,
                    start_sec=max(0.0, cursor_sec + start),
                    length_sec=max(0.0, length),
                    trim_start=max(0.0, trim_start),
                    gain=gain,
                    asset_id=str(asset_id) if asset_id else None,
                    label=label,
                )
            )

        cursor_sec += max(0.0, scene_duration)

    return stems, skipped


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
