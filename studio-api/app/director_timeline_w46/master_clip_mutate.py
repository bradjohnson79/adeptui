"""Shared SceneTimelineMaster clip mutations — sole write path for batch-owned clips."""

from __future__ import annotations

from typing import Any, Iterable

from .contracts import BatchBlock, BatchClip, DurationState, SceneTimelineMaster
from .creator_batch_surface import default_execution_window_label


CLIP_ATTRS = ("visualClips", "audioClips", "sfxClips", "cameraInstructions")


def start_containing_batch(master: Any, start: float) -> Any:
    """Window whose [cursor, cursor+planned) contains `start`. Last window if past end."""
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    if not blocks:
        raise ValueError("Timeline Master has no execution windows yet.")
    cursor = 0.0
    target = blocks[0]
    for batch in blocks:
        dur = getattr(batch, "duration", None)
        planned = max(
            0.1,
            float(
                getattr(dur, "plannedDuration", None)
                or getattr(dur, "timelineVisibleDuration", None)
                or 0.0
            ),
        )
        end = cursor + planned
        if start + 1e-6 >= cursor and start < end - 1e-9:
            return batch
        cursor = end
        target = batch
    return target


def ensure_windows(master: SceneTimelineMaster, *, scene_id: str, duration_sec: float) -> SceneTimelineMaster:
    """Mint one Window 1 from scene duration when Master has no execution windows."""
    if getattr(master, "batchBlocks", None):
        return master
    planned = max(0.1, float(duration_sec or 5.0))
    master.batchBlocks = [
        BatchBlock(
            sceneId=str(scene_id),
            order=0,
            label=default_execution_window_label(0),
            duration=DurationState(plannedDuration=planned, timelineVisibleDuration=planned),
        )
    ]
    return master


def flatten_attr(master: Any, attr: str) -> list[Any]:
    out: list[Any] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        out.extend(list(getattr(batch, attr, None) or []))
    return out


def iter_clips(master: Any, attrs: Iterable[str] | None = None):
    names = tuple(attrs) if attrs else CLIP_ATTRS
    for batch in getattr(master, "batchBlocks", None) or []:
        for attr in names:
            for clip in list(getattr(batch, attr, None) or []):
                yield batch, attr, clip


def clip_matches(clip: Any, clip_id: str) -> bool:
    wanted = str(clip_id or "").strip()
    if not wanted:
        return False
    return str(getattr(clip, "id", "") or "") == wanted or str(
        getattr(clip, "legacyClipId", "") or ""
    ) == wanted


def find_clip(master: Any, clip_id: str, attrs: Iterable[str] | None = None):
    for batch, attr, clip in iter_clips(master, attrs):
        if clip_matches(clip, clip_id):
            return batch, attr, clip
    return None, None, None


def append_clip(master: Any, clip: BatchClip, start: float, attr: str) -> Any:
    target = start_containing_batch(master, float(start or 0.0))
    setattr(target, attr, list(getattr(target, attr, None) or []) + [clip])
    return target


def snapshot(master: SceneTimelineMaster) -> dict[str, Any]:
    return master.model_dump(mode="json")


def restore(data: dict[str, Any]) -> SceneTimelineMaster:
    return SceneTimelineMaster.model_validate(data)
