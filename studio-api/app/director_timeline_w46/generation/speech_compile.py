"""Compile Lip Sync + Prompt dialogue into timed speech windows.

Hierarchy (locked):
  Explicit Lip Sync audio → Prompt dialogue via assigned character voice → no speech

A Prompt clip is shared visual/action context. Lip Sync clips switch the speaker
by time. Do not split one Prompt into two unrelated scenes.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, PromptSegment, _intervals_overlap
from ...lipsync_tracks import LipSyncClip
from ..contracts import BatchBlock
from .reference_compile import resolve_binding_id

_SAYS_RE = re.compile(
    r"@([A-Za-z0-9_]+)\s+says\s+[\"“](.+?)[\"”]",
    re.IGNORECASE | re.DOTALL,
)

LIPSYNC_SPEAKER_REQUIRED = "Assign a character to this Lip Sync clip."


def _clip_end(start: float, length: float) -> float:
    return float(start) + max(0.0, float(length))


def iter_lipsync_clips(timeline: DirectorTimeline | None) -> list[tuple[LipSyncClip, str | None]]:
    if timeline is None:
        return []
    out: list[tuple[LipSyncClip, str | None]] = []
    for track in timeline.lipsync.tracks or []:
        for clip in track.clips or []:
            out.append((clip, track.id))
    return out


def lipsync_speaker_errors(timeline: DirectorTimeline | None) -> list[dict[str, Any]]:
    """Block generation when Lip Sync audio is present without a character speaker."""
    errors: list[dict[str, Any]] = []
    if timeline is None:
        return errors
    for clip, _track_id in iter_lipsync_clips(timeline):
        audio = (clip.audio_asset_id or "").strip()
        speaker = (clip.speaker_binding_id or "").strip()
        if audio and not speaker:
            errors.append(
                {
                    "code": "LIPSYNC_SPEAKER_REQUIRED",
                    "message": LIPSYNC_SPEAKER_REQUIRED,
                    "clipId": clip.id,
                    "severity": "error",
                }
            )
    return errors


def _overlapping_prompts(
    timeline: DirectorTimeline,
    start: float,
    end: float,
) -> list[PromptSegment]:
    length = max(0.0, end - start)
    return [
        seg
        for seg in timeline.prompt_segments or []
        if _intervals_overlap(seg.start, seg.length, start, length)
    ]


def _active_voice_id(db: Session | None, identity_id: str | None) -> str | None:
    if not db or not identity_id:
        return None
    try:
        from app.character_identity.models import CharacterProfileRow

        row = db.get(CharacterProfileRow, identity_id)
        vid = getattr(row, "active_voice_profile_id", None) if row is not None else None
        return str(vid) if vid else None
    except Exception:
        return None


def extract_dialogue_cues(
    prompt: PromptSegment,
    db: Session | None,
    project_id: str | None,
) -> list[dict[str, Any]]:
    """Extract `@Token says "..."` only when Token is a bound entity on this Prompt."""
    text = prompt.text or ""
    bound = list(prompt.reference_binding_ids or [])
    if not text.strip() or not bound:
        return []
    alias_to_binding: dict[str, str] = {}
    for binding_id in bound:
        resolved = resolve_binding_id(db, project_id, binding_id)
        alias = (resolved.get("alias") or "").strip()
        kind = (resolved.get("mediaKind") or "").lower()
        ref_type = (resolved.get("referenceType") or "").lower()
        if kind and kind != "entity" and ref_type not in ("character", "prop"):
            continue
        if alias:
            alias_to_binding[alias.lower()] = binding_id
    cues: list[dict[str, Any]] = []
    for match in _SAYS_RE.finditer(text):
        token = (match.group(1) or "").strip()
        spoken = (match.group(2) or "").strip()
        binding_id = alias_to_binding.get(token.lower())
        if not binding_id or not spoken:
            continue
        resolved = resolve_binding_id(db, project_id, binding_id)
        cues.append(
            {
                "speakerBindingId": binding_id,
                "text": spoken,
                "characterId": resolved.get("identityId"),
                "assignedVoiceId": _active_voice_id(db, resolved.get("identityId")),
            }
        )
    return cues


def _lipsync_covering(timeline: DirectorTimeline, start: float, end: float) -> list[LipSyncClip]:
    mid = (start + end) / 2.0
    covering: list[LipSyncClip] = []
    for clip, _ in iter_lipsync_clips(timeline):
        clip_end = _clip_end(clip.start, clip.length)
        if clip.start <= mid < clip_end or _intervals_overlap(clip.start, clip.length, start, end - start):
            covering.append(clip)
    # Prefer clips that actually overlap the interval interior.
    return [
        clip
        for clip in covering
        if _intervals_overlap(clip.start, clip.length, start, max(0.0, end - start))
    ]


def compile_speech_windows(
    timeline: DirectorTimeline | None,
    *,
    window_start: float = 0.0,
    window_end: float | None = None,
    db: Session | None = None,
    project_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (windows, errors). Prompt text/IDs stay whole across Lip Sync splits."""
    if timeline is None:
        return [], []
    errors = lipsync_speaker_errors(timeline)
    duration = float(window_end if window_end is not None else timeline.duration_sec or 5.0)
    start = float(window_start or 0.0)
    cuts = {start, duration}
    for clip, _ in iter_lipsync_clips(timeline):
        clip_start = max(start, float(clip.start or 0.0))
        clip_end = min(duration, _clip_end(clip.start, clip.length))
        if clip_end > start and clip_start < duration:
            cuts.add(clip_start)
            cuts.add(clip_end)
    points = sorted(c for c in cuts if start - 1e-9 <= c <= duration + 1e-9)
    windows: list[dict[str, Any]] = []
    for i in range(len(points) - 1):
        t0, t1 = points[i], points[i + 1]
        if t1 - t0 <= 1e-6:
            continue
        prompts = _overlapping_prompts(timeline, t0, t1)
        prompt_text = "\n".join(p.text.strip() for p in prompts if (p.text or "").strip())
        binding_ids: list[str] = []
        for prompt in prompts:
            for bid in prompt.reference_binding_ids or []:
                if bid and bid not in binding_ids:
                    binding_ids.append(bid)
        lips = [
            clip
            for clip in _lipsync_covering(timeline, t0, t1)
            if (clip.audio_asset_id or "").strip()
        ]
        speakers: list[dict[str, Any]] = []
        kind = "none"
        if lips:
            kind = "lipsync_audio"
            for clip in lips:
                resolved = resolve_binding_id(db, project_id, clip.speaker_binding_id)
                speakers.append(
                    {
                        "speakerBindingId": clip.speaker_binding_id,
                        "audioAssetId": clip.audio_asset_id,
                        "characterId": resolved.get("identityId") or clip.character_id,
                        "characterName": resolved.get("alias") or clip.character_name,
                        "assignedVoiceId": _active_voice_id(db, resolved.get("identityId") or clip.character_id),
                        "clipId": clip.id,
                    }
                )
        else:
            cues: list[dict[str, Any]] = []
            for prompt in prompts:
                cues.extend(extract_dialogue_cues(prompt, db, project_id))
            if cues:
                kind = "prompt_dialogue"
                speakers = cues
        windows.append(
            {
                "start": t0,
                "end": t1,
                "promptText": prompt_text,
                "referenceBindingIds": binding_ids,
                "speechKind": kind,
                "speakers": speakers,
            }
        )
    return windows, errors


def apply_compiled_speech(
    batch: BatchBlock,
    director_timeline: DirectorTimeline | None,
    db: Session | None = None,
    project_id: str | None = None,
    *,
    window_start: float = 0.0,
    window_end: float | None = None,
) -> list[dict[str, Any]]:
    end = window_end
    if end is None:
        end = float(batch.duration.plannedDuration or 5.0) + float(window_start or 0.0)
    windows, errors = compile_speech_windows(
        director_timeline,
        window_start=window_start,
        window_end=end,
        db=db,
        project_id=project_id,
    )
    batch.speechWindows = windows
    return errors
