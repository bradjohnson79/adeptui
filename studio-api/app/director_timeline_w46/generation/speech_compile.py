"""Compile Lip Sync + Prompt dialogue into timed speech windows.

Hierarchy (locked):
  Explicit Lip Sync audio â†’ Prompt dialogue via assigned character voice â†’ no speech

A Prompt clip is shared visual/action context. Lip Sync clips switch the speaker
by time. Do not split one Prompt into two unrelated scenes.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, PromptSegment, _intervals_overlap
from ...lipsync_tracks import LipSyncClip, LipSyncTracks
from ..contracts import BatchBlock
from .reference_compile import resolve_binding_id

_SAYS_RE = re.compile(
    r"@([A-Za-z0-9_]+)\s+says\s+[\"\u201c](.+?)[\"\u201d]",
    re.IGNORECASE | re.DOTALL,
)

_QUOTE_RE = re.compile(r"[\"\u201c](.+?)[\"\u201d]", re.DOTALL)

# Screenplay character cue: ALL-CAPS speaker line, then spoken lines (no quotes required).
# e.g.  KORRI\nHello, welcome to Schnick Coffee.
_SCREENPLAY_SPEAKER_RE = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9 .'\-]{0,40}?)(?:\s*\([^\)]*\))?\s*$"
)
_SCENE_HEADING_RE = re.compile(r"^(INT\.|EXT\.|EST\.|I/E\.|FADE |CUT TO)", re.IGNORECASE)


_SPEECH_VERB_RE = re.compile(
    r"\b(says|saying|said|tells|telling|told|asks|asking|asked|"
    r"shouts|shouting|snaps|snapping|whispers|whispering|"
    r"hisses|hissing|yells|yelling|replies|replying|replied|"
    r"answers|answering|speaks|speaking)\b",
    re.IGNORECASE,
)

# Mentioned objects (toward Korri / to Korri) are not the speaking subject.
_OBJECT_PREP_RE = re.compile(
    r"\b(?:toward|towards|to|at|with|about|like|for|from|on|of|behind|beside)\s+$",
    re.IGNORECASE,
)

LIPSYNC_SPEAKER_REQUIRED = "Assign a character to this Lip Sync clip."


def _clip_end(start: float, length: float) -> float:
    return float(start) + max(0.0, float(length))


def _as_lipsync(source: Any) -> Any:
    if source is None:
        return None
    lipsync = getattr(source, "lipsync", None)
    if lipsync is None and getattr(source, "tracks", None) is not None:
        return source
    return lipsync


def iter_lipsync_clips(timeline: Any | None) -> list[tuple[LipSyncClip, str | None]]:
    lipsync = _as_lipsync(timeline)
    if lipsync is None:
        return []
    out: list[tuple[LipSyncClip, str | None]] = []
    for track in lipsync.tracks or []:
        for clip in track.clips or []:
            out.append((clip, track.id))
    return out


def _speaker_identity(clip: LipSyncClip, track_id: str | None, timeline: Any | None) -> str:
    """Canonical speaker: Prompt Name binding, else clip/track character identity."""
    speaker = (clip.speaker_binding_id or "").strip()
    if speaker:
        return speaker
    character = (clip.character_id or "").strip()
    if character:
        return character
    lipsync = _as_lipsync(timeline)
    if lipsync is None or not track_id:
        return ""
    for track in lipsync.tracks or []:
        if track.id == track_id:
            return (track.character_id or "").strip()
    return ""


def lipsync_speaker_errors(timeline: Any | None) -> list[dict[str, Any]]:
    """Block generation when Lip Sync audio is present without a character speaker.

    Character identity on the clip or parent track satisfies the gate. Do not
    require a separate speaker_binding_id when the creator already assigned
    Korri / Anadriya (or any character) on the Lip Sync track.
    """
    errors: list[dict[str, Any]] = []
    if timeline is None:
        return errors
    for clip, track_id in iter_lipsync_clips(timeline):
        audio = (clip.audio_asset_id or "").strip()
        if audio and not _speaker_identity(clip, track_id, timeline):
            errors.append(
                {
                    "code": "LIPSYNC_SPEAKER_REQUIRED",
                    "message": LIPSYNC_SPEAKER_REQUIRED,
                    "clipId": clip.id,
                    "severity": "error",
                }
            )
    return errors


def _overlapping_master_prompts(
    master: Any,
    start: float,
    end: float,
) -> list[Any]:
    """Overlap helper against Master batch.promptSegments only."""
    if master is None:
        return []
    length = max(0.0, end - start)
    out: list[Any] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            if _intervals_overlap(
                float(getattr(seg, "start", 0.0) or 0.0),
                float(getattr(seg, "length", 0.0) or 0.0),
                start,
                length,
            ):
                out.append(seg)
    return out


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



def prompt_text_implies_speech(text: str) -> bool:
    """True when Timed Prompt text looks like dialogue / screenplay speech.

    Owner law: missing cue metadata must not authorize silent success.
    Shot headings like [WIDE SHOT] are visual direction, not speech cues.
    """
    blob = (text or "").strip()
    if not blob:
        return False
    if '"' in blob or "\u201c" in blob or "\u201d" in blob:
        return True
    if re.search(
        r"\b(says|said|asks|asked|whispers|shouts|yells|tells|replies)\b",
        blob,
        re.I,
    ):
        return True
    lines = blob.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for idx, line in enumerate(lines[:-1]):
        s = line.strip()
        if not s or len(s) > 48:
            continue
        if not s.isupper():
            continue
        if s.startswith(("INT.", "EXT.", "EST.", "I/E.", "[", "(")):
            continue
        if re.search(r"\b(SHOT|LENS|CLOSE\s*UP|DOLLY|PAN|TILT|ORBIT)\b", s):
            continue
        nxt = lines[idx + 1].strip()
        if nxt and not nxt.isupper() and not nxt.startswith("("):
            return True
    return False


def extract_dialogue_cues(
    prompt: PromptSegment,
    db: Session | None,
    project_id: str | None,
) -> list[dict[str, Any]]:
    """Extract speaker cues from Prompt text when Token is a bound entity.

    Accepts:
      1) Canonical ``@Token says "..."``
      2) Owner prose ``Name says [adverbs]: "..."`` / ``Name ... says "..."``
    Token/Name must resolve via reference_binding_ids or reference_name_bindings.
    """
    text_val = prompt.text or ""
    bound = list(
        getattr(prompt, "reference_binding_ids", None)
        or getattr(prompt, "referenceBindingIds", None)
        or []
    )
    name_bindings = list(
        getattr(prompt, "reference_name_bindings", None)
        or getattr(prompt, "referenceNameBindings", None)
        or []
    )
    return extract_dialogue_cues_from_text(
        text_val,
        db=db,
        project_id=project_id,
        reference_binding_ids=bound,
        reference_name_bindings=name_bindings,
    )


def extract_dialogue_cues_from_text(
    text: str,
    db: Session | None = None,
    project_id: str | None = None,
    *,
    reference_binding_ids: list[str] | None = None,
    reference_name_bindings: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Shared cue extractor for PromptSegment and Timeline retake compile.

    Speaker binds to exact quoted text. The speaking *subject* wins; a name
    that is only a prepositional object (toward Korri / to Korri) must not
    steal the line. Bad ASR is never consulted — Prompt text is authority.

    Also accepts screenplay formatting::

        KORRI
        Hello, welcome to Schnick Coffee.
    """
    text = text or ""
    bound = list(reference_binding_ids or [])
    name_bindings = list(reference_name_bindings or [])
    if not text.strip():
        return []
    # Bindings preferred; screenplay pass can still run when aliases exist.
    alias_to_binding: dict[str, str] = {}
    for binding_id in bound:
        resolved = resolve_binding_id(db, project_id, binding_id) if db is not None else {}
        if not isinstance(resolved, dict):
            resolved = {}
        alias = (resolved.get("alias") or "").strip()
        kind = (resolved.get("mediaKind") or "").lower()
        ref_type = (resolved.get("referenceType") or "").lower()
        if kind and kind != "entity" and ref_type not in ("character", "prop"):
            pass
        elif alias:
            alias_to_binding[alias.lower()] = binding_id
        if binding_id:
            alias_to_binding.setdefault(str(binding_id).lower(), binding_id)
    for b in name_bindings:
        if isinstance(b, dict):
            binding_id = str(b.get("binding_id") or b.get("bindingId") or "").strip()
            prompt_name = str(b.get("prompt_name") or b.get("promptName") or "").strip()
            tag = str(b.get("tag") or "").strip()
        else:
            binding_id = str(getattr(b, "binding_id", None) or getattr(b, "bindingId", None) or "").strip()
            prompt_name = str(getattr(b, "prompt_name", None) or getattr(b, "promptName", None) or "").strip()
            tag = str(getattr(b, "tag", None) or "").strip()
        if not binding_id:
            continue
        if prompt_name:
            alias_to_binding[prompt_name.lower()] = binding_id
        if tag:
            alias_to_binding[tag.lstrip("@#/%").lower()] = binding_id
            alias_to_binding[tag.lower()] = binding_id

    if not alias_to_binding:
        return []

    cues: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _append(token: str, spoken: str) -> None:
        binding_id = alias_to_binding.get(token.lower())
        if not binding_id or not spoken:
            return
        key = (binding_id, spoken)
        if key in seen:
            return
        seen.add(key)
        resolved = resolve_binding_id(db, project_id, binding_id) if db is not None else {}
        if not isinstance(resolved, dict):
            resolved = {}
        display = token.strip() or resolved.get("alias") or token
        cues.append(
            {
                "speakerBindingId": binding_id,
                "text": spoken,
                "exactText": spoken,
                "characterId": resolved.get("identityId"),
                "assignedVoiceId": _active_voice_id(db, resolved.get("identityId")),
                "speakerName": display,
                "speakerId": resolved.get("identityId") or binding_id,
            }
        )

    for match in _SAYS_RE.finditer(text):
        _append((match.group(1) or "").strip(), (match.group(2) or "").strip())

    display_aliases = [a for a in alias_to_binding if _is_display_alias(a)]
    for match in _QUOTE_RE.finditer(text):
        spoken = (match.group(1) or "").strip()
        if not spoken:
            continue
        token, display = _subject_alias_for_quote(text[: match.start()], display_aliases)
        if token:
            _append(display or token, spoken)

    # Screenplay: ALL-CAPS cue line then spoken line(s) until next cue / blank / heading.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        cue = _SCREENPLAY_SPEAKER_RE.match(raw.strip())
        if not cue or _SCENE_HEADING_RE.match(raw.strip()):
            i += 1
            continue
        name = (cue.group("name") or "").strip()
        # Must match a bound display alias (Korri / KORRI).
        token = ""
        for alias in display_aliases:
            if alias.lower() == name.lower() or alias.lower() == name.replace(" ", "").lower():
                token = alias
                break
        if not token:
            # Also try first token of multi-word caps against aliases
            first = name.split()[0] if name else ""
            for alias in display_aliases:
                if alias.lower() == first.lower():
                    token = alias
                    break
        if not token:
            i += 1
            continue
        spoken_parts: list[str] = []
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            stripped = nxt.strip()
            if not stripped:
                if spoken_parts:
                    break
                j += 1
                continue
            if _SCENE_HEADING_RE.match(stripped):
                break
            if _SCREENPLAY_SPEAKER_RE.match(stripped) and not stripped.startswith("("):
                # Next character cue
                break
            if stripped.startswith("(") and stripped.endswith(")"):
                # Parenthetical direction — skip
                j += 1
                continue
            # Strip wrapping quotes if present
            quoted = False
            if (stripped.startswith('"') and stripped.endswith('"')) or (
                stripped.startswith("\u201c") and stripped.endswith("\u201d")
            ):
                stripped = stripped[1:-1].strip()
                quoted = True
            # ACTION_LINE_BREAK: once dialogue started, do not swallow narrative action
            # into the spoken cue (no cross-block / action leak).
            if spoken_parts and not quoted:
                if re.match(
                    r"^(He|She|They|It|We|Someone|The|A|An)\b",
                    stripped,
                    re.I,
                ):
                    break
            spoken_parts.append(stripped)
            j += 1
        spoken = " ".join(spoken_parts).strip()
        if spoken:
            _append(token, spoken)
        i = max(j, i + 1)

    return cues



def _is_display_alias(alias: str) -> bool:
    """True for character names; false for binding UUIDs / raw ids."""
    a = (alias or "").strip()
    if not a:
        return False
    compact = a.replace("-", "")
    if len(compact) >= 8 and all(c in "0123456789abcdef" for c in compact.lower()):
        return False
    if a.lower().startswith("bind-") or a.lower().startswith("sb_"):
        return False
    return any(c.isalpha() for c in a)


def _subject_alias_for_quote(prefix: str, aliases: list[str]) -> tuple[str, str]:
    """Nearest non-object name before the last speech verb. Empty if none.

    Scene 12B: 'Anadriya looks toward Korri ... and says' -> Anadriya, not Korri.
    """
    if not prefix or not aliases:
        return "", ""
    verbs = list(_SPEECH_VERB_RE.finditer(prefix))
    if not verbs:
        return "", ""
    verb = verbs[-1]
    line_start = prefix.rfind("\n", 0, verb.start())
    search = prefix[line_start + 1 if line_start >= 0 else 0 : verb.start()]
    subjects: list[tuple[int, str, str]] = []
    for alias in aliases:
        for m in re.finditer(rf"(?<![\w']){re.escape(alias)}(?![\w'])", search, re.IGNORECASE):
            before = search[: m.start()]
            if _OBJECT_PREP_RE.search(before):
                continue
            subjects.append((m.start(), alias, m.group(0)))
    if not subjects:
        return "", ""
    subjects.sort(key=lambda h: h[0])
    _pos, alias, display = subjects[-1]
    return alias, display



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
    master: Any = None,
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
        prompts = _overlapping_master_prompts(master, t0, t1)
        prompt_text = "\n".join(
            str(getattr(p, "text", "") or "").strip() for p in prompts if str(getattr(p, "text", "") or "").strip()
        )
        binding_ids: list[str] = []
        for prompt in prompts:
            ids = getattr(prompt, "referenceBindingIds", None) or getattr(prompt, "reference_binding_ids", None) or []
            for bid in ids:
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
                speaker = _speaker_identity(clip, None, timeline) or (clip.speaker_binding_id or clip.character_id)
                resolved = resolve_binding_id(db, project_id, speaker)
                character_id = resolved.get("identityId") or clip.character_id or speaker
                speakers.append(
                    {
                        "speakerBindingId": clip.speaker_binding_id or speaker,
                        "audioAssetId": clip.audio_asset_id,
                        "characterId": character_id,
                        "characterName": resolved.get("alias") or clip.character_name,
                        "assignedVoiceId": _active_voice_id(db, character_id),
                        "clipId": clip.id,
                    }
                )
        else:
            cues: list[dict[str, Any]] = []
            # One scene-level Timed Prompt: spoken lines belong to the later
            # render window (Batch 2 extension), not the first-half setup.
            if not _defer_scene_level_prompt_speech(prompts, timeline, window_end=t1):
                for prompt in prompts:
                    cues.extend(extract_dialogue_cues(prompt, db, project_id))
            if cues:
                kind = "prompt_dialogue"
                speakers = cues
            elif prompt_text_implies_speech(prompt_text) and not _defer_scene_level_prompt_speech(
                prompts, timeline, window_end=t1
            ):
                # Owner law: authored dialogue present but cues unresolved →
                # surface error; never authorize silent success (speechKind=none).
                # Skip when scene-level Timed Prompt deliberately defers speech to a later window.
                kind = "prompt_dialogue_unresolved"
                errors.append(
                    {
                        "code": "REQUIRED_SPEECH_UNRESOLVED",
                        "message": (
                            "Prompt contains dialogue/screenplay speech but no speaker cue "
                            "could be bound. Assign character bindings or fix speaker lines "
                            "before generate — silent success is not allowed."
                        ),
                        "severity": "error",
                        "windowStart": t0,
                        "windowEnd": t1,
                    }
                )
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
    # A03/A01: master batch.promptSegments is generation speech authority.
    master_segs = list(getattr(batch, "promptSegments", None) or [])
    master_has_text = any(str(getattr(s, "text", "") or "").strip() for s in master_segs)
    errors: list[dict[str, Any]] = []
    if master_has_text:
        errors = lipsync_speaker_errors(director_timeline)
        cues: list[dict[str, Any]] = []
        prompt_text_parts: list[str] = []
        binding_ids: list[str] = []
        for seg in master_segs:
            t = str(getattr(seg, "text", "") or "").strip()
            if t:
                prompt_text_parts.append(t)
            for bid in (
                getattr(seg, "reference_binding_ids", None)
                or getattr(seg, "referenceBindingIds", None)
                or []
            ):
                if bid and bid not in binding_ids:
                    binding_ids.append(bid)
            try:
                cues.extend(extract_dialogue_cues(seg, db, project_id))
            except Exception:
                pass
        prompt_text = "\n".join(prompt_text_parts)
        lips = []
        if director_timeline is not None:
            lips = [
                clip
                for clip in _lipsync_covering(
                    director_timeline, float(window_start or 0.0), float(end)
                )
                if (clip.audio_asset_id or "").strip()
            ]
        speakers: list[dict[str, Any]] = []
        kind = "none"
        if lips:
            kind = "lipsync_audio"
            for clip in lips:
                speaker = _speaker_identity(clip, None, director_timeline) or (
                    clip.speaker_binding_id or clip.character_id
                )
                resolved = resolve_binding_id(db, project_id, speaker) if db is not None else {}
                if not isinstance(resolved, dict):
                    resolved = {}
                character_id = resolved.get("identityId") or clip.character_id or speaker
                speakers.append(
                    {
                        "speakerBindingId": clip.speaker_binding_id or speaker,
                        "audioAssetId": clip.audio_asset_id,
                        "characterId": character_id,
                        "characterName": resolved.get("alias") or clip.character_name,
                        "assignedVoiceId": _active_voice_id(db, character_id),
                        "clipId": clip.id,
                    }
                )
        elif cues:
            kind = "prompt_dialogue"
            speakers = cues
        elif prompt_text_implies_speech(prompt_text):
            kind = "prompt_dialogue_unresolved"
            errors.append(
                {
                    "code": "REQUIRED_SPEECH_UNRESOLVED",
                    "message": (
                        "batch.promptSegments contain dialogue/screenplay speech but no "
                        "speaker cue could be bound. Silent success is not allowed."
                    ),
                    "severity": "error",
                    "windowStart": float(window_start or 0.0),
                    "windowEnd": float(end),
                }
            )
        windows = [
            {
                "start": float(window_start or 0.0),
                "end": float(end),
                "promptText": prompt_text,
                "referenceBindingIds": binding_ids,
                "speechKind": kind,
                "speakers": speakers,
            }
        ]
    else:
        # PHASE23_SPEECH_MASTER_ONLY: do NOT fall back to legacy director
        # prompt_segments as generate speech SoT when Master has no text.
        # Lipsync audio clips may still inform speakers; prompt text authority
        # remains Master-only (empty Master => no prompt speech windows).
        errors = lipsync_speaker_errors(director_timeline)
        lips = []
        if director_timeline is not None:
            lips = [
                clip
                for clip in _lipsync_covering(
                    director_timeline, float(window_start or 0.0), float(end)
                )
                if (clip.audio_asset_id or "").strip()
            ]
        speakers: list[dict[str, Any]] = []
        kind = "none"
        if lips:
            kind = "lipsync_audio"
            for clip in lips:
                speaker = _speaker_identity(clip, None, director_timeline) or (
                    clip.speaker_binding_id or clip.character_id
                )
                resolved = resolve_binding_id(db, project_id, speaker) if db is not None else {}
                if not isinstance(resolved, dict):
                    resolved = {}
                character_id = resolved.get("identityId") or clip.character_id or speaker
                speakers.append(
                    {
                        "speakerBindingId": clip.speaker_binding_id or speaker,
                        "audioAssetId": clip.audio_asset_id,
                        "characterId": character_id,
                        "characterName": resolved.get("alias") or clip.character_name,
                        "assignedVoiceId": _active_voice_id(db, character_id),
                        "clipId": clip.id,
                    }
                )
        if not master_has_text and not lips:
            pass
        windows = [
            {
                "start": float(window_start or 0.0),
                "end": float(end),
                "promptText": "",
                "referenceBindingIds": [],
                "speechKind": kind,
                "speakers": speakers,
            }
        ] if lips else []
    batch.speechWindows = windows
    # Dialogue Manifest authority (from speechWindows) — no second script DB.
    if db is not None and project_id:
        try:
            from .dialogue_authority import compile_dialogue_authority_for_batch

            scene_id = getattr(batch, "sceneId", None) or ""
            compile_dialogue_authority_for_batch(
                db,
                project_id=str(project_id),
                scene_id=str(scene_id),
                batch=batch,
                master=master,
            )
        except Exception as exc:
            # REBUILD LAW (dialogue authority): a failed fresh compile must
            # NEVER leave the prior revision's cached manifest in place — the
            # submit preflight would ship stale authorized speakers/lines as
            # if they were current. Drop the cached manifest so the preflight
            # fails closed (missing authority) instead of silently reusing a
            # stale one. The compile error is logged and re-raised to the
            # caller's own fail-closed handling.
            from .dialogue_authority import DIALOGUE_MANIFEST_KIND

            batch.references = [
                r
                for r in (getattr(batch, "references", None) or [])
                if not (isinstance(r, dict) and r.get("kind") == DIALOGUE_MANIFEST_KIND)
            ]
            if hasattr(batch, "dialogueManifest"):
                try:
                    batch.dialogueManifest = None
                except Exception:
                    pass
            raise RuntimeError(
                f"Dialogue manifest compile failed for batch {getattr(batch, 'id', '?')} — "
                "cached manifest dropped (fail-closed)."
            ) from exc
    return errors


def _scene_level_prompt_midpoint(prompts: list[Any], timeline: DirectorTimeline) -> float | None:
    scene_dur = float(getattr(timeline, "duration_sec", 0) or 0.0)
    if scene_dur <= 0:
        return None
    for prompt in prompts:
        length = float(getattr(prompt, "length", 0) or 0.0)
        start = float(getattr(prompt, "start", 0) or 0.0)
        if length >= scene_dur - 0.05 and start <= 0.05:
            return start + (length / 2.0)
    return None


def _defer_scene_level_prompt_speech(
    prompts: list[Any],
    timeline: DirectorTimeline,
    *,
    window_end: float,
) -> bool:
    """True when this window is the first half of a scene-length Timed Prompt."""
    midpoint = _scene_level_prompt_midpoint(prompts, timeline)
    if midpoint is None:
        return False
    return float(window_end) <= midpoint + 0.05


def spoken_line_from_segment(
    segment: Any,
    db: Session | None = None,
    project_id: str | None = None,
) -> str:
    existing = str(getattr(segment, "dialogue", None) or "").strip()
    if existing:
        return existing
    try:
        cues = extract_dialogue_cues(segment, db, project_id)
    except Exception:
        cues = []
    if not cues:
        return ""
    return str(cues[0].get("exactText") or cues[0].get("text") or "").strip()


def hydrate_spoken_dialogue_on_master(
    master: Any,
    db: Session | None = None,
    project_id: str | None = None,
) -> int:
    """Persist extracted spoken lines onto Timed Prompt.dialogue. Returns change count."""
    changed = 0
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            if str(getattr(seg, "dialogue", None) or "").strip():
                continue
            line = spoken_line_from_segment(seg, db, project_id)
            if not line:
                continue
            try:
                seg.dialogue = line
                changed += 1
            except Exception:
                continue
    return changed
