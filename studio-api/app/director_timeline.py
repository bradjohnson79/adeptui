from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .lipsync_tracks import LipSyncTracks, parse_lipsync_tracks


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


class ImageClip(TimelineClip):
    role: Literal["start", "middle", "end", "guide"] = "guide"


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
    speed: float = 1.0
    distance: float = 1.0
    ease: str = "ease_in_out"
    shake: float = 0.0
    blend: float = 0.5
    rig: CameraRig = "tripod"
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
      - lip sync 1 / lip sync 2 (via lipsync_tracks)

    Director creates shots. Editor assembles the film.
    """

    media_mode: Literal["image", "video"] = "image"
    duration_sec: float = 5.0
    image_clips: list[ImageClip] = Field(default_factory=list)
    video_clips: list[TimelineClip] = Field(default_factory=list)
    prompt_segments: list[PromptSegment] = Field(default_factory=list)
    camera_clips: list[CameraClip] = Field(default_factory=list)
    audio_clips: list[TimelineClip] = Field(default_factory=list)
    sfx_clips: list[TimelineClip] = Field(default_factory=list)
    lipsync: LipSyncTracks = Field(default_factory=LipSyncTracks.default)
    playhead: float = 0.0

    @classmethod
    def default(cls, duration_sec: float = 5.0, prompt: str = "") -> "DirectorTimeline":
        segs = []
        if prompt.strip():
            segs.append(PromptSegment(start=0.0, length=duration_sec, text=prompt))
        return cls(
            media_mode="image",
            duration_sec=duration_sec,
            image_clips=[],
            prompt_segments=segs or [PromptSegment(start=0.0, length=duration_sec, text="")],
            camera_clips=[
                CameraClip(start=0.0, length=duration_sec, motion_type="static", rig="tripod", label="Static")
            ],
            lipsync=LipSyncTracks.default(),
        )


def camera_prompt_hint(clips: list[CameraClip]) -> str:
    if not clips:
        return ""
    bits = []
    for c in sorted(clips, key=lambda x: x.start):
        bits.append(
            f"{c.motion_type.replace('_', ' ')} on {c.rig} "
            f"(speed {c.speed:.2f}, distance {c.distance:.2f}, ease {c.ease}, shake {c.shake:.2f})"
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
        if not tl.prompt_segments:
            tl.prompt_segments = [PromptSegment(start=0.0, length=tl.duration_sec, text=fallback_prompt)]
        return tl
    except Exception:
        return DirectorTimeline.default(fallback_duration, fallback_prompt)


def dumps_director_timeline(tl: DirectorTimeline) -> str:
    return tl.model_dump_json()


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
    tl = DirectorTimeline.default(duration_sec, prompt)
    for clip in tl.image_clips:
        if clip.role == "start":
            clip.asset_id = start_asset_id
        elif clip.role == "middle":
            clip.asset_id = middle_asset_id
        elif clip.role == "end":
            clip.asset_id = end_asset_id
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
    enabled_audio = next((t.audio_asset_id for t in ls.tracks if t.enabled and t.audio_asset_id), None)
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
