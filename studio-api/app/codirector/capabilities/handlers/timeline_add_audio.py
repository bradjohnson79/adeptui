"""Capability handler: timeline.add_audio — place approved audio on the scene Timeline.

Reconnects the existing AudioService.place_cue / director sfx_clips path.
Footstep requests create independently timed clips per character rather than
one looping bed or an advice-only chat reply.
"""

from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ....timeline_media_labels import resolve_media_clip_labels

from .analyze_video import _resolve_playable_video_asset_id
from ...video_intelligence import media_persist
from ...video_intelligence.audio_timing import (
    DEFAULT_WALK_CADENCE_SEC,
    disclose_timing,
    plan_contact_hits,
)
from ...video_intelligence.media_packet import (
    MediaIntelligencePacket,
    MotionEvent,
)

DEFAULT_COMPANION_OFFSET_SEC = 0.22
DEFAULT_FOOTSTEP_VOLUME = 0.32
_ASSET_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_FOOTSTEP_RE = re.compile(r"\b(?:footsteps?|footfalls?|boot\s+step)\b", re.I)
_AUDIO_KINDS = frozenset({"audio", "sfx", "music", "ambience"})


@dataclass(frozen=True)
class FootstepHit:
    character_name: str
    start_sec: float
    length_sec: float
    volume: float
    label: str



def _resolved_place_label(*, kind: str, label: str | None, asset_tag: str | None = None, asset_filename: str | None = None) -> dict[str, str | None]:
    """Canonical title/description/label for Co-Director place_cue (shared with Timeline UI)."""
    resolved = resolve_media_clip_labels(
        {
            "kind": kind,
            "clip": {"label": label},
            "asset": {"tag": asset_tag, "filename": asset_filename},
        }
    )
    return {
        "label": resolved.get("title") or resolved.get("label") or label,
        "title": resolved.get("title"),
        "description": resolved.get("description"),
    }


def looks_like_footstep_placement(text: str) -> bool:
    return bool(_FOOTSTEP_RE.search(text or ""))


def plan_walk_footsteps(
    character_names: list[str],
    *,
    duration_sec: float,
    cadence_sec: float = DEFAULT_WALK_CADENCE_SEC,
    companion_offset_sec: float = DEFAULT_COMPANION_OFFSET_SEC,
    clip_length_sec: float = 0.45,
    volume: float = DEFAULT_FOOTSTEP_VOLUME,
) -> list[FootstepHit]:
    """Inferred walk cadence. Not frame-perfect unless contact frames are supplied."""

    names = [name.strip() for name in character_names if (name or "").strip()]
    if not names:
        names = ["Footsteps"]
    window = max(float(duration_sec or 0), 0.0)
    cadence = max(float(cadence_sec or DEFAULT_WALK_CADENCE_SEC), 0.2)
    length = min(max(float(clip_length_sec or 0.45), 0.12), cadence * 0.9)
    offset = max(float(companion_offset_sec or 0), 0.0)
    if len(names) > 2:
        offset = cadence / float(len(names))
    hits: list[FootstepHit] = []
    for index, name in enumerate(names):
        start = 0.0 if index == 0 else min(offset * index, cadence * 0.85)
        while start + 0.04 < window:
            hits.append(
                FootstepHit(
                    character_name=name,
                    start_sec=round(start, 3),
                    length_sec=round(length, 3),
                    volume=volume,
                    label=f"{name} footsteps" if name != "Footsteps" else "Footsteps",
                )
            )
            start += cadence
    return hits


def _wav_duration_sec(path: str | None) -> float | None:
    if not path:
        return None
    try:
        with wave.open(path, "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate > 0 and frames > 0:
                return float(frames) / float(rate)
    except Exception:
        return None
    return None


def _resolve_named_characters(db: Session, project_id: str, prompt: str) -> list[str]:
    from ...entity_resolver import find_character_names, resolve_character
    from ....character_identity.models import CharacterProfileRow

    text = prompt or ""
    mentions: list[tuple[int, str]] = []
    seen: set[str] = set()

    def _add(index: int, name: str) -> None:
        clean = name.strip()
        key = clean.lower()
        if not clean or key in seen:
            return
        seen.add(key)
        mentions.append((index, clean))

    for match in re.finditer(r"@([A-Za-z][A-Za-z'\-0-9]*(?:\s+[A-Z][A-Za-z'\-0-9]+)*)", text):
        tagged = match.group(1).strip()
        resolved = resolve_character(db, project_id, tagged)
        _add(match.start(), str((resolved or {}).get("name") or tagged))

    for tagged in find_character_names(text):
        resolved = resolve_character(db, project_id, tagged)
        name = str((resolved or {}).get("name") or tagged)
        found = re.search(rf"@{re.escape(tagged)}\b", text)
        _add(found.start() if found else len(text), name)

    rows = (
        db.query(CharacterProfileRow)
        .filter(CharacterProfileRow.project_id == project_id)
        .all()
    )
    for row in rows:
        name = str(getattr(row, "name", "") or "").strip()
        if not name:
            continue
        found = re.search(rf"\b{re.escape(name)}\b", text, re.I)
        if found:
            _add(found.start(), name)
    mentions.sort(key=lambda item: item[0])
    return [name for _index, name in mentions]


def _candidate_asset_id(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    return str(candidate.get("asset_id") or candidate.get("assetId") or "").strip()


def _is_project_audio_asset(asset: Any, project_id: str) -> bool:
    return (
        asset is not None
        and str(getattr(asset, "project_id", "") or "") == project_id
        and str(getattr(asset, "kind", "") or "").lower() in _AUDIO_KINDS
    )


def _first_audio_asset_id(db: Session, project_id: str, ids: list[str] | None) -> str:
    from ....db import Asset

    for raw in ids or []:
        uid = str(raw or "").strip()
        if not uid:
            continue
        asset = db.get(Asset, uid)
        if _is_project_audio_asset(asset, project_id):
            return uid
    return ""


def _library_approved_sfx_asset_id(db: Session, project_id: str, prompt: str) -> str:
    from ....db import Asset

    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .all()
    )
    best: tuple[int, str] | None = None
    for asset in rows:
        if not _is_project_audio_asset(asset, project_id):
            continue
        blob = " ".join(
            [
                str(getattr(asset, "filename", "") or ""),
                str(getattr(asset, "tag", "") or ""),
                str(getattr(asset, "prompt_meta_json", "") or ""),
            ]
        )
        approval = str(getattr(asset, "production_approval", "") or "").lower()
        score = 0
        if approval == "approved":
            score += 4
        if _FOOTSTEP_RE.search(blob):
            score += 3
        elif looks_like_footstep_placement(prompt) and approval == "approved":
            score += 1
        if score and (best is None or score > best[0]):
            best = (score, str(asset.id))
    return best[1] if best else ""


def _resolve_sfx_asset_id(db: Session, project_id: str, prompt: str) -> str:
    from ....audio_studio import store
    from ....db import Asset

    for uid in _ASSET_UUID_RE.findall(prompt or ""):
        asset = db.get(Asset, uid)
        if _is_project_audio_asset(asset, project_id):
            return uid

    draft = store.get_draft(project_id)
    approved_id = str(draft.get("approvedCandidateId") or "").strip()
    batch_id = str(draft.get("approvedBatchId") or "").strip()
    if approved_id and batch_id:
        batch = store.get_batch(project_id, batch_id)
        method = str((batch or {}).get("method") or "")
        if method != "ambience":
            for candidate in (batch or {}).get("candidates") or []:
                if str(candidate.get("id") or "") == approved_id:
                    asset_id = _candidate_asset_id(candidate)
                    asset = db.get(Asset, asset_id) if asset_id else None
                    if _is_project_audio_asset(asset, project_id):
                        return asset_id

    best: tuple[int, str] | None = None
    for batch in store.list_batches(project_id):
        method = str(batch.get("method") or "")
        if method not in {"sfx", "foley"}:
            continue
        brief = str(
            (batch.get("brief_snapshot") or {}).get("prompt")
            or batch.get("prompt")
            or ""
        )
        footstepish = bool(_FOOTSTEP_RE.search(brief) or re.search(r"\b(?:grate|boot|metal)\b", brief, re.I))
        for candidate in batch.get("candidates") or []:
            if str(candidate.get("status") or "") != "approved":
                continue
            asset_id = _candidate_asset_id(candidate)
            asset = db.get(Asset, asset_id) if asset_id else None
            if not _is_project_audio_asset(asset, project_id):
                continue
            score = 3 if footstepish else 1
            if best is None or score > best[0]:
                best = (score, asset_id)
    return best[1] if best else ""


_MUSIC_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert)\b.+\b(?:music|score|cue|track|soundtrack)\b"
    r"|\b(?:music|score|cue|track|soundtrack)\b.+\b(?:timeline|scene)\b",
    re.I,
)
_AMBIENCE_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert)\b.+\b(?:ambience|room tone|atmosphere|scene bed)\b"
    r"|\b(?:ambience|room tone|atmosphere|scene bed)\b.+\b(?:timeline|scene)\b",
    re.I,
)
_SFX_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert)\b.+\b(?:sfx|sound effects?|foley)\b.+\b(?:timeline|scene)\b"
    r"|\b(?:sfx|sound effects?|foley)\b.+\b(?:on|to|onto)\s+(?:the\s+)?timeline\b",
    re.I,
)
_DUCK_UNDER_DIALOGUE_RE = re.compile(
    r"\b(?:under\s+(?:the\s+)?dialogue|duck|lower\s+under\s+(?:the\s+)?speech|dip\s+under\s+(?:the\s+)?dialogue)\b",
    re.I,
)


def looks_like_music_placement(text: str) -> bool:
    return bool(_MUSIC_PLACE_RE.search(text or ""))


def looks_like_ambience_placement(text: str) -> bool:
    return bool(_AMBIENCE_PLACE_RE.search(text or ""))


def _looks_like_walk_motion(motion_events: list[Any]) -> bool:
    """True when at least one motion event looks like a character walking."""
    for ev in motion_events or []:
        if isinstance(ev, dict):
            subject = ev.get("subject") or ev.get("motionSubject") or "unknown"
            motion_type = str(ev.get("motionType") or ev.get("type") or "").lower()
        else:
            subject = getattr(ev, "subject", "unknown")
            motion_type = str(getattr(ev, "motionType", "") or "").lower()
        if subject == "character" and ("walk" in motion_type or "stride" in motion_type or "step" in motion_type):
            return True
    return False


def _plan_motion_derived_hits(
    character_names: list[str],
    motion_events: list[Any],
    *,
    duration_sec: float,
    clip_length_sec: float = 0.45,
    volume: float = DEFAULT_FOOTSTEP_VOLUME,
) -> list[FootstepHit]:
    """Derive footstep hits from visible character walking motion events."""
    names = [name.strip() for name in character_names if (name or "").strip()] or ["Footsteps"]
    length = min(max(float(clip_length_sec or 0.45), 0.12), 0.8)
    hits: list[FootstepHit] = []
    for index, ev in enumerate(motion_events or []):
        if isinstance(ev, dict):
            subject = ev.get("subject") or ev.get("motionSubject") or "unknown"
            motion_type = str(ev.get("motionType") or ev.get("type") or "").lower()
            start = float(ev.get("startTime") or ev.get("start") or 0.0)
            end = float(ev.get("endTime") or ev.get("end") or start + 0.5)
        else:
            subject = getattr(ev, "subject", "unknown")
            motion_type = str(getattr(ev, "motionType", "") or "").lower()
            start = float(getattr(ev, "startTime", 0.0) or 0.0)
            end = float(getattr(ev, "endTime", None) or start + 0.5)
        if subject != "character" or ("walk" not in motion_type and "stride" not in motion_type and "step" not in motion_type):
            continue
        name = names[index % len(names)]
        t = start
        while t < end and t < duration_sec:
            hits.append(
                FootstepHit(
                    character_name=name,
                    start_sec=round(t, 3),
                    length_sec=round(length, 3),
                    volume=volume,
                    label=f"{name} footsteps" if name != "Footsteps" else "Footsteps",
                )
            )
            t += 0.55
    return hits


def _load_media_intelligence_packet(
    db: Session,
    project_id: str,
    scene_id: str,
) -> MediaIntelligencePacket | None:
    """Load the latest Media Intelligence packet for the scene's playable video."""
    video_asset_id = _resolve_playable_video_asset_id(db, project_id, scene_id)
    if not video_asset_id:
        return None
    return media_persist.load_packet(db, project_id, video_asset_id)


def _library_approved_music_asset_id(db: Session, project_id: str, prompt: str) -> str:
    """Best approved music/score asset in the project's Library."""
    from ....db import Asset

    rows = db.query(Asset).filter(Asset.project_id == project_id).all()
    best: tuple[int, str] | None = None
    for asset in rows:
        if not _is_project_audio_asset(asset, project_id):
            continue
        blob = " ".join(
            [
                str(getattr(asset, "filename", "") or ""),
                str(getattr(asset, "tag", "") or ""),
                str(getattr(asset, "prompt_meta_json", "") or ""),
            ]
        )
        approval = str(getattr(asset, "production_approval", "") or "").lower()
        score = 0
        if approval == "approved":
            score += 4
        if re.search(r"\b(?:music|score|cue|track|soundtrack|bgm)\b", blob, re.I):
            score += 3
        elif looks_like_music_placement(prompt) and approval == "approved":
            score += 1
        if score and (best is None or score > best[0]):
            best = (score, str(asset.id))
    return best[1] if best else ""


def _library_approved_ambience_asset_id(db: Session, project_id: str, prompt: str) -> str:
    """Best approved ambience/room-tone asset in the project's Library."""
    from ....db import Asset

    rows = db.query(Asset).filter(Asset.project_id == project_id).all()
    best: tuple[int, str] | None = None
    for asset in rows:
        if not _is_project_audio_asset(asset, project_id):
            continue
        blob = " ".join(
            [
                str(getattr(asset, "filename", "") or ""),
                str(getattr(asset, "tag", "") or ""),
                str(getattr(asset, "prompt_meta_json", "") or ""),
            ]
        )
        approval = str(getattr(asset, "production_approval", "") or "").lower()
        score = 0
        if approval == "approved":
            score += 4
        if re.search(r"\b(?:ambience|room tone|atmosphere|scene bed|background)\b", blob, re.I):
            score += 3
        elif looks_like_ambience_placement(prompt) and approval == "approved":
            score += 1
        if score and (best is None or score > best[0]):
            best = (score, str(asset.id))
    return best[1] if best else ""


def _resolve_sfx_audio_asset_id(
    db: Session,
    project_id: str,
    prompt: str,
    attachment_asset_ids: list[str] | None,
) -> str:
    """Resolve an SFX/foley/footstep audio asset from attachments, Audio Studio, or Library."""
    asset_id = _first_audio_asset_id(db, project_id, attachment_asset_ids)
    if not asset_id:
        asset_id = _resolve_sfx_asset_id(db, project_id, prompt)
    if not asset_id:
        asset_id = _library_approved_sfx_asset_id(db, project_id, prompt)
    return asset_id


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    scene_id: str = "",
    character_names: list[str] | None = None,
    attachment_asset_ids: list[str] | None = None,
    **_: Any,
) -> dict[str, Any]:
    from ....codirector.m29.audio.service import AudioService
    from ....db import Asset, Scene

    if not scene_id:
        return {
            "error": "Open the scene on Timeline first so audio can be placed on it.",
            "child_jobs": [],
            "surface_type": "timeline_audio",
        }

    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        return {
            "error": "That scene is not in this project.",
            "child_jobs": [],
            "surface_type": "timeline_audio",
        }

    names = [str(n).strip() for n in (character_names or []) if str(n).strip()]

    # ── Footsteps / SFX: contact-first, motion-derived, or cadence fallback ─────
    if looks_like_footstep_placement(prompt) or _SFX_PLACE_RE.search(prompt or ""):
        asset_id = _resolve_sfx_audio_asset_id(db, project_id, prompt, attachment_asset_ids)
        asset = db.get(Asset, asset_id) if asset_id else None
        if not _is_project_audio_asset(asset, project_id):
            return {
                "error": "No approved footstep or SFX sound was found. Approve one in Audio Studio first.",
                "child_jobs": [],
                "surface_type": "timeline_audio",
            }

        names = _resolve_named_characters(db, project_id, prompt) or names
        duration = float(scene.duration_sec or 8.0)
        sample_len = _wav_duration_sec(getattr(asset, "path", None)) or 1.0
        clip_len = min(sample_len, DEFAULT_WALK_CADENCE_SEC * 0.85)

        # Contact-first timing: load the latest Media Intelligence packet for the clip.
        packet = _load_media_intelligence_packet(db, project_id, scene_id)
        timing_source: str = "cadence_inference"
        hits: list[FootstepHit] = []
        if packet and packet.is_ready() and packet.contactEvents:
            hits = [
                FootstepHit(
                    character_name=th.character_name or "Footsteps",
                    start_sec=th.start_sec,
                    length_sec=th.length_sec,
                    volume=th.volume,
                    label=th.label,
                )
                for th in plan_contact_hits(packet.contactEvents, clip_length_sec=clip_len)
            ]
            timing_source = "visible_contact"
        elif packet and packet.is_ready() and _looks_like_walk_motion(packet.motionEvents):
            hits = _plan_motion_derived_hits(
                names,
                packet.motionEvents,
                duration_sec=duration,
                clip_length_sec=clip_len,
            )
            timing_source = "motion_derived"
        else:
            hits = plan_walk_footsteps(
                names,
                duration_sec=duration,
                clip_length_sec=clip_len,
            )

        if not hits:
            return {
                "error": "The scene is too short to place walking footsteps.",
                "child_jobs": [],
                "surface_type": "timeline_audio",
            }

        child_jobs: list[dict[str, Any]] = []
        placed = 0
        for index, hit in enumerate(hits):
            _lbl = _resolved_place_label(kind="sfx", label=hit.label)
            result = AudioService.place_cue(
                db,
                project_id=project_id,
                kind="sfx",
                asset_id=asset_id,
                start_sec=hit.start_sec,
                duration_sec=hit.length_sec,
                scene_id=scene_id,
                volume=hit.volume,
                label=_lbl["label"],
                title=_lbl["title"],
                description=_lbl["description"],
            )
            ok = bool(result.get("timelinePlaced"))
            placed += int(ok)
            child_jobs.append(
                {
                    "job_id": str(result.get("cueId") or uuid4()),
                    "label": hit.label,
                    "status": "completed" if ok else "failed",
                    "child_index": index,
                    "asset_id": asset_id,
                    "error": None if ok else "Timeline clip was not written.",
                    "metadata": {
                        "startSec": hit.start_sec,
                        "lengthSec": hit.length_sec,
                        "character": hit.character_name,
                        "timingSource": timing_source,
                    },
                }
            )
        lanes = ", ".join(names) if names else "the scene"
        return {
            "status": "completed",
            "result_asset_ids": [asset_id],
            "job_ids": [execution_id],
            "child_jobs": child_jobs,
            "surface_type": "timeline_audio",
            "creatorAck": (
                f"Placed {placed} independently timed footstep/SFX hits for {lanes} "
                f"on the SFX track. {disclose_timing(timing_source)}"
            ),
        }

    # ── Music: search Library first, duck under dialogue when asked ────────────
    if looks_like_music_placement(prompt):
        asset_id = _first_audio_asset_id(db, project_id, attachment_asset_ids)
        if not asset_id:
            asset_id = _library_approved_music_asset_id(db, project_id, prompt)
        asset = db.get(Asset, asset_id) if asset_id else None
        if not _is_project_audio_asset(asset, project_id):
            return {
                "error": "No approved music cue was found. Approve a music cue in Audio Studio first.",
                "child_jobs": [],
                "surface_type": "timeline_audio",
            }

        packet = _load_media_intelligence_packet(db, project_id, scene_id)
        start_sec = 0.0
        duration_sec = float(scene.duration_sec or 8.0)
        if packet and packet.is_ready() and packet.musicOpportunities:
            first = packet.musicOpportunities[0]
            start_sec = float(first.startTime or 0.0)
            if first.endTime is not None:
                duration_sec = max(0.0, float(first.endTime) - start_sec)
        ducking = bool(_DUCK_UNDER_DIALOGUE_RE.search(prompt or ""))
        _mlabel = str(getattr(asset, "tag", "") or "Music")
        _lbl = _resolved_place_label(
            kind="music",
            label=_mlabel,
            asset_tag=getattr(asset, "tag", None),
            asset_filename=getattr(asset, "filename", None),
        )
        result = AudioService.place_cue(
            db,
            project_id=project_id,
            kind="music",
            asset_id=asset_id,
            start_sec=start_sec,
            duration_sec=duration_sec,
            scene_id=scene_id,
            volume=1.0,
            ducking=ducking,
            fade_in_sec=0.5,
            fade_out_sec=0.5,
            label=_lbl["label"],
            title=_lbl["title"],
            description=_lbl["description"],
        )
        ok = bool(result.get("timelinePlaced"))
        return {
            "status": "completed" if ok else "failed",
            "error": None if ok else "Timeline clip was not written.",
            "result_asset_ids": [asset_id],
            "job_ids": [execution_id],
            "child_jobs": [
                {
                    "job_id": str(result.get("cueId") or uuid4()),
                    "label": "Music cue",
                    "status": "completed" if ok else "failed",
                    "child_index": 0,
                    "asset_id": asset_id,
                    "metadata": {
                        "ducking": ducking,
                        "startSec": start_sec,
                        "durationSec": duration_sec,
                    },
                }
            ],
            "surface_type": "timeline_audio",
            "creatorAck": (
                f"Placed the approved music cue on the Timeline{' with ducking under dialogue' if ducking else ''}."
                if ok
                else ""
            ),
        }

    # ── Ambience: search Library first, full scene bed by default ──────────────
    if looks_like_ambience_placement(prompt):
        asset_id = _first_audio_asset_id(db, project_id, attachment_asset_ids)
        if not asset_id:
            asset_id = _library_approved_ambience_asset_id(db, project_id, prompt)
        asset = db.get(Asset, asset_id) if asset_id else None
        if not _is_project_audio_asset(asset, project_id):
            return {
                "error": "No approved ambience bed was found. Approve an ambience cue in Audio Studio first.",
                "child_jobs": [],
                "surface_type": "timeline_audio",
            }

        duration_sec = float(scene.duration_sec or 8.0)
        _alabel = str(getattr(asset, "tag", "") or "Ambience")
        _lbl = _resolved_place_label(
            kind="ambience",
            label=_alabel,
            asset_tag=getattr(asset, "tag", None),
            asset_filename=getattr(asset, "filename", None),
        )
        result = AudioService.place_cue(
            db,
            project_id=project_id,
            kind="ambience",
            asset_id=asset_id,
            start_sec=0.0,
            duration_sec=duration_sec,
            scene_id=scene_id,
            volume=1.0,
            loop=True,
            label=_lbl["label"],
            title=_lbl["title"],
            description=_lbl["description"],
        )
        ok = bool(result.get("timelinePlaced"))
        return {
            "status": "completed" if ok else "failed",
            "error": None if ok else "Timeline clip was not written.",
            "result_asset_ids": [asset_id],
            "job_ids": [execution_id],
            "child_jobs": [
                {
                    "job_id": str(result.get("cueId") or uuid4()),
                    "label": "Ambience bed",
                    "status": "completed" if ok else "failed",
                    "child_index": 0,
                    "asset_id": asset_id,
                }
            ],
            "surface_type": "timeline_audio",
            "creatorAck": "Placed the approved ambience bed across the scene." if ok else "",
        }

    # ── Generic audio placement (backward-compatible single cue) ───────────────
    asset_id = _resolve_sfx_audio_asset_id(db, project_id, prompt, attachment_asset_ids)
    asset = db.get(Asset, asset_id) if asset_id else None
    if not _is_project_audio_asset(asset, project_id):
        return {
            "error": "No approved audio was found. Approve an audio asset in Audio Studio first.",
            "child_jobs": [],
            "surface_type": "timeline_audio",
        }

    _glabel = str(getattr(asset, "tag", "") or "Audio")
    _lbl = _resolved_place_label(
        kind="sfx",
        label=_glabel,
        asset_tag=getattr(asset, "tag", None),
        asset_filename=getattr(asset, "filename", None),
    )
    result = AudioService.place_cue(
        db,
        project_id=project_id,
        kind="sfx",
        asset_id=asset_id,
        start_sec=0.0,
        duration_sec=_wav_duration_sec(getattr(asset, "path", None)) or 2.0,
        scene_id=scene_id,
        volume=1.0,
        label=_lbl["label"],
        title=_lbl["title"],
        description=_lbl["description"],
    )
    ok = bool(result.get("timelinePlaced"))
    return {
        "status": "completed" if ok else "failed",
        "error": None if ok else "Timeline clip was not written.",
        "result_asset_ids": [asset_id],
        "job_ids": [execution_id],
        "child_jobs": [
            {
                "job_id": str(result.get("cueId") or uuid4()),
                "label": "Timeline audio",
                "status": "completed" if ok else "failed",
                "child_index": 0,
                "asset_id": asset_id,
            }
        ],
        "surface_type": "timeline_audio",
        "creatorAck": "Placed the approved audio on the Timeline." if ok else "",
    }
