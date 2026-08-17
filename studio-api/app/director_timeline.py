from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .lipsync_tracks import LipSyncTracks, parse_lipsync_tracks
from .director_timeline_w46.camera_catalog import describe_camera_clip


def _nid() -> str:
    return uuid.uuid4().hex[:10]


class RegionBox(BaseModel):
    """Normalized highlight region (0-1) for segment prompt edits."""

    x: float = 0.25
    y: float = 0.25
    w: float = 0.5
    h: float = 0.5


class TimelineClip(BaseModel):
    id: str = Field(default_factory=_nid)
    asset_id: Optional[str] = None
    start: float = 0.0
    length: float = 5.0
    trim_start: float = 0.0
    label: str = ""
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    reference_binding_id: Optional[str] = None


class ImageClip(TimelineClip):
    role: Literal["start", "middle", "end", "guide"] = "guide"
    display_tag: Optional[str] = None


class PromptSegment(BaseModel):
    id: str = Field(default_factory=_nid)
    start: float = 0.0
    length: float = 2.0
    text: str = ""
    weight: float = 1.0
    region: Optional[RegionBox] = None  # if set, affects only highlighted area
    # Prompt Timeline metadata (optional; old JSON remains valid)
    audio_intent: list[str] = Field(default_factory=list)
    script_segment_id: Optional[str] = None
    storyboard_panel_id: Optional[str] = None
    scene_state_id: Optional[str] = None
    model_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    # W46: when set, this is an Image-Attached Prompt bound to a Timeline image clip.
    bound_image_clip_id: Optional[str] = None


CameraMotionType = Literal[
    "static",
    "dolly_in",
    "dolly_out",
    "push",
    "pull",
    "pan",
    "tilt",
    "orbit",
    "crane",
    "rail",
    "handheld",
    "drone",
]

CameraRig = Literal[
    "tripod",
    "dolly",
    "crane",
    "steadicam",
    "handheld",
    "drone",
    "rail",
    "gimbal",
    "virtual",
]


class CameraClip(BaseModel):
    id: str = Field(default_factory=_nid)
    start: float = 0.0
    length: float = 2.0
    motion_type: CameraMotionType = "static"
    motion_id: Optional[str] = None
    speed: float = 1.0
    distance: float = 1.0
    ease: str = "ease_in_out"
    shake: float = 0.0
    blend: float = 0.5
    intensity: Optional[float] = None
    subject_lock: Optional[float] = None
    stabilization: Optional[str] = None
    rig: CameraRig = "tripod"
    rig_id: Optional[str] = None
    custom_motion_label: Optional[str] = None
    custom_rig_label: Optional[str] = None
    execution_strategy: Optional[str] = None
    label: str = ""
    preset_id: Optional[str] = None


class DirectorTimeline(BaseModel):
    """
    Director Prompt Timeline for one scene (shot / short sequence generation).

    Tracks:
      - media (image OR video mode)
      - text prompt segments (optional region highlight + audio intent)
      - camera motion
      - audio (music / dialogue bed)
      - sfx
      - one or more lip sync tracks (via lipsync_tracks)

    Director creates shots. Editor assembles the film.
    """

    media_mode: Literal["image", "video"] = "image"
    duration_sec: float = 5.0
    image_clips: list[ImageClip] = Field(default_factory=list)
    video_clips: list[TimelineClip] = Field(default_factory=list)
    video_reference_clips: list[TimelineClip] = Field(default_factory=list)
    image_reference_clips: list[TimelineClip] = Field(default_factory=list)
    prompt_segments: list[PromptSegment] = Field(default_factory=list)
    camera_clips: list[CameraClip] = Field(default_factory=list)
    audio_clips: list[TimelineClip] = Field(default_factory=list)
    sfx_clips: list[TimelineClip] = Field(default_factory=list)
    lipsync: LipSyncTracks = Field(default_factory=LipSyncTracks.default)
    playhead: float = 0.0
    next_image_tag_number: int = 1
    # W46 SA40 — compilation/provenance preference (never mutates already-generated assets).
    guidance_priority: Literal["visual_first", "prompt_first", "balanced", "custom"] = "visual_first"

    @classmethod
    def default(cls, duration_sec: float = 5.0, prompt: str = "") -> "DirectorTimeline":
        """True-empty tracks by default; lip sync starts with one empty track."""
        _ = prompt  # kept for API compat; does not invent Timeline items
        return cls(
            media_mode="image",
            duration_sec=duration_sec,
            image_clips=[],
            prompt_segments=[],
            camera_clips=[],
            audio_clips=[],
            sfx_clips=[],
            video_clips=[],
            video_reference_clips=[],
            image_reference_clips=[],
            lipsync=LipSyncTracks.default(),
            playhead=0.0,
            guidance_priority="visual_first",
        )


def camera_prompt_hint(clips: list[CameraClip]) -> str:
    if not clips:
        return ""
    bits = []
    for c in sorted(clips, key=lambda x: x.start):
        summary = describe_camera_clip(c)
        motion_label = summary.get("motionLabel") or c.motion_type.replace("_", " ")
        rig_label = summary.get("rigLabel") or c.rig.replace("_", " ")
        extras = []
        if c.intensity is not None:
            extras.append(f"intensity {c.intensity:.2f}")
        if c.subject_lock is not None:
            extras.append(f"subject lock {c.subject_lock:.2f}")
        if c.stabilization:
            extras.append(f"stabilization {c.stabilization}")
        bits.append(
            f"{motion_label} on {rig_label} "
            f"(speed {c.speed:.2f}, distance {c.distance:.2f}, ease {c.ease}, shake {c.shake:.2f}"
            f"{', ' + ', '.join(extras) if extras else ''})"
        )
    return "Camera: " + "; ".join(bits)


def parse_director_timeline(raw: str | None, *, fallback_duration: float = 5.0, fallback_prompt: str = "") -> DirectorTimeline:
    if not raw or not str(raw).strip():
        return DirectorTimeline.default(fallback_duration, fallback_prompt)
    try:
        data = json.loads(raw)
        # Accept nested lipsync as raw dict
        if isinstance(data.get("lipsync"), dict):
            data["lipsync"] = parse_lipsync_tracks(json.dumps(data["lipsync"])).model_dump()
        tl = DirectorTimeline.model_validate(data)
        # Do not invent empty prompt segments — true empty tracks (W46).
        _ = fallback_prompt
        return tl
    except Exception:
        return DirectorTimeline.default(fallback_duration, fallback_prompt)


def dumps_director_timeline(tl: DirectorTimeline) -> str:
    return tl.model_dump_json()


def dumps_director_timeline_preserving_embedded(
    tl: DirectorTimeline, existing_raw: str | None
) -> str:
    """Serialize ``tl`` to director_json while preserving any embedded
    ``timelineMaster`` / ``timelineWorkspace`` and other non-DirectorTimeline
    keys that lived in the existing blob.

    This is the merge path used by ``PUT /director`` so that legacy track
    updates never erase the W46 master/workspace (PUT_DIRECTOR_PRESERVES_MASTER).
    The DirectorTimeline fields are fully replaced by ``tl``; only the keys
    that are NOT part of DirectorTimeline are carried over from the existing
    blob.
    """
    base = json.loads(dumps_director_timeline(tl))
    if existing_raw and str(existing_raw).strip():
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, dict):
                director_keys = set(base.keys())
                for k, v in parsed.items():
                    if k not in director_keys:
                        base[k] = v
        except Exception:
            pass
    return json.dumps(base)


def migrate_scene_to_director(
    *,
    duration_sec: float,
    prompt: str,
    start_asset_id: str | None,
    middle_asset_id: str | None,
    end_asset_id: str | None,
    audio_asset_id: str | None,
    lipsync_tracks_json: str | None,
) -> DirectorTimeline:
    """COW migrate legacy scene slots onto a true-empty DirectorTimeline (only real content)."""
    tl = DirectorTimeline.default(duration_sec, prompt)
    images: list[ImageClip] = []
    if start_asset_id:
        images.append(ImageClip(asset_id=start_asset_id, start=0.0, length=duration_sec, role="start", label="Start"))
    if middle_asset_id:
        images.append(ImageClip(asset_id=middle_asset_id, start=0.0, length=duration_sec, role="middle", label="Middle"))
    if end_asset_id:
        images.append(ImageClip(asset_id=end_asset_id, start=0.0, length=duration_sec, role="end", label="End"))
    tl.image_clips = images
    # Preserve creator prompt as an independent timed segment only when legacy prompt exists.
    if (prompt or "").strip():
        tl.prompt_segments = [
            PromptSegment(start=0.0, length=duration_sec, text=prompt.strip())
        ]
    if audio_asset_id:
        tl.audio_clips = [
            TimelineClip(asset_id=audio_asset_id, start=0.0, length=duration_sec, label="Audio")
        ]
    tl.lipsync = parse_lipsync_tracks(lipsync_tracks_json)
    return tl


def sync_legacy_fields_from_director(tl: DirectorTimeline) -> dict[str, Any]:
    """Map director tracks back onto legacy scene columns for render pipeline."""
    start = next((c.asset_id for c in tl.image_clips if c.role == "start" and c.asset_id), None)
    middle = next((c.asset_id for c in tl.image_clips if c.role == "middle" and c.asset_id), None)
    end = next((c.asset_id for c in tl.image_clips if c.role == "end" and c.asset_id), None)
    # Prefer first video clip as continuity source when in video mode
    if tl.media_mode == "video" and tl.video_clips:
        # keep start as first frame proxy if images empty
        pass
    audio = tl.audio_clips[0].asset_id if tl.audio_clips else None
    # Combine prompt segments in time order for the scene prompt field
    segs = sorted(tl.prompt_segments, key=lambda s: s.start)
    prompt = " | ".join(s.text.strip() for s in segs if s.text.strip())
    ls = tl.lipsync
    enabled_audio = None
    for track in ls.tracks:
        if not track.enabled:
            continue
        enabled_audio = track.audio_asset_id or next(
            (clip.audio_asset_id for clip in track.clips if clip.audio_asset_id),
            None,
        )
        if enabled_audio:
            break
    return {
        "duration_sec": tl.duration_sec,
        "prompt": prompt,
        "start_asset_id": start,
        "middle_asset_id": middle,
        "end_asset_id": end,
        "audio_asset_id": audio,
        "lipsync_enabled": 1 if any(t.enabled for t in ls.tracks) else 0,
        "lipsync_audio_asset_id": enabled_audio,
        "lipsync_tracks_json": ls.model_dump_json(),
    }
