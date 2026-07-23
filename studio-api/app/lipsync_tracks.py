from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class MouthRoi(BaseModel):
    """Normalized rectangle (0-1) over the preview frame."""

    x: float = 0.4
    y: float = 0.55
    w: float = 0.18
    h: float = 0.12


class LipSyncTrack(BaseModel):
    slot: int = Field(ge=1, le=2)
    label: str = "Character 1"
    enabled: bool = False
    audio_asset_id: Optional[str] = None
    roi: MouthRoi = Field(default_factory=MouthRoi)
    # Optional baked sticky path: list of {frame, x, y, w, h, visible}
    track_path: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class LipSyncTracks(BaseModel):
    tracks: list[LipSyncTrack] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "LipSyncTracks":
        return cls(
            tracks=[
                LipSyncTrack(slot=1, label="Character 1", enabled=False),
                LipSyncTrack(slot=2, label="Character 2", enabled=False),
            ]
        )


def parse_lipsync_tracks(raw: str | None) -> LipSyncTracks:
    if not raw or not raw.strip():
        return LipSyncTracks.default()
    try:
        data = json.loads(raw)
        tracks = LipSyncTracks.model_validate(data)
        # Ensure exactly 2 slots
        by_slot = {t.slot: t for t in tracks.tracks if t.slot in (1, 2)}
        out = []
        for slot in (1, 2):
            if slot in by_slot:
                out.append(by_slot[slot])
            else:
                out.append(LipSyncTrack(slot=slot, label=f"Character {slot}"))
        return LipSyncTracks(tracks=out)
    except Exception:
        return LipSyncTracks.default()


def dumps_lipsync_tracks(tracks: LipSyncTracks) -> str:
    return tracks.model_dump_json()
