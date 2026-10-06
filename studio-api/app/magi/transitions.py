"""Boundary transitions for MAGI picture clips.

Dissolve, fade, and wipe use FFmpeg xfade on the existing finishing render.
They apply only where two clips on the same track meet.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .media import probe_has_audio, run_ffmpeg
from .sequence.store import get_sequence, save_sequence

TRANSITION_KINDS = ("none", "dissolve", "fade", "wipe")
XFADE_NAME = {
    "dissolve": "fade",
    "fade": "fadeblack",
    "wipe": "wipeleft",
}
KIND_ALIASES = {
    "none": "none",
    "cut": "none",
    "dissolve": "dissolve",
    "crossfade": "dissolve",
    "cross fade": "dissolve",
    "fade": "fade",
    "wipe": "wipe",
}


def canonical_transition(value: str) -> str:
    key = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return KIND_ALIASES.get(key, "")


def _fps(sequence: dict[str, Any]) -> int:
    return max(int(sequence.get("frameRate") or 24), 1)


def transition_seconds(clip: dict[str, Any], fps: int) -> float:
    raw = clip.get("transitionDurationFrames")
    if raw is None:
        return 1.0
    return max(0.1, min(3.0, int(raw) / fps))


def transition_in_seconds(clip: dict[str, Any], fps: int) -> float:
    raw = clip.get("transitionInDurationFrames")
    if raw is None:
        raw = clip.get("transitionDurationFrames")
    if raw is None:
        return 1.0
    return max(0.1, min(3.0, int(raw) / fps))


def edge_fade_filter(duration: float, fade_in: float, fade_out: float) -> str:
    """Fade through black at an open head or tail. Empty when neither edge fades."""

    length = max(0.0, float(duration))
    filters: list[str] = []
    if fade_in >= 0.1 and length > 0:
        filters.append(f"fade=t=in:st=0:d={min(fade_in, length):.3f}")
    if fade_out >= 0.1 and length > 0:
        hold = min(fade_out, length)
        filters.append(f"fade=t=out:st={max(0.0, length - hold):.3f}:d={hold:.3f}")
    return ",".join(filters)


def apply_edge_fades(path: Path, duration: float, fade_in: float, fade_out: float) -> None:
    graph = edge_fade_filter(duration, fade_in, fade_out)
    if not graph:
        return
    dest = path.with_name(f"{path.stem}_edge{path.suffix}")
    audio = ["-c:a", "copy"] if probe_has_audio(path) else ["-an"]
    run_ffmpeg(
        [
            "-i",
            str(path),
            "-vf",
            graph,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            *audio,
            str(dest),
        ]
    )
    dest.replace(path)


def frames_for_seconds(seconds: float, fps: int) -> int:
    return max(1, int(round(max(0.1, min(3.0, float(seconds))) * fps)))


def adjacency_tolerance_frames(fps: int) -> int:
    """Match the timeline snap window (about 0.2s, at least 4 frames)."""
    return max(4, int(round(max(int(fps), 1) * 0.2)))


def max_transition_seconds(left_frames: int, right_frames: int, fps: int) -> float:
    """Longest blend both clips can hold. 0 means the cut is too short."""
    rate = max(int(fps), 1)
    raw = min(3.0, left_frames / rate - 0.08, right_frames / rate - 0.08)
    stepped = int(raw * 10 + 1e-6) / 10
    return stepped if stepped >= 0.1 else 0.0


def next_adjacent(
    clips: list[dict[str, Any]],
    clip: dict[str, Any],
    *,
    fps: int = 24,
) -> dict[str, Any] | None:
    """Next clip on the same track that meets this one.

    A gap inside the timeline snap window still counts. A real gap does not.
    """
    end = int(clip.get("startFrame") or 0) + int(clip.get("durationFrames") or 0)
    track_id = clip.get("trackId")
    tolerance = adjacency_tolerance_frames(fps)
    best: dict[str, Any] | None = None
    best_gap: int | None = None
    for other in clips:
        if other.get("id") == clip.get("id"):
            continue
        if other.get("trackId") != track_id:
            continue
        gap = int(other.get("startFrame") or 0) - end
        if gap < 0 or gap > tolerance:
            continue
        if best_gap is None or gap < best_gap:
            best = other
            best_gap = gap
    return best


def picture_clips_on_track(sequence: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = {str(track.get("id")): track for track in (sequence.get("tracks") or [])}
    selected = []
    for clip in sequence.get("clips") or []:
        kind = str((tracks.get(str(clip.get("trackId"))) or {}).get("kind") or "")
        if kind in {"video", "image"}:
            selected.append(clip)
    return selected


def apply_transition(
    project_id: str,
    *,
    kind: str,
    clip_id: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    canonical = canonical_transition(kind)
    if not canonical:
        raise ValueError("Transition must be None, Dissolve, Fade, or Wipe.")
    sequence = get_sequence(project_id)
    fps = _fps(sequence)
    clips = list(sequence.get("clips") or [])
    pictures = picture_clips_on_track(sequence)
    target = None
    wanted = str(clip_id or "").strip()
    if wanted:
        target = next((clip for clip in pictures if str(clip.get("id")) == wanted), None)
    if target is None:
        for clip in pictures:
            if next_adjacent(pictures, clip, fps=fps):
                target = clip
                break
    if target is None and pictures:
        target = pictures[0]
    if target is None:
        raise ValueError("Add a picture clip before setting a transition.")
    nxt = next_adjacent(pictures, target, fps=fps)
    if canonical != "none" and nxt is None:
        raise ValueError("A transition needs two clips that meet on the same track.")
    seconds = 1.0 if duration_seconds is None else float(duration_seconds)
    if canonical != "none" and nxt is not None:
        supported = max_transition_seconds(
            int(target.get("durationFrames") or 0),
            int(nxt.get("durationFrames") or 0),
            fps,
        )
        if supported < 0.1:
            raise ValueError("These clips are too short for a transition.")
        seconds = min(seconds, supported)
    duration_frames = frames_for_seconds(seconds, fps)
    updated = []
    for clip in clips:
        if str(clip.get("id")) != str(target.get("id")):
            updated.append(clip)
            continue
        row = dict(clip)
        if canonical == "none":
            row["transitionOutId"] = None
            row["transitionDurationFrames"] = None
        else:
            row["transitionOutId"] = canonical
            row["transitionDurationFrames"] = duration_frames
        updated.append(row)
    sequence["clips"] = updated
    save_sequence(project_id, sequence)
    return {
        "ok": True,
        "clipId": target.get("id"),
        "nextClipId": None if nxt is None else nxt.get("id"),
        "transition": canonical,
        "durationSeconds": 0 if canonical == "none" else duration_frames / fps,
    }


def preview_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, clip in enumerate(clips[:-1]):
        kind = canonical_transition(str(clip.get("transitionOutId") or ""))
        if kind and kind != "none":
            return clips[index : index + 2]
    return clips[:1]


def _padded_length(group_durations: list[float], joins: list[dict[str, Any]], index: int) -> float:
    start = float(joins[index - 1]["xfade"]) / 2 if index > 0 else 0.0
    stop = float(joins[index]["xfade"]) / 2 if index < len(joins) else 0.0
    return float(group_durations[index]) + start + stop


def xfade_chain_filter(group_durations: list[float], joins: list[dict[str, Any]]) -> str:
    """Picture xfade that keeps the sum of the clip durations.

    Each side is padded with a cloned frame for half the blend, so the overlap
    does not shorten the program. Audio is a hard concat: a picture blend does
    not crossfade dialogue, music, or effects.
    """
    filters: list[str] = []
    count = len(group_durations)
    for index in range(count):
        start = float(joins[index - 1]["xfade"]) / 2 if index > 0 else 0.0
        stop = float(joins[index]["xfade"]) / 2 if index < len(joins) else 0.0
        pads: list[str] = []
        if start > 0:
            pads.append(f"start_mode=clone:start_duration={start:.3f}")
        if stop > 0:
            pads.append(f"stop_mode=clone:stop_duration={stop:.3f}")
        label = f"[vp{index}]"
        if pads:
            filters.append(f"[{index}:v]tpad={':'.join(pads)}{label}")
        else:
            filters.append(f"[{index}:v]setpts=PTS-STARTPTS{label}")
        filters.append(
            f"[{index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[ap{index}]"
        )
    video = "[vp0]"
    timeline = _padded_length(group_durations, joins, 0)
    last = len(joins) - 1
    for index, join in enumerate(joins):
        duration = float(join["xfade"])
        offset = max(0.0, timeline - duration)
        name = XFADE_NAME[str(join["kind"])]
        video_out = "[vout]" if index == last else f"[v{index}]"
        filters.append(
            f"{video}[vp{index + 1}]xfade=transition={name}:duration={duration:.3f}:offset={offset:.3f}{video_out}"
        )
        video = video_out
        timeline = offset + _padded_length(group_durations, joins, index + 1)
    audio_inputs = "".join(f"[ap{index}]" for index in range(count))
    filters.append(f"{audio_inputs}concat=n={count}:v=0:a=1[aout]")
    return ";".join(filters)


def _concat_copy(paths: list[Path], dest: Path) -> None:
    if len(paths) == 1:
        if paths[0] != dest:
            shutil.copy2(paths[0], dest)
        return
    listing = dest.parent / f"{dest.stem}_concat.txt"
    listing.write_text("".join(f"file '{path.as_posix()}'\n" for path in paths), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)])


def join_picture_parts(parts: list[dict[str, Any]], dest: Path) -> None:
    """Join trimmed clip files. Hard cuts stay concat. Boundary transitions use xfade."""
    if not parts:
        raise RuntimeError("No playable MAGI clips were found for render.")
    groups: list[list[dict[str, Any]]] = [[parts[0]]]
    joins: list[dict[str, Any]] = []
    for item in parts[1:]:
        previous = groups[-1][-1]
        if previous.get("kind"):
            group_duration = sum(float(row["duration"]) for row in groups[-1])
            xfade = min(
                float(previous.get("xfade") or 1.0),
                group_duration - 0.08,
                float(item["duration"]) - 0.08,
            )
            if xfade < 0.1:
                groups[-1].append(item)
                continue
            previous = {**previous, "xfade": xfade}
            groups[-1][-1] = previous
            joins.append(previous)
            groups.append([item])
        else:
            groups[-1].append(item)
    work = dest.parent
    group_files: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        out = work / f"transition_group_{index:02d}.mp4"
        _concat_copy([Path(item["path"]) for item in group], out)
        group_files.append({"path": out, "duration": sum(float(item["duration"]) for item in group)})
    if len(group_files) == 1:
        shutil.copy2(group_files[0]["path"], dest)
        return
    audible: list[dict[str, Any]] = []
    for index, item in enumerate(group_files):
        path = Path(item["path"])
        if probe_has_audio(path):
            audible.append(item)
            continue
        with_audio = work / f"transition_audio_{index:02d}.mp4"
        duration = float(item["duration"])
        run_ffmpeg(
            [
                "-i",
                str(path),
                "-f",
                "lavfi",
                "-t",
                f"{duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(with_audio),
            ]
        )
        audible.append({**item, "path": with_audio})
    group_files = audible
    graph = xfade_chain_filter([float(item["duration"]) for item in group_files], joins)
    args = []
    for item in group_files:
        args.extend(["-i", str(item["path"])])
    run_ffmpeg(
        [
            *args,
            "-filter_complex",
            graph,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(dest),
        ]
    )
