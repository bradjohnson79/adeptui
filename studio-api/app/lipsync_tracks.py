from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


def _nid() -> str:
    return uuid.uuid4().hex[:10]


class MouthRoi(BaseModel):
    """Normalized rectangle (0-1) over the preview frame."""

    x: float = 0.4
    y: float = 0.55
    w: float = 0.18
    h: float = 0.12


class LipSyncClip(BaseModel):
    id: str = Field(default_factory=_nid)
    start: float = 0.0
    length: float = 2.0
    label: str = "Lip Sync Clip"
    status: str = "draft"
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    audio_asset_id: Optional[str] = None
    follow_policy: str = "follow_audio"


class LipSyncTrack(BaseModel):
    id: str = Field(default_factory=_nid)
    slot: int = Field(ge=1)
    label: str = "Lip Sync 1"
    enabled: bool = False
    audio_asset_id: Optional[str] = None
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    clips: list[LipSyncClip] = Field(default_factory=list)
    roi: MouthRoi = Field(default_factory=MouthRoi)
    # Optional baked sticky path: list of {frame, x, y, w, h, visible}
    track_path: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class LipSyncTracks(BaseModel):
    tracks: list[LipSyncTrack] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "LipSyncTracks":
        return cls(tracks=[LipSyncTrack(slot=1, label="Lip Sync 1", enabled=False)])


def _default_track(slot: int) -> LipSyncTrack:
    return LipSyncTrack(
        slot=slot,
        label=f"Lip Sync {slot}",
        enabled=False,
    )


def _normalize_clip(raw: LipSyncClip, *, fallback_audio_asset_id: Optional[str] = None) -> LipSyncClip:
    clip = raw.model_copy(deep=True)
    if not (clip.label or "").strip():
        clip.label = "Lip Sync Clip"
    if not (clip.follow_policy or "").strip():
        clip.follow_policy = "follow_audio"
    if not (clip.status or "").strip():
        clip.status = "draft"
    if clip.audio_asset_id is None and fallback_audio_asset_id:
        clip.audio_asset_id = fallback_audio_asset_id
    clip.start = max(0.0, float(clip.start or 0.0))
    clip.length = max(0.1, float(clip.length or 0.1))
    return clip


def _normalize_track(raw: LipSyncTrack, *, index: int) -> LipSyncTrack:
    track = raw.model_copy(deep=True)
    track.slot = index + 1
    if not (track.label or "").strip():
        track.label = f"Lip Sync {track.slot}"
    normalized_clips = [
        _normalize_clip(clip, fallback_audio_asset_id=track.audio_asset_id)
        for clip in sorted(track.clips or [], key=lambda item: (item.start, item.id))
    ]
    track.clips = normalized_clips
    if track.audio_asset_id is None:
        track.audio_asset_id = next((clip.audio_asset_id for clip in normalized_clips if clip.audio_asset_id), None)
    if track.character_id is None:
        track.character_id = next((clip.character_id for clip in normalized_clips if clip.character_id), None)
    if track.character_name is None:
        track.character_name = next((clip.character_name for clip in normalized_clips if clip.character_name), None)
    return track


def parse_lipsync_tracks(raw: str | None) -> LipSyncTracks:
    if not raw or not raw.strip():
        return LipSyncTracks.default()
    try:
        data = json.loads(raw)
        parsed = LipSyncTracks.model_validate(data)
        ordered = sorted(parsed.tracks or [], key=lambda track: (track.slot, track.id))
        if not ordered:
            return LipSyncTracks.default()
        normalized = [_normalize_track(track, index=index) for index, track in enumerate(ordered)]
        return LipSyncTracks(tracks=normalized)
    except Exception:
        return LipSyncTracks.default()


def dumps_lipsync_tracks(tracks: LipSyncTracks) -> str:
    return tracks.model_dump_json()
