"""MAGI sequence document validation.

The authoritative schema is the M4.12 frozen frontend contract
(``studio-web/src/magiSequence/types.ts``). This module mirrors that shape with
Pydantic models so the backend can reject schema-invalid PUT payloads instead of
``setdefault``-filling garbage, and it validates clip -> asset ownership
(cross-project asset references are rejected).
"""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TrackKind = Literal[
    "video", "image", "audio", "text", "fx", "mask", "adjustment"
]

_TRACK_KINDS: frozenset[str] = frozenset(
    {"video", "image", "audio", "text", "fx", "mask", "adjustment"}
)

_ORDER_RE = re.compile(r"^(seq_|trk_|clip_|mk_)")

_DEFAULT_TRACK_KINDS = (
    "video", "video", "video",
    "image", "image",
    "audio", "audio", "audio",
    "text",
    "fx",
    "mask",
    "adjustment",
)


class MagiMarkerModel(BaseModel):
    id: str
    frame: int = Field(ge=0)
    label: str = ""
    color: Optional[str] = None


class MagiTrackModel(BaseModel):
    id: str
    kind: TrackKind
    label: str
    order: int = Field(ge=0)
    locked: Optional[bool] = None
    muted: Optional[bool] = None
    solo: Optional[bool] = None

    @field_validator("kind")
    @classmethod
    def _kind_in_enum(cls, value: str) -> str:
        if value not in _TRACK_KINDS:
            raise ValueError(f"invalid track kind '{value}'")
        return value


class MagiClipModel(BaseModel):
    id: str
    trackId: str
    assetId: str
    name: Optional[str] = None
    startFrame: int = Field(ge=0)
    durationFrames: int = Field(ge=1)
    inPoint: int = Field(ge=0)
    outPoint: int = Field(ge=0)
    speed: Optional[float] = None
    reverse: Optional[bool] = None
    freeze: Optional[bool] = None
    transitionInId: Optional[str] = None
    transitionOutId: Optional[str] = None
    # Lineage (m2): optional provenance of how this clip entered MAGI.
    batchBlockId: Optional[str] = None
    generationId: Optional[str] = None
    takeId: Optional[str] = None
    sourceClipId: Optional[str] = None
    sceneId: Optional[str] = None

    @model_validator(mode="after")
    def _outpoint_not_less_than_inpoint(self) -> "MagiClipModel":
        if self.outPoint < self.inPoint:
            raise ValueError(
                f"clip '{self.id}' outPoint {self.outPoint} < inPoint {self.inPoint}"
            )
        return self


class MagiSequenceModel(BaseModel):
    id: str
    projectId: str
    frameRate: int = Field(ge=1, le=120)
    durationFrames: int = Field(ge=1)
    playheadFrame: int = Field(ge=0)
    tracks: list[MagiTrackModel] = Field(default_factory=list)
    clips: list[MagiClipModel] = Field(default_factory=list)
    markers: list[MagiMarkerModel] = Field(default_factory=list)
    snapEnabled: bool = True
    revision: int = Field(ge=1)
    updatedAt: str = ""
    recipeId: Optional[str] = None
    # m5: MAGI-side export lineage ledger, keyed by W46 batchBlockId. Kept
    # separate from clip documents so the frozen W46 BatchClip contract stays
    # untouched; provenance is preserved here instead.
    exportLedger: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_references(self) -> "MagiSequenceModel":
        ids = [t.id for t in self.tracks]
        if len(ids) != len(set(ids)):
            raise ValueError("track ids are not unique")
        clip_ids = [c.id for c in self.clips]
        if len(clip_ids) != len(set(clip_ids)):
            raise ValueError("clip ids are not unique")
        track_set = set(ids)
        for clip in self.clips:
            if clip.trackId not in track_set:
                raise ValueError(
                    f"clip '{clip.id}' references unknown trackId '{clip.trackId}'"
                )
        return self


def parse_sequence(raw: Any) -> MagiSequenceModel:
    """Validate and normalize a sequence payload.

    Raises ``ValueError`` with a structured message when the payload does not
    conform to the frozen contract. Missing optional fields are filled with
    model defaults (backward-compatible with older empty sequence files).
    """
    if not isinstance(raw, dict):
        raise ValueError("sequence payload must be an object")
    return MagiSequenceModel.model_validate(raw)


def ensure_asset_lineage_fields(clip: dict[str, Any]) -> dict[str, Any]:
    """Carry optional lineage fields from a client clip dict through saving."""
    out = dict(clip)
    for key in ("batchBlockId", "generationId", "takeId", "sourceClipId", "sceneId"):
        if clip.get(key) is not None:
            out[key] = clip[key]
    return out


def validate_asset_ownership(
    db,
    project_id: str,
    sequence: MagiSequenceModel,
) -> dict[str, list[str]]:
    """Return structured ownership violations for a sequence's clips.

    Returns a dict keyed by structured error code (m1 A4):

    - ``ASSET_NOT_FOUND``: ``clip.assetId`` does not exist in the DB at all.
    - ``ASSET_PROJECT_MISMATCH``: the asset exists but belongs to another project.
    - ``INVALID_CLIP_ASSET``: a clip carries an empty/missing asset id.

    Values are the offending asset ids (or clip ids for ``INVALID_CLIP_ASSET``).
    Clips that reference no asset are only reported as ``INVALID_CLIP_ASSET``.
    """
    result: dict[str, list[str]] = {
        "ASSET_NOT_FOUND": [],
        "ASSET_PROJECT_MISMATCH": [],
        "INVALID_CLIP_ASSET": [],
    }
    if not sequence.clips:
        return result

    asset_ids: set[str] = set()
    for clip in sequence.clips:
        if not clip.assetId:
            result["INVALID_CLIP_ASSET"].append(clip.id)
            continue
        asset_ids.add(clip.assetId)
    if not asset_ids:
        return result

    from ...db import Asset

    rows = (
        db.query(Asset.id, Asset.project_id)
        .filter(Asset.id.in_(asset_ids))
        .all()
    )
    owned = {row[0]: row[1] for row in rows}
    for aid in sorted(asset_ids):
        if aid not in owned:
            result["ASSET_NOT_FOUND"].append(aid)
        elif owned[aid] != project_id:
            result["ASSET_PROJECT_MISMATCH"].append(aid)
    return result
