"""Co-Director Dialogue Authority — multilingual spoken-language + locked-script QC.

HARD LAW (SCOPE_MULTILINGUAL_AUTHORITY):
  Multilingual capability != multilingual improvisation.
  Spoken language ONLY from: line -> scene -> project (most specific wins).
  NEVER from: UI/browser locale, Co-Director response language, generator defaults,
  prior/ref audio language, Omni/Qwen detection, provider region, character names.

A Dialogue Manifest is the sole dialogue authority for generate -> Omni QC -> Re-Take.
Omni observation never rewrites authority. UNCERTAIN != PASS.
Render complete != SCENE_FINISHED when dialogue QC fails.
No language blacklist (Latin/Welsh/etc. are unauthorized-speech cases, not blocklists).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIALOGUE_MANIFEST_KIND = "dialogueManifest"
DIALOGUE_QC_KIND = "dialogueQcDiagnostics"
SPOKEN_LANGUAGE_SETTINGS_KEY = "spokenLanguage"
# UI blob under settings_json["language"] — NEVER spoken authority.
UI_LANGUAGE_SETTINGS_KEY = "language"

DEFAULT_ALLOW_ADLIBS = False
DEFAULT_ALLOW_LANGUAGE_SWITCH = False

STATUS_NEEDS_DIALOGUE_RETAKE = "NeedsDialogueRetake"
STATUS_QC_PENDING = "QC_Pending"
STATUS_QC_RETRY_REQUIRED = "QC_RetryRequired"
CODE_OMNI_UNAVAILABLE = "OMNI_UNAVAILABLE"
AUTHORITY_PACKET_KIND = "languageAuthorityPacket"
QC_PASS = "PASS"
QC_FAIL = "FAIL"
QC_UNCERTAIN = "UNCERTAIN"

# Empty Omni transcript + locked speech expected: energy corroboration threshold.
# mean_volume (ffmpeg volumedetect) ≳ this dB => loud audio, not true silence.
# Scene 12B false-silent evidence was ~-15..-17 dB with empty Omni transcript.
LOUD_MEAN_VOLUME_DB = -25.0
CODE_OMNI_TRANSCRIPT_MISS = "OMNI_TRANSCRIPT_MISS"
CODE_SILENT_WHEN_SPEECH_EXPECTED = "SILENT_WHEN_SPEECH_EXPECTED"
CODE_SPEECH_WHEN_SILENCE_EXPECTED = "SPEECH_WHEN_SILENCE_EXPECTED"
CODE_UNAUTHORIZED_BACKGROUND_SPEAKER = "UNAUTHORIZED_BACKGROUND_SPEAKER"
CODE_WRONG_SPEAKER = "WRONG_SPEAKER"
CODE_MODALITY_CONFLICT = "MODALITY_CONFLICT"

# Manifest expectedSpeech enum (authority — not Omni inference).

EXPECTED_SPEECH_SPEECH = "SPEECH"
EXPECTED_SPEECH_NONE = "NONE"
EXPECTED_SPEECH_OPEN = "OPEN"

# Permanent Language Authority speech classifications (Brad).
CLASS_AUTHORIZED_DIALOGUE = "AUTHORIZED_DIALOGUE"
CLASS_AUTHORIZED_LANGUAGE_VARIATION = "AUTHORIZED_LANGUAGE_VARIATION"
CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT = "UNAUTHORIZED_LANGUAGE_ARTIFACT"
CLASS_UNAUTHORIZED_SPEECH = "UNAUTHORIZED_SPEECH"
CLASS_UNCERTAIN_SPEECH = "UNCERTAIN_SPEECH"
SPEECH_CLASSIFICATIONS = frozenset({
    CLASS_AUTHORIZED_DIALOGUE,
    CLASS_AUTHORIZED_LANGUAGE_VARIATION,
    CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
    CLASS_UNAUTHORIZED_SPEECH,
    CLASS_UNCERTAIN_SPEECH,
})
CODE_UNAUTHORIZED_LANGUAGE = "UNAUTHORIZED_LANGUAGE"

# Gate verdict name (Primary owns GO).
GATE_NAME = "CO-DIRECTOR MULTILINGUAL LANGUAGE AUTHORITY + DIALOGUE SANITATION VERIFIED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nid(prefix: str = "dlg_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# A/B — Language authority resolution (line -> scene -> project)
# ---------------------------------------------------------------------------

def _norm_lang(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Accept BCP-47-ish tags; do not map through UI locale registry as authority.
    primary = text.replace("_", "-")
    return primary


def parse_settings_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def read_ui_language_blob(settings_json: Any) -> dict[str, Any]:
    """Return the UI/CD language blob only — never use as spoken authority."""
    settings = parse_settings_object(settings_json)
    blob = settings.get(UI_LANGUAGE_SETTINGS_KEY) or {}
    return blob if isinstance(blob, dict) else {}


def read_project_spoken_language(settings_json: Any) -> Optional[str]:
    """Explicit project spoken language. Ignores UI interface/conversation locales."""
    settings = parse_settings_object(settings_json)
    spoken = settings.get(SPOKEN_LANGUAGE_SETTINGS_KEY) or {}
    if isinstance(spoken, dict):
        lang = _norm_lang(spoken.get("projectLanguage") or spoken.get("language"))
        if lang:
            return lang
    # Do NOT fall back to settings.language.interfaceLocale / conversationLocale.
    # Optional one-hop promote only when an EXPLICIT projectPrimaryLocale was stored
    # under settings.language (has blob) — still not interfaceLocale.
    return None


def has_explicit_ui_project_primary(settings_json: Any) -> bool:
    settings = parse_settings_object(settings_json)
    blob = settings.get(UI_LANGUAGE_SETTINGS_KEY)
    if not isinstance(blob, dict) or not blob:
        return False
    return bool(_norm_lang(blob.get("projectPrimaryLocale")))


def promote_project_primary_to_spoken_if_explicit(settings_json: Any) -> tuple[str, Optional[str]]:
    """If UI language blob exists with projectPrimaryLocale, seed spoken projectLanguage.

    Does nothing when settings.language is missing (Quarters case) — that remains
    SPOKEN_LANGUAGE_AUTHORITY_MISSING until an explicit spokenLanguage is written.
    Never reads interfaceLocale / conversationLocale / browser locale.
    Returns (new_settings_json, spoken_language_or_none).
    """
    settings = parse_settings_object(settings_json)
    existing = read_project_spoken_language(settings)
    if existing:
        return json.dumps(settings), existing
    if not has_explicit_ui_project_primary(settings):
        return json.dumps(settings) if settings else (settings_json or "{}"), None
    blob = settings.get(UI_LANGUAGE_SETTINGS_KEY) or {}
    primary = _norm_lang(blob.get("projectPrimaryLocale"))
    if not primary:
        return json.dumps(settings), None
    settings[SPOKEN_LANGUAGE_SETTINGS_KEY] = {
        "projectLanguage": primary,
        "source": "promoted_from_explicit_projectPrimaryLocale",
        "updatedAt": _now(),
        "uiLanguageIsolated": True,
    }
    return json.dumps(settings), primary


def write_project_spoken_language(settings_json: Any, language: str, *, source: str = "explicit") -> str:
    settings = parse_settings_object(settings_json)
    lang = _norm_lang(language)
    if not lang:
        raise ValueError("SPOKEN_LANGUAGE_REQUIRED")
    settings[SPOKEN_LANGUAGE_SETTINGS_KEY] = {
        "projectLanguage": lang,
        "source": source,
        "updatedAt": _now(),
        "uiLanguageIsolated": True,
    }
    return json.dumps(settings)



def write_scene_spoken_language(master: Any, language: str, *, source: str = "explicit") -> str:
    """Set SceneTimelineMaster.sceneLanguage. Never writes UI locale blobs."""
    lang = _norm_lang(language)
    if not lang:
        raise ValueError("SPOKEN_LANGUAGE_REQUIRED")
    if master is None:
        raise ValueError("SCENE_MASTER_REQUIRED")
    if isinstance(master, dict):
        master["sceneLanguage"] = lang
        spoken = dict(master.get("spokenLanguage") or {})
        spoken["sceneLanguage"] = lang
        spoken["source"] = source
        spoken["updatedAt"] = _now()
        spoken["uiLanguageIsolated"] = True
        master["spokenLanguage"] = spoken
    else:
        master.sceneLanguage = lang
        spoken = getattr(master, "spokenLanguage", None)
        if isinstance(spoken, dict) or spoken is None:
            blob = dict(spoken or {})
            blob["sceneLanguage"] = lang
            blob["source"] = source
            blob["updatedAt"] = _now()
            blob["uiLanguageIsolated"] = True
            try:
                master.spokenLanguage = blob
            except Exception:
                pass
    return lang


def read_scene_spoken_language(master: Any) -> Optional[str]:
    if master is None:
        return None
    direct = _norm_lang(getattr(master, "sceneLanguage", None))
    if direct:
        return direct
    if isinstance(master, dict):
        return _norm_lang(master.get("sceneLanguage") or (master.get("spokenLanguage") or {}).get("sceneLanguage"))
    spoken = getattr(master, "spokenLanguage", None)
    if isinstance(spoken, dict):
        return _norm_lang(spoken.get("sceneLanguage") or spoken.get("language"))
    return None


def resolve_line_language(
    *,
    line_language: Any = None,
    scene_language: Any = None,
    project_language: Any = None,
) -> dict[str, Any]:
    """Inheritance: line -> scene -> project. Never UI."""
    line = _norm_lang(line_language)
    scene = _norm_lang(scene_language)
    project = _norm_lang(project_language)
    if line:
        return {"language": line, "source": "line", "explicit": True}
    if scene:
        return {"language": scene, "source": "scene", "explicit": True}
    if project:
        return {"language": project, "source": "project", "explicit": True}
    return {
        "language": None,
        "source": "missing",
        "explicit": False,
        "error": "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
    }


# ---------------------------------------------------------------------------
# A — Dialogue Manifest (canonical from existing script / speechWindows)
# ---------------------------------------------------------------------------

def _speaker_entries_from_windows(speech_windows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for window in speech_windows or []:
        if not isinstance(window, dict):
            continue
        kind = str(window.get("speechKind") or "")
        # prompt_dialogue / lipsync_audio carry speaker text; "none" does not.
        speakers = window.get("speakers") or []
        start = window.get("start")
        end = window.get("end")
        for sp in speakers:
            if not isinstance(sp, dict):
                continue
            text = (sp.get("text") or sp.get("exactText") or "").strip()
            # Lip-sync windows may omit text (audio asset owns speech); skip empty for locked script.
            if not text and kind != "lipsync_audio":
                continue
            lines.append(
                {
                    "lineId": _nid("line_"),
                    "speakerId": sp.get("characterId") or sp.get("speakerBindingId") or sp.get("speakerName"),
                    "speakerBindingId": sp.get("speakerBindingId"),
                    "speakerName": sp.get("speakerName"),
                    "characterId": sp.get("characterId"),
                    "assignedVoiceId": sp.get("assignedVoiceId"),
                    "text": text,
                    "language": _norm_lang(sp.get("language")),
                    "start": sp.get("start", start),
                    "end": sp.get("end", end),
                    "speechKind": kind,
                    "audioAssetId": sp.get("audioAssetId"),
                }
            )
    return lines


def resolve_expected_speech(
    *,
    lines: list[dict[str, Any]] | None = None,
    allow_adlibs: bool = DEFAULT_ALLOW_ADLIBS,
    explicit: Any = None,
) -> str:
    """Resolve expectedSpeech enum for a Manifest.

    SPEECH  — scripted lines exist (speech required).
    NONE    — no scripted lines and allowAdLibs=false (silence locked).
    OPEN    — no scripted lines but ad-libs allowed (not silence-locked).

    Explicit expectedSpeech on the Manifest wins when provided.
    Never inferred from Omni / ASR.
    """
    if explicit is not None and str(explicit).strip():
        val = str(explicit).strip().upper()
        if val in (EXPECTED_SPEECH_SPEECH, EXPECTED_SPEECH_NONE, EXPECTED_SPEECH_OPEN):
            return val
        if val in ("REQUIRED", "YES", "TRUE", "1"):
            return EXPECTED_SPEECH_SPEECH
        if val in ("SILENCE", "SILENT", "NO", "FALSE", "0"):
            return EXPECTED_SPEECH_NONE
    has_lines = bool(lines)
    if has_lines:
        return EXPECTED_SPEECH_SPEECH
    if not allow_adlibs:
        return EXPECTED_SPEECH_NONE
    return EXPECTED_SPEECH_OPEN


def _authorized_speaker_keys(manifest: dict[str, Any]) -> set[str]:
    """Lowercased speaker identity keys from Manifest lines / speakers list."""
    keys: set[str] = set()
    for ln in manifest.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        for field in ("speakerName", "speakerId", "characterId", "speakerBindingId"):
            val = ln.get(field)
            if val is not None and str(val).strip():
                keys.add(str(val).strip().lower())
    for sp in manifest.get("speakers") or []:
        if isinstance(sp, str) and sp.strip():
            keys.add(sp.strip().lower())
        elif isinstance(sp, dict):
            for field in ("speakerName", "speakerId", "characterId", "speakerBindingId", "name", "id"):
                val = sp.get(field)
                if val is not None and str(val).strip():
                    keys.add(str(val).strip().lower())
    return keys


def _observed_speaker_labels(observed: dict[str, Any] | None) -> list[str]:
    """Speaker labels Omni reported on segments — observation only, never authority."""
    labels: list[str] = []
    for s in (observed or {}).get("segments") or []:
        if not isinstance(s, dict):
            continue
        # Only count segments that actually carry speech text (background chatter).
        text = (s.get("transcription") or s.get("text") or "").strip()
        if not text:
            continue
        sp = s.get("speaker") or s.get("speakerName") or s.get("speakerId")
        if sp is None:
            continue
        label = str(sp).strip()
        if label:
            labels.append(label)
    return labels


_SPEECH_SUMMARY_RE = re.compile(
    r"\b(speaking|speaks|spoken|speech|dialogue|talking|talks|"
    r"foreign language|gibberish|whisper(?:ing)?|muttering|phonation|utterance|utterances|"
    r"vocalization|vocalizations|syllable|lip.?sync|human voice)\b",
    re.I,
)
_SILENCE_SUMMARY_RE = re.compile(
    r"\b(silent|silence|no spee?ch|no dialogue|no voice|ambience only|atmosphere only|"
    r"footsteps only|no human voice|mute)\b",
    re.I,
)
# Fail-closed: silence-locked PASS needs energy quieter than this (dB).
QUIET_MEAN_VOLUME_DB = -40.0


def _has_observed_speech(observed: dict[str, Any] | None) -> bool:
    """True when Omni observation indicates unauthorized speech activity.

    Empty ASR is NOT proof of silence: isSilence=false segments and speech-like
    summary language count as observed speech (P6 foreign-speech NO-GO).
    """
    if not observed:
        return False
    transcript = (observed.get("transcript") or "").strip()
    if transcript:
        return True
    summary = str(observed.get("summary") or "").strip()
    if summary and _SPEECH_SUMMARY_RE.search(summary):
        # Negated silence phrases are not speech evidence.
        if _SILENCE_SUMMARY_RE.search(summary) and not re.search(
            r"\b(speaking|speaks|spoken|utterance|utterances|gibberish|foreign language|dialogue|talking)\b",
            summary,
            re.I,
        ):
            pass
        else:
            return True
    for s in observed.get("segments") or []:
        if not isinstance(s, dict):
            continue
        if (s.get("transcription") or s.get("text") or "").strip():
            return True
        # Explicit non-silence segment even with empty transcription.
        if s.get("isSilence") is False:
            return True
        if str(s.get("isSilence") or "").strip().lower() in ("false", "0", "no"):
            return True
    return False




def _has_positive_silence_evidence(
    observed: dict[str, Any] | None,
    mean_volume_db: float | None,
) -> bool:
    """Silence-locked PASS requires affirmative silence — empty ASR is not enough.

    Gate slip (P6 v3): dialogueQc PASS on empty transcript while media-intel heard speech.

    Path (b) / Chief CLEAR: media with no audio track (hasAudio=False / audio_streams=0)
    is affirmative silence for silence-lock — stronger than empty ASR. Empty ASR alone
    still does not PASS. Omni worker timeout remains unavailable (not this path).
    """
    obs = observed or {}
    # Explicit no-audio-track evidence (ffprobe / Omni media.hasAudio=False).
    if obs.get("hasAudio") is False or str(obs.get("availability") or "").strip().lower() in (
        "no_audio_track",
        "video_only",
    ):
        return True
    segs = list(obs.get("segments") or [])
    if segs:
        flags = []
        for s in segs:
            if not isinstance(s, dict):
                continue
            raw = s.get("isSilence")
            if raw is True or str(raw).strip().lower() in ("true", "1", "yes"):
                flags.append(True)
            elif raw is False or str(raw).strip().lower() in ("false", "0", "no"):
                flags.append(False)
        if flags and all(flags):
            return True
        if flags and any(f is False for f in flags):
            return False
    summary = str((observed or {}).get("summary") or "").strip()
    if summary and _SILENCE_SUMMARY_RE.search(summary) and not _SPEECH_SUMMARY_RE.search(summary):
        return True
    if mean_volume_db is not None:
        try:
            if float(mean_volume_db) <= float(QUIET_MEAN_VOLUME_DB):
                return True
        except (TypeError, ValueError):
            pass
    return False



def _authorized_languages_from_lines(
    lines: list[dict[str, Any]],
    *,
    expected: str,
    manifest_lang: Any = None,
) -> list[str]:
    """Silent => []; EN-only => ["en"]; multi-scripted => unique line codes only."""
    if expected == EXPECTED_SPEECH_NONE or not lines:
        return []
    langs: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        code = _norm_lang(ln.get("language"))
        if code and code not in seen:
            seen.add(code)
            langs.append(code)
    if langs:
        return langs
    m = _norm_lang(manifest_lang)
    return [m] if m else []


def language_authority_fields(
    *,
    lines: list[dict[str, Any]] | None,
    speakers: list[str] | None = None,
    expected: str | None = None,
    manifest_lang: Any = None,
    allow_adlibs: bool = False,
) -> dict[str, Any]:
    """Brad permanent Language Authority surface for an execution window."""
    clean_lines = [ln for ln in (lines or []) if (ln.get("text") or "").strip() or ln.get("audioAssetId")]
    exp = resolve_expected_speech(
        lines=clean_lines,
        allow_adlibs=allow_adlibs,
        explicit=expected,
    )
    if exp == EXPECTED_SPEECH_NONE or not clean_lines:
        return {
            "authorized_dialogue_lines": [],
            "authorized_speakers": [],
            "authorized_languages": [],
        }
    auth_speakers = sorted(
        {
            str(ln.get("speakerName") or ln.get("speakerId") or "").strip()
            for ln in clean_lines
            if (ln.get("speakerName") or ln.get("speakerId"))
        }
    )
    if speakers:
        # Prefer explicit speaker list when provided and non-empty.
        auth_speakers = list(speakers) if not auth_speakers else auth_speakers
    return {
        "authorized_dialogue_lines": [
            {
                "lineId": ln.get("lineId"),
                "speakerId": ln.get("speakerId"),
                "speakerName": ln.get("speakerName"),
                "text": ln.get("text"),
                "language": ln.get("language"),
            }
            for ln in clean_lines
        ],
        "authorized_speakers": auth_speakers,
        "authorized_languages": _authorized_languages_from_lines(
            clean_lines, expected=exp, manifest_lang=manifest_lang
        ),
    }


def _looks_like_gibberish(transcript: str) -> bool:
    t = (transcript or "").strip()
    if not t:
        return False
    low = t.lower()
    if any(k in low for k in ("gibberish", "nonsense", "unintelligible", "non-lexical", "phonation")):
        return True
    # Repeated single token e.g. "the the the the"
    toks = re.findall(r"[A-Za-z']+", t)
    if len(toks) >= 4 and len(set(tok.lower() for tok in toks)) <= 2:
        return True
    # High non-letter ratio without whitespace words
    letters = sum(ch.isalpha() for ch in t)
    if len(t) >= 8 and letters / max(len(t), 1) < 0.35:
        return True
    return False


def classify_observed_speech(
    manifest: dict[str, Any],
    observed: dict[str, Any] | None,
    *,
    verdict: str | None = None,
    mean_volume_db: float | None = None,
) -> str:
    """Map Omni observation vs Language Authority into Brad classification enum."""
    observed = observed or {}
    auth = language_authority_fields(
        lines=manifest.get("lines") or [],
        speakers=list(manifest.get("speakers") or []),
        expected=manifest.get("expectedSpeech"),
        manifest_lang=manifest.get("language"),
        allow_adlibs=bool(manifest.get("allowAdLibs")),
    )
    auth_langs = {_norm_lang(x) for x in (auth.get("authorized_languages") or []) if _norm_lang(x)}
    # Prefer explicit Brad fields if already on manifest.
    if manifest.get("authorized_languages") is not None:
        auth_langs = {_norm_lang(x) for x in (manifest.get("authorized_languages") or []) if _norm_lang(x)}
    silence = (
        resolve_expected_speech(
            lines=manifest.get("lines") or [],
            allow_adlibs=bool(manifest.get("allowAdLibs")),
            explicit=manifest.get("expectedSpeech"),
        )
        == EXPECTED_SPEECH_NONE
        or not (auth.get("authorized_dialogue_lines") or [])
    )
    transcript = (observed.get("transcript") or "").strip()
    obs_lang = _norm_lang(observed.get("languageCode"))
    has_speech = _has_observed_speech(observed)
    loud = audio_energy_is_loud(mean_volume_db)

    if verdict == QC_UNCERTAIN or (
        silence and not transcript and (loud or has_speech or not _has_positive_silence_evidence(observed, mean_volume_db=mean_volume_db))
        and (loud or has_speech or (observed.get("availability") == "unavailable"))
    ):
        # Empty ASR + acoustic evidence / missing Omni under silence => uncertain
        if silence and (loud or has_speech) and not transcript:
            return CLASS_UNCERTAIN_SPEECH
        if verdict == QC_UNCERTAIN and silence:
            return CLASS_UNCERTAIN_SPEECH

    if silence:
        if has_speech or transcript:
            if obs_lang and obs_lang not in (None,) and (not auth_langs or obs_lang not in auth_langs):
                return CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
            if _looks_like_gibberish(transcript):
                return CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
            return CLASS_UNAUTHORIZED_SPEECH
        return CLASS_AUTHORIZED_DIALOGUE  # true silence under empty auth

    # Speech expected / scripted
    if not transcript and (loud or has_speech):
        return CLASS_UNCERTAIN_SPEECH
    if obs_lang and auth_langs and obs_lang not in auth_langs:
        return CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
    if _looks_like_gibberish(transcript) and (not auth_langs or (obs_lang and obs_lang not in auth_langs)):
        return CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
    if has_speech or transcript:
        # Within authorized language(s)
        if not auth_langs or (obs_lang in auth_langs) or (obs_lang is None and auth_langs):
            # Unknown lang with speech under restricted auth => uncertain unless fidelity clear
            if obs_lang is None and auth_langs and not allow_switchish(manifest):
                # Still allow AUTHORIZED_DIALOGUE when script coverage will decide; variation path unused without lang
                return CLASS_AUTHORIZED_DIALOGUE
            return CLASS_AUTHORIZED_DIALOGUE
        return CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
    return CLASS_UNCERTAIN_SPEECH


def allow_switchish(manifest: dict[str, Any]) -> bool:
    return bool(manifest.get("allowLanguageSwitch"))



def build_dialogue_manifest(
    *,
    project_id: str,
    scene_id: str,
    batch_id: str | None = None,
    speech_windows: list[dict[str, Any]] | None = None,
    scene_language: Any = None,
    project_language: Any = None,
    allow_adlibs: bool = DEFAULT_ALLOW_ADLIBS,
    allow_language_switch: bool = DEFAULT_ALLOW_LANGUAGE_SWITCH,
    extra_lines: list[dict[str, Any]] | None = None,
    expected_speech: Any = None,
) -> dict[str, Any]:
    """Build the sole Dialogue Manifest from compiled speech / script cues.

    No second script DB. allowAdLibs / allowLanguageSwitch default False (locked).
    expectedSpeech: SPEECH | NONE | OPEN — explicit or inferred from lines + allowAdLibs.
    """
    raw_lines = list(extra_lines or []) + _speaker_entries_from_windows(speech_windows)
    lines: list[dict[str, Any]] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            continue
        resolved = resolve_line_language(
            line_language=raw.get("language"),
            scene_language=scene_language,
            project_language=project_language,
        )
        entry = {
            "lineId": raw.get("lineId") or _nid("line_"),
            "speakerId": raw.get("speakerId") or raw.get("characterId") or raw.get("speakerBindingId"),
            "speakerBindingId": raw.get("speakerBindingId"),
            "speakerName": raw.get("speakerName"),
            "characterId": raw.get("characterId"),
            "assignedVoiceId": raw.get("assignedVoiceId"),
            "text": (raw.get("text") or "").strip(),
            "language": resolved.get("language"),
            "languageSource": resolved.get("source"),
            "languageExplicit": bool(resolved.get("explicit")),
            "start": raw.get("start"),
            "end": raw.get("end"),
            "speechKind": raw.get("speechKind"),
            "audioAssetId": raw.get("audioAssetId"),
        }
        if entry["text"] or entry.get("audioAssetId"):
            lines.append(entry)

    scripted = bool(lines)
    # Primary law: scripted manifests lock ad-libs / language switch to False.
    if scripted:
        adlibs = False
        lang_switch = False
    else:
        adlibs = bool(allow_adlibs)
        lang_switch = bool(allow_language_switch)

    expected = resolve_expected_speech(
        lines=lines, allow_adlibs=adlibs, explicit=expected_speech
    )
    # Silence-locked (NONE) or scripted lines => lockedScript authority holds.
    locked = bool(scripted) or expected == EXPECTED_SPEECH_NONE

    # Manifest-level language = unanimous line language, else scene, else project.
    languages = [ln["language"] for ln in lines if ln.get("language")]
    unanimous = languages[0] if languages and all(x == languages[0] for x in languages) else None
    scene_l = _norm_lang(scene_language)
    project_l = _norm_lang(project_language)
    manifest_lang = unanimous or scene_l or project_l
    # Speech-required needs language; silence-locked does not.
    authority_ok = bool(manifest_lang) if scripted else True

    speakers = sorted(
        {
            str(ln.get("speakerName") or ln.get("speakerId") or "").strip()
            for ln in lines
            if (ln.get("speakerName") or ln.get("speakerId"))
        }
    )

    return {
        "kind": DIALOGUE_MANIFEST_KIND,
        "manifestId": _nid("manif_"),
        "schemaVersion": "dialogue-manifest-v1",
        "projectId": project_id,
        "sceneId": scene_id,
        "batchId": batch_id,
        "language": manifest_lang,
        "projectLanguage": project_l,
        "sceneLanguage": scene_l,
        "allowAdLibs": False if scripted else adlibs,
        "allowLanguageSwitch": False if scripted else lang_switch,
        "lockedScript": locked,
        "expectedSpeech": expected,
        "speakers": speakers,
        "authorityExplicit": authority_ok,
        "authorityError": None if authority_ok else "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
        "uiLanguageIsolated": True,
        "lines": lines,
        "lineCount": len(lines),
        "createdAt": _now(),
        "notes": "Canonical dialogue authority. Omni observes; never rewrites this manifest.",
        **language_authority_fields(
            lines=lines,
            speakers=speakers,
            expected=expected,
            manifest_lang=manifest_lang,
            allow_adlibs=False if scripted else adlibs,
        ),
    }


def attach_manifest_to_batch(batch: Any, manifest: dict[str, Any]) -> None:
    refs = [r for r in (getattr(batch, "references", None) or []) if not (isinstance(r, dict) and r.get("kind") == DIALOGUE_MANIFEST_KIND)]
    refs.append(manifest)
    batch.references = refs
    # Mirror for fast access when BatchBlock supports the field.
    if hasattr(batch, "dialogueManifest"):
        try:
            batch.dialogueManifest = manifest
        except Exception:
            pass


def get_manifest_from_batch(batch: Any) -> Optional[dict[str, Any]]:
    direct = getattr(batch, "dialogueManifest", None)
    if isinstance(direct, dict) and direct.get("kind") == DIALOGUE_MANIFEST_KIND:
        return direct
    for r in getattr(batch, "references", None) or []:
        if isinstance(r, dict) and r.get("kind") == DIALOGUE_MANIFEST_KIND:
            return r
    return None


def manifest_needs_authority_recompile(manifest: dict[str, Any] | None) -> bool:
    """True when a cached locked-script manifest still lacks spoken-language authority.

    Generate must recompile after the creator persists scene/project language.
    Do not treat the stale miss as final.
    """
    if not isinstance(manifest, dict):
        return True
    return bool(
        manifest.get("lockedScript")
        and manifest.get("lines")
        and not manifest.get("authorityExplicit")
    )


def drop_dialogue_manifests(master: Any) -> int:
    """Remove cached dialogue manifests so the next compile reads current authority."""
    batches = getattr(master, "batchBlocks", None)
    if batches is None and isinstance(master, dict):
        batches = master.get("batchBlocks") or []
    dropped = 0
    for batch in batches or []:
        refs = getattr(batch, "references", None)
        if refs is None and isinstance(batch, dict):
            refs = batch.get("references")
        if not isinstance(refs, list):
            continue
        kept = [
            r
            for r in refs
            if not (isinstance(r, dict) and r.get("kind") == DIALOGUE_MANIFEST_KIND)
        ]
        if len(kept) != len(refs):
            dropped += 1
            if isinstance(batch, dict):
                batch["references"] = kept
            else:
                batch.references = kept
        if hasattr(batch, "dialogueManifest"):
            try:
                batch.dialogueManifest = None
            except Exception:
                pass
        elif isinstance(batch, dict) and "dialogueManifest" in batch:
            batch["dialogueManifest"] = None
    return dropped


# ---------------------------------------------------------------------------
# C/D — Locked-script compile + structured generator language payload
# ---------------------------------------------------------------------------

def build_generator_language_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Structured language + exact dialogue for H3/LTX/Seedance/Timeline R2V."""
    lines = []
    for ln in manifest.get("lines") or []:
        lines.append(
            {
                "speakerId": ln.get("speakerId"),
                "speakerName": ln.get("speakerName"),
                "text": ln.get("text"),
                "language": ln.get("language"),
                "start": ln.get("start"),
                "end": ln.get("end"),
            }
        )
    expected = resolve_expected_speech(
        lines=manifest.get("lines") or [],
        allow_adlibs=bool(manifest.get("allowAdLibs")),
        explicit=manifest.get("expectedSpeech"),
    )
    return {
        "dialogueAuthority": "manifest",
        "language": manifest.get("language"),
        "projectLanguage": manifest.get("projectLanguage"),
        "sceneLanguage": manifest.get("sceneLanguage"),
        "allowAdLibs": bool(manifest.get("allowAdLibs")),
        "allowLanguageSwitch": bool(manifest.get("allowLanguageSwitch")),
        "lockedScript": bool(manifest.get("lockedScript")),
        "expectedSpeech": expected,
        "speakers": list(manifest.get("speakers") or []),
        "exactScriptDialogue": bool(manifest.get("lockedScript"))
        and bool(manifest.get("authorityExplicit"))
        and expected == EXPECTED_SPEECH_SPEECH,
        "authorityExplicit": bool(manifest.get("authorityExplicit")),
        "lines": lines,
        "uiLanguageIsolated": True,
        # Honesty: H3 may still lack a Comfy language widget; structured state is canonical.
        "comfyLanguageWidget": "absent_on_h3",
        "promptReinforcementOk": True,
        "blacklist": None,  # never a forbidden-language list
        "authorized_dialogue_lines": list(manifest.get("authorized_dialogue_lines") or []),
        "authorized_speakers": list(manifest.get("authorized_speakers") or []),
        "authorized_languages": list(manifest.get("authorized_languages") or []),
    }


def apply_manifest_to_request(request: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    payload = build_generator_language_payload(manifest)
    opts = dict(getattr(request, "providerOptions", None) or {})
    opts["dialogueManifestId"] = manifest.get("manifestId")
    opts["dialogueAuthority"] = payload
    opts["spokenLanguage"] = {
        "language": manifest.get("language"),
        "projectLanguage": manifest.get("projectLanguage"),
        "sceneLanguage": manifest.get("sceneLanguage"),
        "source": "dialogue_manifest",
        "uiLanguageIsolated": True,
    }
    # Reinforce locked script in audioAuthority without reviving Lip Sync.
    aa = dict(opts.get("audioAuthority") or {})
    if manifest.get("lockedScript") and manifest.get("authorityExplicit"):
        aa["dialogue"] = "manifest_locked_script"
        aa["allowAdLibs"] = False
        aa["allowLanguageSwitch"] = False
        aa["spokenLanguage"] = manifest.get("language")
        # Keep generator_native as delivery mechanism when no timeline audio,
        # but mark that QC will enforce manifest fidelity.
        aa["exactScriptEnforcedBy"] = "omni_post_gen_qc"
    opts["audioAuthority"] = aa
    request.providerOptions = opts
    return payload


# ---------------------------------------------------------------------------
# E/F — Omni post-gen dialogue QC (observed != authority)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _normalize_transcript(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(_normalize_transcript(text)))


def _line_coverage(expected: str, observed: str) -> float:
    exp = _token_set(expected)
    if not exp:
        return 1.0 if not (observed or "").strip() else 0.0
    obs = _token_set(observed)
    if not obs:
        return 0.0
    hit = len(exp & obs)
    return hit / max(1, len(exp))




def _final_check_hints(
    *,
    retake_eligible: bool,
    auto_destroy: bool = False,
    acceptance_eligible: bool = False,
    creative_taste: bool = False,
    note: str | None = None,
    modality_conflict: bool = False,
    modalities: list[str] | tuple[str, ...] | None = None,
    conflict_reason: str | None = None,
) -> dict[str, Any]:
    """Hints Final Check can consume — not a Final Check UI/API.

    Hard Manifest/speaker/language violations stay retake-eligible.
    UNCERTAIN / OMNI_TRANSCRIPT_MISS / MODALITY_CONFLICT: not PASS, not auto-destroy.
    Absence of evidence from one Omni modality is NOT evidence of absence when
    another modality contradicts it (e.g. empty ASR + loud energy).
    Creative taste is never a retake signal. Bad ASR never becomes authority.
    Energy alone never invents speech (still != PASS).
    """
    out: dict[str, Any] = {
        "acceptanceEligible": bool(acceptance_eligible),
        "retakeEligible": bool(retake_eligible),
        "autoDestroy": bool(auto_destroy),
        "creativeTaste": bool(creative_taste),
        "authoritySource": "dialogue_manifest",
        "modalityConflict": bool(modality_conflict),
    }
    if modalities is not None:
        out["modalities"] = list(modalities)
    if conflict_reason:
        out["conflictReason"] = conflict_reason
    if note:
        out["note"] = note
    return out



def _find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def probe_mean_volume_db(path: str | Path, *, timeout_sec: float = 60.0) -> float | None:
    """Return ffmpeg volumedetect mean_volume (dB), or None if unprobeable.

    Deterministic energy corroboration only — never invents speech or rewrites
    Manifest authority. No stream / ffmpeg absent / parse failure => None.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostats",
                "-i",
                str(p),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception:
        return None
    # volumedetect logs to stderr
    blob = (proc.stderr or "") + "\n" + (proc.stdout or "")
    match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", blob)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def audio_energy_is_loud(mean_volume_db: float | None, *, threshold_db: float = LOUD_MEAN_VOLUME_DB) -> bool:
    """True when measured mean volume is at/above threshold (e.g. -16 >= -25)."""
    if mean_volume_db is None:
        return False
    try:
        return float(mean_volume_db) >= float(threshold_db)
    except (TypeError, ValueError):
        return False



def _media_has_audio_from_packet(packet: Any) -> bool | None:
    """Return False when media has no audio track; True when present; None unknown."""
    if packet is None:
        return None
    media = None
    reason = ""
    if isinstance(packet, dict):
        media = packet.get("media")
        reason = str(packet.get("reason") or "")
    else:
        media = getattr(packet, "media", None)
        reason = str(getattr(packet, "reason", None) or "")
    if media is not None:
        if isinstance(media, dict):
            if "hasAudio" in media:
                return bool(media.get("hasAudio"))
            try:
                ch = media.get("channels")
                sr = media.get("sampleRate")
                ac = str(media.get("audioCodec") or "").strip()
                if ch == 0 and sr == 0 and not ac:
                    return False
            except Exception:
                pass
        else:
            ha = getattr(media, "hasAudio", None)
            if ha is not None:
                return bool(ha)
            try:
                ch = getattr(media, "channels", None)
                sr = getattr(media, "sampleRate", None)
                ac = str(getattr(media, "audioCodec", None) or "").strip()
                if ch == 0 and sr == 0 and not ac:
                    return False
            except Exception:
                pass
    rl = reason.lower()
    if "must has audio" in rl or "must have audio" in rl or "use_audio_in_video" in rl:
        return False
    return None



def count_audio_streams(path: str | Path, *, timeout_sec: float = 30.0) -> int | None:
    """ffprobe audio stream count. None if unprobeable. 0 = video-only / no-audio track."""
    ffprobe = _find_ffprobe()
    if not ffprobe:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(p),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception:
        return None
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return len(lines)


def _find_ffprobe() -> str | None:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None
    # sibling ffprobe next to ffmpeg
    cand = Path(ffmpeg).with_name("ffprobe.exe" if Path(ffmpeg).suffix.lower() == ".exe" else "ffprobe")
    if cand.is_file():
        return str(cand)
    import shutil

    return shutil.which("ffprobe")


def _batch_generate_audio_flag(batch: Any) -> bool | None:
    """True/False when known; None unknown. silence_locked Gen path implies False."""
    if batch is None:
        return None
    for r in getattr(batch, "references", None) or []:
        if not isinstance(r, dict):
            continue
        aa = r.get("audioAuthority") if isinstance(r.get("audioAuthority"), dict) else None
        if aa is None and r.get("kind") in ("audioAuthority", "timelineGenerationLineage"):
            aa = r if r.get("authority") or "generateAudio" in r or "generate_audio" in r else None
        if isinstance(aa, dict):
            if "generateAudio" in aa:
                return bool(aa.get("generateAudio"))
            if "generate_audio" in aa:
                return bool(aa.get("generate_audio"))
            if str(aa.get("authority") or "").strip().lower() == "silence_locked":
                return False
        if "generate_audio" in r:
            return bool(r.get("generate_audio"))
        if "generateAudio" in r:
            return bool(r.get("generateAudio"))
    # providerOptions-style on batch
    for key in ("generate_audio", "generateAudio"):
        if hasattr(batch, key):
            return bool(getattr(batch, key))
        if isinstance(batch, dict) and key in batch:
            return bool(batch.get(key))
    return None


def is_silence_locked_authority(manifest: dict[str, Any] | None) -> bool:
    """True when dialogue authority is empty silence-lock (Chief path b).

    Ambience-on / speech-off (allowNonSpeechAudio) is NOT silence-locked: speech
    authority stays empty / expectedSpeech=NONE for QC, but native non-speech
    audio may be generated (no full mute).
    """
    if not isinstance(manifest, dict):
        return False
    if bool(manifest.get("allowNonSpeechAudio") or manifest.get("allow_non_speech_audio")):
        return False
    aa = manifest.get("audioAuthority") if isinstance(manifest.get("audioAuthority"), dict) else {}
    auth = str(aa.get("authority") or manifest.get("audioPolicy") or "").strip().lower()
    if auth in {"ambience_speech_off", "ambience_only", "ambience-on-speech-off"}:
        return False
    expected = resolve_expected_speech(
        lines=manifest.get("lines") or [],
        allow_adlibs=bool(manifest.get("allowAdLibs")),
        explicit=manifest.get("expectedSpeech"),
    )
    if expected != EXPECTED_SPEECH_NONE:
        return False
    langs = manifest.get("authorized_languages")
    lines = manifest.get("authorized_dialogue_lines")
    # empty auth sets (or missing → treat as empty under NONE)
    if langs is not None and list(langs):
        return False
    if lines is not None and list(lines):
        return False
    return True


def is_no_audio_generation_path(
    *,
    manifest: dict[str, Any] | None,
    batch: Any = None,
    asset_path: str | Path | None = None,
    audio_stream_count: int | None = None,
) -> bool:
    """Chief path (b) law:
    silence_locked + generate_audio=false + audio_streams=0 ⇒ affirmative silence.
    Do NOT require Omni ASR/energy. audio_streams>0 ⇒ full Omni QC.
    """
    if not is_silence_locked_authority(manifest):
        return False
    streams = audio_stream_count
    if streams is None and asset_path is not None:
        streams = count_audio_streams(asset_path)
    if streams is None or int(streams) != 0:
        return False
    gen = _batch_generate_audio_flag(batch)
    # silence_locked Gen request_builder always sets generateAudio=False; unknown ⇒ False
    if gen is True:
        return False
    return True

def annotate_observed_media_audio(observed: dict[str, Any], packet: Any) -> dict[str, Any]:
    """Attach hasAudio / no_audio_track availability for path-(b) silence PASS."""
    out = dict(observed or {})
    has_audio = _media_has_audio_from_packet(packet)
    if has_audio is not None:
        out["hasAudio"] = has_audio
    if has_audio is False:
        # Distinct from Omni worker unavailable — empty ASR alone still not PASS.
        out["availability"] = "no_audio_track"
        out.setdefault("noAudioTrackReason", "media.hasAudio=False")
    return out

def extract_observed_speech(packet: Any) -> dict[str, Any]:
    """Pull Omni observations. Observation never becomes authority."""
    if packet is None:
        return {"transcript": "", "languageCode": None, "segments": [], "availability": "unavailable"}
    if isinstance(packet, dict):
        segments = packet.get("speechSegments") or []
        extras = packet.get("extras") or {}
        availability = packet.get("availability") or "unavailable"
        lang = (
            extras.get("languageCode")
            or packet.get("languageCode")
            or (packet.get("media") or {}).get("languageCode")
        )
    else:
        segments = list(getattr(packet, "speechSegments", None) or [])
        extras = dict(getattr(packet, "extras", None) or {})
        availability = getattr(packet, "availability", None) or "unavailable"
        media = getattr(packet, "media", None)
        lang = extras.get("languageCode") or getattr(packet, "languageCode", None)
        if lang is None and media is not None:
            lang = getattr(media, "languageCode", None) if not isinstance(media, dict) else media.get("languageCode")
        # Normalize segment objects
        norm_segs = []
        for s in segments:
            if isinstance(s, dict):
                norm_segs.append(s)
            else:
                norm_segs.append(
                    {
                        "transcription": getattr(s, "transcription", "") or "",
                        "speaker": getattr(s, "speaker", None),
                        "startTime": getattr(s, "startTime", None),
                        "endTime": getattr(s, "endTime", None),
                    }
                )
        segments = norm_segs
    parts = []
    for s in segments:
        if isinstance(s, dict):
            t = (s.get("transcription") or "").strip()
            if t:
                parts.append(t)
    transcript = " ".join(parts).strip()
    summary = ""
    if isinstance(packet, dict):
        summary = str(packet.get("summary") or "").strip()
    else:
        summary = str(getattr(packet, "summary", None) or "").strip()
    return {
        "transcript": transcript,
        "languageCode": _norm_lang(lang) if lang else None,
        "segments": segments,
        "summary": summary,
        "availability": availability,
        "role": "observation_only",
    }


def evaluate_dialogue_qc(
    manifest: dict[str, Any],
    observed: dict[str, Any],
    *,
    min_line_coverage: float = 0.55,
    mean_volume_db: float | None = None,
) -> dict[str, Any]:
    """Compare Omni observation to Manifest authority.

    Rules:
      - observed language/text never rewrite the manifest
      - UNCERTAIN != PASS
      - expectedSpeech=NONE (silence locked) + any speech => FAIL SPEECH_WHEN_SILENCE_EXPECTED
      - expectedSpeech=NONE + empty ASR + loud energy => UNCERTAIN MODALITY_CONFLICT (not silence claim, not PASS; energy does not invent speech)
      - expectedSpeech=NONE + confirmed quiet + empty ASR => PASS
      - unexpected speaker not in Manifest speakers => FAIL UNAUTHORIZED_BACKGROUND_SPEAKER
      - unauthorized language (any language != authorized when allowLanguageSwitch=false) => FAIL
      - silent when speech expected => FAIL (quiet/no-stream energy)
      - empty Omni transcript + loud audio energy => OMNI_TRANSCRIPT_MISS / UNCERTAIN (not SILENT)
      - ad-libs when allowAdLibs=false (low coverage / unexpected bulk speech) => FAIL
      - no forbidden-language blacklist — mismatch vs authority is enough
      - detection never invents speech or rewrites Manifest authority
      - creative taste != retake; bad ASR never becomes Manifest authority
    """
    findings: list[dict[str, Any]] = []

    def _finalize_qc(result: dict[str, Any]) -> dict[str, Any]:
        """Attach speechClassification; never rewrite Manifest authority."""
        cls = classify_observed_speech(
            manifest,
            observed,
            verdict=result.get("verdict"),
            mean_volume_db=mean_volume_db,
        )
        # Override classification from hard findings when more specific.
        codes = {f.get("code") for f in (result.get("findings") or [])}
        if CODE_SPEECH_WHEN_SILENCE_EXPECTED in codes:
            cls = CLASS_UNAUTHORIZED_SPEECH
            # Foreign/gibberish under silence upgrades to language artifact when language mismatch/gibberish.
            if _looks_like_gibberish((observed or {}).get("transcript") or "") or (
                _norm_lang((observed or {}).get("languageCode"))
                and _norm_lang((observed or {}).get("languageCode"))
                not in {
                    _norm_lang(x)
                    for x in (manifest.get("authorized_languages") or [])
                    if _norm_lang(x)
                }
                and (manifest.get("authorized_languages") is not None)
            ):
                obs_l = _norm_lang((observed or {}).get("languageCode"))
                auth_l = {
                    _norm_lang(x)
                    for x in (manifest.get("authorized_languages") or [])
                    if _norm_lang(x)
                }
                if _looks_like_gibberish((observed or {}).get("transcript") or "") or (
                    obs_l and auth_l and obs_l not in auth_l
                ) or (obs_l and not auth_l):
                    cls = CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
        if CODE_UNAUTHORIZED_LANGUAGE in codes or "UNAUTHORIZED_LANGUAGE" in codes:
            cls = CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
        if result.get("verdict") == QC_UNCERTAIN:
            cls = CLASS_UNCERTAIN_SPEECH
        if result.get("verdict") == QC_PASS and cls in (
            CLASS_UNAUTHORIZED_SPEECH,
            CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
            CLASS_UNCERTAIN_SPEECH,
        ):
            # PASS only with authorized classifications.
            cls = CLASS_AUTHORIZED_DIALOGUE
        result = dict(result)
        if result.get("reason") in (CODE_OMNI_UNAVAILABLE, "OMNI_UNAVAILABLE") or any(
            isinstance(f, dict) and f.get("code") == CODE_OMNI_UNAVAILABLE
            for f in (result.get("findings") or [])
        ):
            result["infraUnavailable"] = True
            result["retryable"] = True
            result["vcmAdvanceBlocked"] = True
            result["contentFail"] = False
            cls = CLASS_UNCERTAIN_SPEECH
        else:
            result["infraUnavailable"] = False
            result["contentFail"] = cls in (
                CLASS_UNAUTHORIZED_SPEECH,
                CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
                CLASS_UNCERTAIN_SPEECH,
            ) and result.get("verdict") != QC_PASS
            result["vcmAdvanceBlocked"] = result.get("verdict") != QC_PASS
        result["speechClassification"] = cls
        result["languageAuthority"] = {
            "authorized_dialogue_lines": list(manifest.get("authorized_dialogue_lines") or []),
            "authorized_speakers": list(manifest.get("authorized_speakers") or []),
            "authorized_languages": list(manifest.get("authorized_languages") or []),
        }
        # Fail-closed: unauthorized / uncertain-when-silence never CandidateReady.
        if cls in (
            CLASS_UNAUTHORIZED_SPEECH,
            CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
            CLASS_UNCERTAIN_SPEECH,
        ):
            result["sceneFinishedEligible"] = False
            if result.get("verdict") == QC_PASS:
                result["verdict"] = QC_FAIL if cls != CLASS_UNCERTAIN_SPEECH else QC_UNCERTAIN
        return result

    allow_adlibs = bool(manifest.get("allowAdLibs"))
    allow_switch = bool(manifest.get("allowLanguageSwitch"))
    auth_lang = _norm_lang(manifest.get("language"))
    lines = [ln for ln in (manifest.get("lines") or []) if (ln.get("text") or "").strip()]
    expected = resolve_expected_speech(
        lines=lines,
        allow_adlibs=allow_adlibs,
        explicit=manifest.get("expectedSpeech"),
    )
    locked = bool(manifest.get("lockedScript")) or expected in (
        EXPECTED_SPEECH_SPEECH,
        EXPECTED_SPEECH_NONE,
    )

    # Ensure Brad Language Authority fields present for this evaluation.
    if manifest.get("authorized_languages") is None:
        manifest = dict(manifest)
        manifest.update(
            language_authority_fields(
                lines=lines,
                speakers=list(manifest.get("speakers") or []),
                expected=expected,
                manifest_lang=manifest.get("language"),
                allow_adlibs=allow_adlibs,
            )
        )

    availability = (observed or {}).get("availability") or "unavailable"
    transcript = (observed or {}).get("transcript") or ""
    obs_lang = _norm_lang((observed or {}).get("languageCode"))
    # Energy may arrive as explicit kwarg (preferred) or observation sidecar.
    # Observation never invents speech; energy is deterministic corroboration only.
    if mean_volume_db is None and isinstance(observed, dict):
        raw_energy = observed.get("meanVolumeDb")
        if raw_energy is None:
            raw_energy = observed.get("mean_volume_db")
        if raw_energy is not None:
            try:
                mean_volume_db = float(raw_energy)
            except (TypeError, ValueError):
                mean_volume_db = None

    # FAIL-CLOSED SILENCE: empty Dialogue Manifest / OPEN with no lines is silence-locked.
    # Unexpected speech must FAIL (never soft PASS / CandidateReady).
    if expected == EXPECTED_SPEECH_OPEN and not lines:
        expected = EXPECTED_SPEECH_NONE

    # --- Silence-locked path (expectedSpeech=NONE) ---
    if expected == EXPECTED_SPEECH_NONE:
        # Path (b): no audio track + silence-lock = affirmative silence (not Omni infra miss).
        if (
            (observed or {}).get("hasAudio") is False
            or str(availability or "").strip().lower() in ("no_audio_track", "video_only")
        ) and not _has_observed_speech(observed):
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_PASS,
                "gate": GATE_NAME,
                "reason": "NO_AUDIO_TRACK_SILENCE",
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "sceneFinishedEligible": True,
                "meanVolumeDb": mean_volume_db,
                "createdAt": _now(),
            })
        if availability in ("unavailable", "error", None) or availability == "unavailable":
            findings.append(
                {
                    "code": "OMNI_UNAVAILABLE",
                    "severity": "error",
                    "message": "Omni observation unavailable — cannot verify silence; UNCERTAIN != PASS",
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        note="UNCERTAIN: not PASS, not auto-destroy",
                    ),
                }
            )
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_UNCERTAIN,
                "gate": GATE_NAME,
                "reason": "OMNI_UNAVAILABLE",
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "sceneFinishedEligible": False,
                "createdAt": _now(),
            })
        if _has_observed_speech(observed):
            findings.append(
                {
                    "code": CODE_SPEECH_WHEN_SILENCE_EXPECTED,
                    "severity": "error",
                    "message": (
                        "expectedSpeech=NONE (silence locked); Omni observed unauthorized speech "
                        "— FAIL; creative taste != retake; ASR is not authority"
                    ),
                    "finalCheck": _final_check_hints(
                        retake_eligible=True,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        creative_taste=False,
                        note="Hard unauthorized speech when silence expected — auto Re-Take eligible",
                    ),
                }
            )
            # Also flag unexpected speakers when labels present.
            auth_speakers = _authorized_speaker_keys(manifest)
            for label in _observed_speaker_labels(observed):
                if label.strip().lower() not in auth_speakers:
                    findings.append(
                        {
                            "code": CODE_UNAUTHORIZED_BACKGROUND_SPEAKER,
                            "severity": "error",
                            "observedSpeaker": label,
                            "authorizedSpeakers": sorted(auth_speakers),
                            "message": (
                                "Background / unexpected speaker not in Manifest speakers "
                                "(silence-locked scene)"
                            ),
                            "finalCheck": _final_check_hints(
                                retake_eligible=True,
                                auto_destroy=False,
                                acceptance_eligible=False,
                                creative_taste=False,
                                note="Hard speaker-authority violation — auto Re-Take eligible",
                            ),
                        }
                    )
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_FAIL,
                "gate": GATE_NAME,
                "reason": CODE_SPEECH_WHEN_SILENCE_EXPECTED,
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "meanVolumeDb": mean_volume_db,
                "sceneFinishedEligible": False,
                "createdAt": _now(),
            })
        # Empty ASR under silence lock: energy corroboration is a *different* modality.
        # PRIMARY LAW: absence of ASR evidence is NOT evidence of absence when energy
        # contradicts it. Loud + empty => UNCERTAIN / modality conflict (not PASS, not
        # inventing speech). Confirmed quiet + empty => true silence PASS.
        if audio_energy_is_loud(mean_volume_db):
            conflict_reason = (
                "expectedSpeech=NONE; empty ASR but loud audio energy — modality conflict; "
                "do not claim silence; do not invent speech; UNCERTAIN != PASS"
            )
            findings.append(
                {
                    "code": CODE_OMNI_TRANSCRIPT_MISS,
                    "severity": "error",
                    "meanVolumeDb": mean_volume_db,
                    "loudThresholdDb": LOUD_MEAN_VOLUME_DB,
                    "message": conflict_reason,
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        creative_taste=False,
                        modality_conflict=True,
                        modalities=["asr", "energy"],
                        conflict_reason=conflict_reason,
                        note=(
                            "UNCERTAIN/OMNI_TRANSCRIPT_MISS modality conflict: not PASS, "
                            "not auto-destroy; energy alone does not invent speech; "
                            "do not promote ASR"
                        ),
                    ),
                }
            )
            findings.append(
                {
                    "code": CODE_MODALITY_CONFLICT,
                    "severity": "error",
                    "meanVolumeDb": mean_volume_db,
                    "message": conflict_reason,
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        creative_taste=False,
                        modality_conflict=True,
                        modalities=["asr", "energy"],
                        conflict_reason=conflict_reason,
                        note="MODALITY_CONFLICT for Final Check — not silence claim, not PASS",
                    ),
                }
            )
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_UNCERTAIN,
                "gate": GATE_NAME,
                "reason": CODE_MODALITY_CONFLICT,
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "meanVolumeDb": mean_volume_db,
                "sceneFinishedEligible": False,
                "createdAt": _now(),
            })
        # FAIL-CLOSED: empty ASR is NOT proof of silence. Require positive silence evidence
        # or else UNCERTAIN (blocks CandidateReady). P6 v3 gate-slip fix.
        if not _has_positive_silence_evidence(observed, mean_volume_db):
            findings.append(
                {
                    "code": CODE_OMNI_TRANSCRIPT_MISS,
                    "severity": "error",
                    "meanVolumeDb": mean_volume_db,
                    "quietThresholdDb": QUIET_MEAN_VOLUME_DB,
                    "message": (
                        "expectedSpeech=NONE; empty ASR without affirmative silence evidence "
                        "(segments/summary/quiet energy) — UNCERTAIN != PASS; do not CandidateReady"
                    ),
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        note="UNCERTAIN: empty ASR alone cannot clear silence lock",
                    ),
                }
            )
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_UNCERTAIN,
                "gate": GATE_NAME,
                "reason": CODE_OMNI_TRANSCRIPT_MISS,
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "meanVolumeDb": mean_volume_db,
                "sceneFinishedEligible": False,
                "createdAt": _now(),
            })
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_PASS,
            "gate": GATE_NAME,
            "reason": "OK",
            "expectedSpeech": expected,
            "findings": [],
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "meanVolumeDb": mean_volume_db,
            "sceneFinishedEligible": True,
            "createdAt": _now(),
        })


    # --- Speech-required path (expectedSpeech=SPEECH / locked lines) ---
    if not locked or not lines:
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_PASS,
            "gate": GATE_NAME,
            "reason": "no_locked_script_lines",
            "expectedSpeech": expected,
            "findings": [],
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "sceneFinishedEligible": True,
            "createdAt": _now(),
        })

    if not manifest.get("authorityExplicit") or not auth_lang:
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_FAIL,
            "gate": GATE_NAME,
            "reason": "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
            "expectedSpeech": expected,
            "findings": [{
                "code": "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
                "severity": "error",
                "finalCheck": _final_check_hints(
                    retake_eligible=True,
                    auto_destroy=False,
                    acceptance_eligible=False,
                    note="Hard authority gap — auto Re-Take / block eligible",
                ),
            }],
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "sceneFinishedEligible": False,
            "createdAt": _now(),
        })

    if availability in ("unavailable", "error", None) or availability == "unavailable":
        findings.append(
            {
                "code": "OMNI_UNAVAILABLE",
                "severity": "error",
                "message": "Omni observation unavailable — UNCERTAIN != PASS",
                "finalCheck": _final_check_hints(
                    retake_eligible=False,
                    auto_destroy=False,
                    acceptance_eligible=False,
                    note="UNCERTAIN: not PASS, not auto-destroy",
                ),
            }
        )
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "gate": GATE_NAME,
            "reason": "OMNI_UNAVAILABLE",
            "expectedSpeech": expected,
            "findings": findings,
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "sceneFinishedEligible": False,
            "createdAt": _now(),
        })

    if not transcript.strip():
        # False-silent guard: loud energy + empty Omni transcript is a miss, not silence.
        if audio_energy_is_loud(mean_volume_db):
            findings.append(
                {
                    "code": CODE_OMNI_TRANSCRIPT_MISS,
                    "severity": "error",
                    "meanVolumeDb": mean_volume_db,
                    "loudThresholdDb": LOUD_MEAN_VOLUME_DB,
                    "message": (
                        "Locked script expects speech; Omni transcript empty but audio energy "
                        "is loud (mean_volume corroboration) — UNCERTAIN != PASS; not SILENT"
                    ),
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        creative_taste=False,
                        modality_conflict=True,
                        modalities=["asr", "energy"],
                        conflict_reason=(
                            "empty ASR + loud energy — modality conflict; "
                            "not silence; energy alone does not invent speech"
                        ),
                        note="UNCERTAIN/OMNI_TRANSCRIPT_MISS: not PASS, not auto-destroy; do not promote ASR",
                    ),
                }
            )
            return _finalize_qc({
                "kind": DIALOGUE_QC_KIND,
                "verdict": QC_UNCERTAIN,
                "gate": GATE_NAME,
                "reason": CODE_OMNI_TRANSCRIPT_MISS,
                "expectedSpeech": expected,
                "findings": findings,
                "observed": observed,
                "manifestId": manifest.get("manifestId"),
                "meanVolumeDb": mean_volume_db,
                "sceneFinishedEligible": False,
                "createdAt": _now(),
            })
        findings.append(
            {
                "code": CODE_SILENT_WHEN_SPEECH_EXPECTED,
                "severity": "error",
                "meanVolumeDb": mean_volume_db,
                "message": "Locked script expects speech; Omni heard silence / empty transcript",
                "finalCheck": _final_check_hints(
                    retake_eligible=True,
                    auto_destroy=False,
                    acceptance_eligible=False,
                    note="Hard missing-required speech vs Manifest — auto Re-Take eligible",
                ),
            }
        )
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_FAIL,
            "gate": GATE_NAME,
            "reason": CODE_SILENT_WHEN_SPEECH_EXPECTED,
            "expectedSpeech": expected,
            "findings": findings,
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "meanVolumeDb": mean_volume_db,
            "sceneFinishedEligible": False,
            "createdAt": _now(),
        })

    # Language match (no blacklist): if Omni reports a language and switch disallowed,
    # any mismatch vs authorized language fails — covers Welsh/Latin/etc. universally.
    if not allow_switch and obs_lang and auth_lang:
        obs_primary = obs_lang.split("-")[0].lower()
        auth_primary = auth_lang.split("-")[0].lower()
        if obs_primary != auth_primary and obs_primary not in ("und", "unknown", "none"):
            findings.append(
                {
                    "code": "UNAUTHORIZED_LANGUAGE",
                    "severity": "error",
                    "authorized": auth_lang,
                    "observed": obs_lang,
                    "message": "Observed spoken language != authorized language (allowLanguageSwitch=false)",
                    "finalCheck": _final_check_hints(
                        retake_eligible=True,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        note="Hard language-authority violation — auto Re-Take eligible; ASR is not authority",
                    ),
                }
            )

    # Unauthorized background / unexpected speakers (Hard — retakeEligible).
    auth_speakers = _authorized_speaker_keys(manifest)
    if auth_speakers:
        for label in _observed_speaker_labels(observed):
            if label.strip().lower() not in auth_speakers:
                findings.append(
                    {
                        "code": CODE_UNAUTHORIZED_BACKGROUND_SPEAKER,
                        "severity": "error",
                        "observedSpeaker": label,
                        "authorizedSpeakers": sorted(auth_speakers),
                        "message": (
                            "Background / unexpected speaker not in Manifest speakers "
                            "(Hard speaker-authority violation)"
                        ),
                        "finalCheck": _final_check_hints(
                            retake_eligible=True,
                            auto_destroy=False,
                            acceptance_eligible=False,
                            creative_taste=False,
                            note="Hard speaker-authority violation — auto Re-Take eligible; ASR is not authority",
                        ),
                    }
                )

    # Wrong speaker: an authorized Manifest speaker delivered another speaker's line.
    # Observation only — never rewrite Manifest from ASR. Weak coverage is ignored
    # (bad ASR must not invent a WRONG_SPEAKER bind).
    if auth_speakers and lines:
        for seg in (observed or {}).get("segments") or []:
            if not isinstance(seg, dict):
                continue
            seg_text = (seg.get("transcription") or seg.get("text") or "").strip()
            seg_speaker = seg.get("speaker") or seg.get("speakerName") or seg.get("speakerId")
            if not seg_text or seg_speaker is None:
                continue
            speaker_key = str(seg_speaker).strip().lower()
            if not speaker_key or speaker_key not in auth_speakers:
                continue
            best = None
            best_cov = 0.0
            tie = False
            for ln in lines:
                cov = _line_coverage(ln.get("text") or "", seg_text)
                if cov > best_cov:
                    best_cov = cov
                    best = ln
                    tie = False
                elif cov == best_cov and best is not None and cov > 0:
                    other = str(ln.get("speakerName") or ln.get("speakerId") or "").strip().lower()
                    cur = str(best.get("speakerName") or best.get("speakerId") or "").strip().lower()
                    if other and cur and other != cur:
                        tie = True
            if tie or best is None or best_cov < min_line_coverage:
                continue
            expected_key = str(best.get("speakerName") or best.get("speakerId") or "").strip().lower()
            if expected_key and speaker_key != expected_key:
                findings.append(
                    {
                        "code": CODE_WRONG_SPEAKER,
                        "severity": "error",
                        "observedSpeaker": str(seg_speaker).strip(),
                        "expectedSpeaker": best.get("speakerName") or best.get("speakerId"),
                        "lineId": best.get("lineId"),
                        "expected": best.get("text"),
                        "coverage": round(best_cov, 3),
                        "message": (
                            "Authorized speaker delivered another Manifest speaker's exact line "
                            "(Hard speaker-authority violation)"
                        ),
                        "finalCheck": _final_check_hints(
                            retake_eligible=True,
                            auto_destroy=False,
                            acceptance_eligible=False,
                            creative_taste=False,
                            note="Hard WRONG_SPEAKER — auto Re-Take eligible; ASR is not authority",
                        ),
                    }
                )

    # Line fidelity
    coverages = []
    for ln in lines:
        cov = _line_coverage(ln.get("text") or "", transcript)
        coverages.append(cov)
        if cov < min_line_coverage:
            findings.append(
                {
                    "code": "LINE_FIDELITY_FAIL",
                    "severity": "error",
                    "lineId": ln.get("lineId"),
                    "speakerName": ln.get("speakerName"),
                    "expected": ln.get("text"),
                    "coverage": round(cov, 3),
                    "minCoverage": min_line_coverage,
                    "finalCheck": _final_check_hints(
                        retake_eligible=True,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        note="Hard Manifest line miss — auto Re-Take eligible; do not rewrite Manifest from ASR",
                    ),
                }
            )

    mean_cov = sum(coverages) / max(1, len(coverages))
    if not allow_adlibs and mean_cov < min_line_coverage:
        findings.append(
            {
                "code": "ADLIB_OR_NONLITERAL",
                "severity": "error",
                "meanCoverage": round(mean_cov, 3),
                "message": "allowAdLibs=false — observed speech diverges from manifest",
                "finalCheck": _final_check_hints(
                    retake_eligible=True,
                    auto_destroy=False,
                    acceptance_eligible=False,
                    note="Hard invented/nonliteral when adlibs off — auto Re-Take eligible",
                ),
            }
        )

    if findings:
        verdict = QC_FAIL
        eligible = False
    else:
        verdict = QC_PASS
        eligible = True

    # If language was unknown/und but fidelity passed, still UNCERTAIN on language when switch disallowed
    if verdict == QC_PASS and not allow_switch and not obs_lang:
        return _finalize_qc({
            "kind": DIALOGUE_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "gate": GATE_NAME,
            "reason": "OBSERVED_LANGUAGE_UNKNOWN",
            "expectedSpeech": expected,
            "findings": [
                {
                    "code": "OBSERVED_LANGUAGE_UNKNOWN",
                    "severity": "error",
                    "message": "Omni did not report languageCode — UNCERTAIN != PASS",
                    "finalCheck": _final_check_hints(
                        retake_eligible=False,
                        auto_destroy=False,
                        acceptance_eligible=False,
                        note="UNCERTAIN: not PASS, not auto-destroy",
                    ),
                }
            ],
            "observed": observed,
            "manifestId": manifest.get("manifestId"),
            "meanCoverage": round(mean_cov, 3),
            "sceneFinishedEligible": False,
            "createdAt": _now(),
        })

    return _finalize_qc({
        "kind": DIALOGUE_QC_KIND,
        "verdict": verdict,
        "gate": GATE_NAME,
        "reason": "OK" if eligible else (findings[0]["code"] if findings else "FAIL"),
        "expectedSpeech": expected,
        "findings": findings,
        "observed": observed,
        "manifestId": manifest.get("manifestId"),
        "authorizedLanguage": auth_lang,
        "meanCoverage": round(mean_cov, 3),
        "sceneFinishedEligible": eligible,
        "createdAt": _now(),
    })



def ensure_silence_locked_manifest(
    *,
    project_id: str,
    scene_id: str,
    batch_id: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed silence Manifest when dialogue authority is empty.

    Empty lines + no ad-libs => expectedSpeech=NONE, lockedScript=True.
    """
    if manifest is None:
        manifest = build_dialogue_manifest(
            project_id=project_id,
            scene_id=scene_id,
            batch_id=batch_id,
            allow_adlibs=False,
            expected_speech=EXPECTED_SPEECH_NONE,
        )
    lines = [ln for ln in (manifest.get("lines") or []) if (ln.get("text") or "").strip()]
    if not lines:
        out = dict(manifest)
        out["expectedSpeech"] = EXPECTED_SPEECH_NONE
        out["lockedScript"] = True
        out["allowAdLibs"] = False
        out["lines"] = []
        out["authorized_dialogue_lines"] = []
        out["authorized_speakers"] = []
        out["authorized_languages"] = []
        out["speakers"] = []
        return out
    # Keep Brad Language Authority fields in sync with lines.
    out = dict(manifest)
    out.update(
        language_authority_fields(
            lines=lines,
            speakers=list(manifest.get("speakers") or []),
            expected=manifest.get("expectedSpeech"),
            manifest_lang=manifest.get("language"),
            allow_adlibs=bool(manifest.get("allowAdLibs")),
        )
    )
    return out

def run_omni_dialogue_qc(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    manifest: dict[str, Any],
    force: bool = True,
    batch: Any = None,
) -> dict[str, Any]:
    """Invoke Adept Omni transcribe and evaluate against Manifest.

    Merges media-intel / continuity summaries already on the batch so a thin
    transcribe packet cannot PASS silence-lock while another Omni pass heard speech.

    Chief path (b): silence_locked + generate_audio=false + audio_streams=0 ⇒
    affirmative silence WITHOUT Omni ASR/energy. audio_streams>0 ⇒ full Omni QC.
    """
    observed: dict[str, Any]
    mean_volume_db: float | None = None
    asset_path = None
    try:
        from app.director_timeline_w46.scene_stitch import resolve_asset_file

        asset_path = resolve_asset_file(db, project_id, asset_id)
    except Exception:
        asset_path = None

    audio_streams = count_audio_streams(asset_path) if asset_path else None
    if is_no_audio_generation_path(
        manifest=manifest,
        batch=batch,
        asset_path=asset_path,
        audio_stream_count=audio_streams,
    ):
        observed = {
            "transcript": "",
            "languageCode": None,
            "segments": [],
            "summary": "",
            "availability": "no_audio_track",
            "hasAudio": False,
            "audioStreamCount": 0,
            "generateAudio": False,
            "pathB": True,
            "role": "observation_only",
            "noAudioTrackReason": "silence_locked+generate_audio=false+audio_streams=0",
        }
        return evaluate_dialogue_qc(manifest, observed, mean_volume_db=None)

    try:
        from app.codirector.video_intelligence.media_analyze import analyze_asset

        packet = analyze_asset(
            db,
            project_id,
            asset_id,
            mode="transcribe",
            scene_id=scene_id,
            force=force,
            persist=True,
            timeout_sec=180.0,
        )
        observed = annotate_observed_media_audio(extract_observed_speech(packet), packet)
        if audio_streams is not None:
            observed["audioStreamCount"] = audio_streams
    except Exception as exc:  # noqa: BLE001
        observed = {
            "transcript": "",
            "languageCode": None,
            "segments": [],
            "summary": "",
            "availability": "unavailable",
            "error": str(exc),
            "role": "observation_only",
        }
        if audio_streams is not None:
            observed["audioStreamCount"] = audio_streams

    # Merge speech cues from other Omni packets already on this batch (continuity / MI).
    if batch is not None:
        extras: list[str] = []
        for r in getattr(batch, "references", None) or []:
            if not isinstance(r, dict):
                continue
            kind = str(r.get("kind") or "")
            if kind not in (
                "omniContinuityDiagnostics",
                "continuityQcDiagnostics",
                "mediaIntelligence",
                "mediaIntelligencePacket",
            ) and "omni" not in kind.lower() and "media" not in kind.lower():
                # Still accept nested observed/summary on any diagnostics ref.
                pass
            for blob in (r, r.get("observed") if isinstance(r.get("observed"), dict) else None):
                if not isinstance(blob, dict):
                    continue
                sm = str(blob.get("summary") or "").strip()
                if sm:
                    extras.append(sm)
                for seg in blob.get("speechSegments") or blob.get("segments") or []:
                    if isinstance(seg, dict):
                        observed.setdefault("segments", []).append(seg)
        if extras:
            merged = " | ".join(extras)
            prior = str(observed.get("summary") or "").strip()
            observed["summary"] = (prior + " | " + merged).strip(" |") if prior else merged

    # Deterministic energy corroboration (never invents speech / never rewrites Manifest).
    mean_volume_db: float | None = None
    try:
        from app.director_timeline_w46.scene_stitch import resolve_asset_file

        asset_path = resolve_asset_file(db, project_id, asset_id)
        if asset_path is not None:
            mean_volume_db = probe_mean_volume_db(asset_path)
    except Exception:
        mean_volume_db = None

    return evaluate_dialogue_qc(manifest, observed, mean_volume_db=mean_volume_db)


def resume_dialogue_qc_against_existing_asset(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    batch: Any,
    master: Any = None,
    force: bool = True,
) -> dict[str, Any]:
    """P0 master-stability support: QC-only retry against an existing asset.

    - Uses frozen languageAuthorityPacket (no recompile drift).
    - If packet missing, freezes silence-lock authority from current/empty Manifest.
    - Never regenerates media. Asset preserve is Gen-owned; this only re-runs Omni QC.
    - OMNI_UNAVAILABLE → QC_RetryRequired (not NeedsDialogueRetake).
    - VCM remains blocked until Omni PASS + sceneFinishedEligible.
    """
    if not (asset_id or "").strip():
        raise ValueError("EXISTING_ASSET_ID_REQUIRED")

    frozen = get_frozen_authority_packet(batch)
    manifest = get_manifest_from_batch(batch)
    if manifest is None:
        manifest = ensure_silence_locked_manifest(
            project_id=project_id,
            scene_id=scene_id,
            batch_id=str(getattr(batch, "id", "") or "") or None,
            manifest=None,
        )
        attach_manifest_to_batch(batch, manifest)
    else:
        manifest = ensure_silence_locked_manifest(
            project_id=project_id,
            scene_id=scene_id,
            batch_id=str(getattr(batch, "id", "") or "") or None,
            manifest=manifest,
        )

    if frozen is None:
        # Prefer Brad silence fields when expectedSpeech=NONE.
        expected = resolve_expected_speech(
            lines=manifest.get("lines") or [],
            allow_adlibs=bool(manifest.get("allowAdLibs")),
            explicit=manifest.get("expectedSpeech"),
        )
        if expected == EXPECTED_SPEECH_NONE:
            manifest["authorized_dialogue_lines"] = []
            manifest["authorized_speakers"] = []
            manifest["authorized_languages"] = []
            manifest["lines"] = []
            manifest["speakers"] = []
        frozen = freeze_language_authority_packet(manifest)
        attach_authority_packet(batch, frozen)
    else:
        manifest = manifest_from_frozen_packet(frozen, fallback=manifest)
        attach_manifest_to_batch(batch, manifest)

    qc = run_omni_dialogue_qc(
        db,
        project_id=project_id,
        scene_id=scene_id,
        asset_id=asset_id,
        manifest=manifest,
        force=force,
        batch=batch,
    )
    status = apply_qc_to_batch_status(batch, qc)
    # Content fail + scripted lines → retake repair. Infra → no retake payload.
    if (
        status == STATUS_NEEDS_DIALOGUE_RETAKE
        and (manifest.get("lines") or [])
        and not is_omni_infra_unavailable(qc)
    ):
        repair = build_retake_repair_from_manifest(manifest, qc)
        refs = [
            r
            for r in (getattr(batch, "references", None) or [])
            if not (isinstance(r, dict) and r.get("kind") == "dialogueRetakeRepair")
        ]
        refs.append(repair)
        batch.references = refs

    return {
        "ok": True,
        "assetPreserved": True,
        "regenerated": False,
        "assetId": asset_id,
        "status": status,
        "qc": qc,
        "frozenAuthority": frozen,
        "vcmAdvanceBlocked": dialogue_qc_blocks_vcm_advance(batch, qc),
        "infraUnavailable": bool(qc.get("infraUnavailable")),
        "contentFail": bool(qc.get("contentFail")),
    }



def persist_qc_diagnostics(batch: Any, qc: dict[str, Any]) -> None:
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") == DIALOGUE_QC_KIND)
    ]
    refs.append(qc)
    batch.references = refs


# ---------------------------------------------------------------------------
# G/H — SCENE_FINISHED gate + Re-Take repair from Manifest
# ---------------------------------------------------------------------------

def is_scene_finished_eligible(batch: Any, qc: dict[str, Any] | None = None) -> bool:
    """RENDER != FINISHED. CandidateReady only when QC says eligible."""
    if qc is None:
        # Look up persisted diagnostics
        for r in getattr(batch, "references", None) or []:
            if isinstance(r, dict) and r.get("kind") == DIALOGUE_QC_KIND:
                qc = r
                break
    if qc is None:
        manifest = get_manifest_from_batch(batch)
        if manifest and manifest.get("lockedScript"):
            expected = resolve_expected_speech(
                lines=manifest.get("lines") or [],
                allow_adlibs=bool(manifest.get("allowAdLibs")),
                explicit=manifest.get("expectedSpeech"),
            )
            # Speech-locked or silence-locked without QC => not finished.
            if manifest.get("lines") or expected == EXPECTED_SPEECH_NONE:
                return False
        return True
    return bool(qc.get("sceneFinishedEligible")) and qc.get("verdict") == QC_PASS



def is_omni_infra_unavailable(qc: dict[str, Any] | None) -> bool:
    """True when QC failed because Omni worker/timeout/request — not content."""
    if not isinstance(qc, dict):
        return False
    if qc.get("infraUnavailable") is True:
        return True
    reason = str(qc.get("reason") or "")
    if reason in (CODE_OMNI_UNAVAILABLE, "OMNI_UNAVAILABLE", "DIALOGUE_QC_EXCEPTION"):
        # Exception path may still be infra; content fails use SPEECH_WHEN_SILENCE etc.
        if reason == "DIALOGUE_QC_EXCEPTION":
            err = str(qc.get("error") or "").lower()
            return any(k in err for k in ("timeout", "unavailable", "connection", "worker", "503", "502", "504", "request"))
        return True
    findings = qc.get("findings") or []
    return any(isinstance(f, dict) and f.get("code") == CODE_OMNI_UNAVAILABLE for f in findings)


def is_content_speech_fail(qc: dict[str, Any] | None) -> bool:
    """Unauthorized speech/lang/uncertain-when-silence — NeedsDialogueRetake path."""
    if not isinstance(qc, dict):
        return False
    if is_omni_infra_unavailable(qc):
        return False
    cls = qc.get("speechClassification")
    if cls in (
        CLASS_UNAUTHORIZED_SPEECH,
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNCERTAIN_SPEECH,
    ):
        return True
    reason = str(qc.get("reason") or "")
    return reason in (
        CODE_SPEECH_WHEN_SILENCE_EXPECTED,
        "UNAUTHORIZED_LANGUAGE",
        CODE_OMNI_TRANSCRIPT_MISS,
        CODE_MODALITY_CONFLICT,
    ) or qc.get("verdict") in (QC_FAIL, QC_UNCERTAIN)


def freeze_language_authority_packet(manifest: dict[str, Any]) -> dict[str, Any]:
    """Frozen per-window authority for QC retry — no recompile drift."""
    auth = language_authority_fields(
        lines=manifest.get("lines") or [],
        speakers=list(manifest.get("speakers") or []),
        expected=manifest.get("expectedSpeech"),
        manifest_lang=manifest.get("language"),
        allow_adlibs=bool(manifest.get("allowAdLibs")),
    )
    # Prefer already-emitted Brad fields when present.
    lines = list(manifest.get("authorized_dialogue_lines") or auth["authorized_dialogue_lines"])
    speakers = list(manifest.get("authorized_speakers") or auth["authorized_speakers"])
    languages = list(manifest.get("authorized_languages") or auth["authorized_languages"])
    return {
        "kind": AUTHORITY_PACKET_KIND,
        "schemaVersion": "language-authority-packet-v1",
        "manifestId": manifest.get("manifestId"),
        "expectedSpeech": manifest.get("expectedSpeech"),
        "lockedScript": bool(manifest.get("lockedScript")),
        "allowAdLibs": bool(manifest.get("allowAdLibs")),
        "allowLanguageSwitch": bool(manifest.get("allowLanguageSwitch")),
        "language": manifest.get("language"),
        "authorized_dialogue_lines": lines,
        "authorized_speakers": speakers,
        "authorized_languages": languages,
        "lines": list(manifest.get("lines") or []),
        "speakers": list(manifest.get("speakers") or []),
        "frozenAt": _now(),
        "notes": "Frozen at first QC. Retry must use this packet — no recompile drift.",
    }


def attach_authority_packet(batch: Any, packet: dict[str, Any]) -> None:
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") == AUTHORITY_PACKET_KIND)
    ]
    refs.append(packet)
    batch.references = refs


def get_frozen_authority_packet(batch: Any) -> dict[str, Any] | None:
    for r in getattr(batch, "references", None) or []:
        if isinstance(r, dict) and r.get("kind") == AUTHORITY_PACKET_KIND:
            return r
    return None


def manifest_from_frozen_packet(packet: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rebuild Manifest-shaped authority from frozen packet (no scene recompile)."""
    base = dict(fallback or {})
    base.update(
        {
            "kind": DIALOGUE_MANIFEST_KIND,
            "manifestId": packet.get("manifestId") or base.get("manifestId") or _nid("manif_"),
            "expectedSpeech": packet.get("expectedSpeech"),
            "lockedScript": bool(packet.get("lockedScript")),
            "allowAdLibs": bool(packet.get("allowAdLibs")),
            "allowLanguageSwitch": bool(packet.get("allowLanguageSwitch")),
            "language": packet.get("language"),
            "lines": list(packet.get("lines") or []),
            "speakers": list(packet.get("speakers") or packet.get("authorized_speakers") or []),
            "authorized_dialogue_lines": list(packet.get("authorized_dialogue_lines") or []),
            "authorized_speakers": list(packet.get("authorized_speakers") or []),
            "authorized_languages": list(packet.get("authorized_languages") or []),
            "authorityPacketFrozen": True,
        }
    )
    return base


def dialogue_qc_blocks_vcm_advance(batch: Any = None, qc: dict[str, Any] | None = None) -> bool:
    """While W(N) QC pending/retry-required, halt VCM + refinement to W(N+1)."""
    if qc is None and batch is not None:
        for r in getattr(batch, "references", None) or []:
            if isinstance(r, dict) and r.get("kind") == DIALOGUE_QC_KIND:
                qc = r
                break
    status = getattr(batch, "status", None) if batch is not None else None
    if status in (STATUS_QC_PENDING, STATUS_QC_RETRY_REQUIRED, "QC_Pending", "QC_RetryRequired"):
        return True
    if is_omni_infra_unavailable(qc):
        return True
    if isinstance(qc, dict):
        # VCM must not advance without successful Omni (PASS + eligible).
        if qc.get("verdict") != QC_PASS or qc.get("sceneFinishedEligible") is False:
            return True
        if qc.get("infraUnavailable") is True:
            return True
    if status == STATUS_NEEDS_DIALOGUE_RETAKE:
        return True
    return False



def apply_qc_to_batch_status(batch: Any, qc: dict[str, Any]) -> str:
    """Mutate batch status from QC. Returns new status.

    CONTENT FAIL (unauthorized speech/lang/uncertain-when-silence) → NeedsDialogueRetake.
    INFRA UNAVAILABLE (Omni timeout/worker/transient) → QC_Pending / QC_RetryRequired.
    Never masquerade OMNI_UNAVAILABLE as NeedsDialogueRetake. Keep asset; retry QC only.
    """
    persist_qc_diagnostics(batch, qc)
    if qc.get("sceneFinishedEligible") and qc.get("verdict") == QC_PASS:
        batch.status = "CandidateReady"
        return "CandidateReady"
    if is_omni_infra_unavailable(qc):
        # Media success + retryable Omni miss — do not retake; do not CandidateReady.
        batch.status = STATUS_QC_RETRY_REQUIRED
        return STATUS_QC_RETRY_REQUIRED
    # Content speech/language fail — retake path.
    batch.status = STATUS_NEEDS_DIALOGUE_RETAKE
    return STATUS_NEEDS_DIALOGUE_RETAKE


def build_retake_repair_from_manifest(
    manifest: dict[str, Any],
    qc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Smallest Timeline R2V Re-Take repair payload — Manifest is authority, not bad ASR."""
    lines = manifest.get("lines") or []
    script_lines = []
    for ln in lines:
        if not (ln.get("text") or "").strip():
            continue
        script_lines.append(
            {
                "speakerId": ln.get("speakerId"),
                "speakerName": ln.get("speakerName"),
                "text": ln.get("text"),
                "language": ln.get("language") or manifest.get("language"),
            }
        )
    delta_parts = []
    for sl in script_lines:
        name = sl.get("speakerName") or sl.get("speakerId") or "Speaker"
        delta_parts.append(f'{name} says:\n"{sl["text"]}"')
    user_delta = "\n\n".join(delta_parts)
    return {
        "kind": "dialogueRetakeRepair",
        "source": "dialogue_manifest",
        "manifestId": manifest.get("manifestId"),
        "language": manifest.get("language"),
        "allowAdLibs": False,
        "allowLanguageSwitch": False,
        "exactScriptDialogue": True,
        "keepTimelineR2V": True,
        "reviveLipSync": False,
        "userCorrection": {
            "text": (
                f"DIALOGUE AUTHORITY RE-TAKE — speak ONLY the authorized {manifest.get('language')} script. "
                f"No ad-libs. No language switch.\n\n{user_delta}"
            ),
            "source": "dialogue_manifest",
            "language": manifest.get("language"),
        },
        "scriptLines": script_lines,
        "qcReason": (qc or {}).get("reason"),
        "reVerifyOmni": True,
        "blacklist": None,
        "createdAt": _now(),
    }


# ---------------------------------------------------------------------------
# Orchestration helpers — ensure authority + compile for a batch
# ---------------------------------------------------------------------------


def batch_has_locked_script_lines(batch: Any, manifest: dict[str, Any] | None = None) -> bool:
    """True when this batch is locked script (speech or silence) via Manifest or speech windows."""
    def _manifest_locked(m: dict[str, Any] | None) -> bool:
        if not m or not m.get("lockedScript"):
            return False
        if m.get("lines"):
            return True
        expected = resolve_expected_speech(
            lines=m.get("lines") or [],
            allow_adlibs=bool(m.get("allowAdLibs")),
            explicit=m.get("expectedSpeech"),
        )
        return expected == EXPECTED_SPEECH_NONE

    if _manifest_locked(manifest):
        return True
    if batch is None:
        return False
    existing = None
    try:
        existing = get_manifest_from_batch(batch)
    except Exception:
        existing = None
    if _manifest_locked(existing):
        return True
    windows = list(getattr(batch, "speechWindows", None) or [])
    for w in windows:
        if not isinstance(w, dict):
            continue
        if str(w.get("text") or "").strip():
            return True
        for sp in w.get("speakers") or []:
            if isinstance(sp, dict) and str(sp.get("text") or "").strip():
                return True
    return False


def submit_dialogue_authority_preflight(
    manifest: dict[str, Any] | None,
    *,
    compile_error: BaseException | None = None,
    batch: Any = None,
) -> dict[str, Any] | None:
    """Return an in-band error dict to fail closed, or None to continue submit.

    SPOKEN_LANGUAGE_AUTHORITY_MISSING is returned honestly — never swallowed by
    except Exception: pass. Unexpected compile/read errors fail closed when the
    batch is locked script.
    """
    if compile_error is not None:
        if batch_has_locked_script_lines(batch, manifest):
            return {
                "ok": False,
                "error": "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
                "message": (
                    "Scripted dialogue requires explicit spoken language authority "
                    "(line -> scene -> project). UI locale is not spoken authority. "
                    f"(preflight failed: {compile_error})"
                ),
                "dialogueManifest": manifest,
                "mock": False,
            }
        return {
            "ok": False,
            "error": "DIALOGUE_AUTHORITY_PREFLIGHT_FAILED",
            "message": str(compile_error),
            "mock": False,
        }
    if (
        manifest
        and manifest.get("lockedScript")
        and manifest.get("lines")
        and not manifest.get("authorityExplicit")
    ):
        return {
            "ok": False,
            "error": "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
            "message": (
                "Scripted dialogue requires explicit spoken language authority "
                "(line -> scene -> project). UI locale is not spoken authority."
            ),
            "dialogueManifest": manifest,
            "mock": False,
        }
    # Fail-closed A: missing manifest when batch expects locked script dialogue.
    if manifest is None and batch_has_locked_script_lines(batch, None):
        return {
            "ok": False,
            "error": "DIALOGUE_MANIFEST_MISSING",
            "message": (
                "Generate blocked: locked-script batch has no Dialogue Manifest. "
                "Compile dialogue authority before submit."
            ),
            "mock": False,
        }
    # Fail-closed B: stale / needs recompile still present after compile attempt.
    if manifest_needs_authority_recompile(manifest):
        return {
            "ok": False,
            "error": "DIALOGUE_MANIFEST_STALE",
            "message": (
                "Generate blocked: Dialogue Manifest is stale "
                "(locked script without explicit spoken-language authority)."
            ),
            "dialogueManifest": manifest,
            "mock": False,
        }
    return None


def apply_qc_exception_fail_closed(
    batch: Any,
    exc: BaseException,
    *,
    manifest: dict[str, Any] | None = None,
) -> str:
    """Omni/QC exception → QC_RetryRequired (infra). Never CandidateReady when silence/locked.

    OMNI_UNAVAILABLE must NOT masquerade as NeedsDialogueRetake.
    """
    locked = batch_has_locked_script_lines(batch, manifest)
    expected = None
    if isinstance(manifest, dict):
        expected = resolve_expected_speech(
            lines=manifest.get("lines") or [],
            allow_adlibs=bool(manifest.get("allowAdLibs")),
            explicit=manifest.get("expectedSpeech"),
        )
    silence = expected == EXPECTED_SPEECH_NONE or (
        isinstance(manifest, dict) and not (manifest.get("lines") or [])
    )
    qc = {
        "kind": DIALOGUE_QC_KIND,
        "verdict": QC_UNCERTAIN,
        "reason": CODE_OMNI_UNAVAILABLE,
        "error": str(exc),
        "sceneFinishedEligible": False,
        "infraUnavailable": True,
        "retryable": True,
        "vcmAdvanceBlocked": True,
        "contentFail": False,
        "speechClassification": CLASS_UNCERTAIN_SPEECH,
    }
    try:
        persist_qc_diagnostics(batch, qc)
    except Exception:
        refs = list(getattr(batch, "references", None) or [])
        refs = [r for r in refs if not (isinstance(r, dict) and r.get("kind") == DIALOGUE_QC_KIND)]
        refs.append(qc)
        batch.references = refs
    if locked or silence:
        batch.status = STATUS_QC_RETRY_REQUIRED
        return STATUS_QC_RETRY_REQUIRED
    batch.status = "CandidateReady"
    return "CandidateReady"


def get_dialogue_retake_repair(batch: Any) -> dict[str, Any] | None:
    for r in (getattr(batch, "references", None) or []):
        if isinstance(r, dict) and r.get("kind") == "dialogueRetakeRepair":
            return r
    return None


def consume_dialogue_retake_repair(
    batch: Any,
    replacement_prompt: str = "",
) -> dict[str, Any]:
    """Read batch.references kind=dialogueRetakeRepair. Manifest is authority, not ASR."""
    repair = get_dialogue_retake_repair(batch)
    caller = str(replacement_prompt or "").strip()
    if not repair:
        return {
            "consumed": False,
            "delta": caller,
            "prompt": caller,
            "source": "caller_prompt",
            "keepTimelineR2V": True,
            "reviveLipSync": False,
            "userCorrection": {
                "delta": caller,
                "prompt": caller,
                "source": "caller_prompt",
            },
        }
    uc = repair.get("userCorrection") if isinstance(repair.get("userCorrection"), dict) else {}
    line_parts: list[str] = []
    for sl in repair.get("scriptLines") or []:
        if not isinstance(sl, dict):
            continue
        t = str(sl.get("text") or "").strip()
        if not t:
            continue
        name = sl.get("speakerName") or sl.get("speakerId") or "Speaker"
        line_parts.append(f'{name} says:\n"{t}"')
    from_lines = "\n\n".join(line_parts)
    text = str(uc.get("text") or uc.get("delta") or uc.get("prompt") or from_lines or caller).strip()
    return {
        "consumed": True,
        "delta": text,
        "prompt": text,
        "source": "dialogue_manifest",
        "language": repair.get("language") or uc.get("language"),
        "exactScriptDialogue": True,
        "keepTimelineR2V": True,
        "reviveLipSync": False,
        "manifestId": repair.get("manifestId"),
        "scriptLines": list(repair.get("scriptLines") or []),
        "userCorrection": {
            "delta": text,
            "prompt": text,
            "text": text,
            "source": "dialogue_manifest",
            "language": repair.get("language") or uc.get("language"),
            "exactScriptDialogue": True,
        },
    }


def manifest_exact_script_dialogue(request: Any = None, batch: Any = None) -> bool:
    """True when Manifest lockedScript + authorityExplicit. Voice timbre must not clobber."""
    opts = dict(getattr(request, "providerOptions", None) or {}) if request is not None else {}
    da = opts.get("dialogueAuthority")
    if isinstance(da, dict) and da.get("exactScriptDialogue"):
        return True
    manif = None
    if batch is not None:
        try:
            manif = get_manifest_from_batch(batch)
        except Exception:
            manif = None
    if manif and manif.get("lockedScript") and manif.get("authorityExplicit"):
        return True
    return False


def load_project_settings_json(db: Session, project_id: str) -> Any:
    try:
        from app.db import Project

        row = db.get(Project, project_id)
        return getattr(row, "settings_json", None) if row is not None else None
    except Exception:
        return None


def save_project_settings_json(db: Session, project_id: str, settings_json: str) -> None:
    from app.db import Project

    row = db.get(Project, project_id)
    if row is None:
        raise ValueError("PROJECT_NOT_FOUND")
    row.settings_json = settings_json
    db.add(row)
    db.commit()


def ensure_spoken_language_authority(
    db: Session,
    project_id: str,
    master: Any = None,
    *,
    persist_promote: bool = True,
) -> dict[str, Any]:
    """Resolve project/scene spoken language; optionally persist promote of explicit projectPrimary.

    Never invents from UI default when settings.language blob is missing.
    """
    settings_raw = load_project_settings_json(db, project_id)
    project_lang = read_project_spoken_language(settings_raw)
    promoted = False
    if not project_lang:
        new_settings, project_lang = promote_project_primary_to_spoken_if_explicit(settings_raw)
        if project_lang and persist_promote:
            try:
                save_project_settings_json(db, project_id, new_settings)
                promoted = True
            except Exception:
                promoted = False
    scene_lang = read_scene_spoken_language(master)
    ui_blob = read_ui_language_blob(settings_raw)
    return {
        "projectLanguage": project_lang,
        "sceneLanguage": scene_lang,
        "uiLanguage": {
            "interfaceLocale": ui_blob.get("interfaceLocale"),
            "conversationLocale": ui_blob.get("conversationLocale"),
            "projectPrimaryLocale": ui_blob.get("projectPrimaryLocale"),
            "note": "UI only — not spoken authority",
        },
        "promotedFromProjectPrimary": promoted,
        "explicit": bool(project_lang or scene_lang),
        "error": None if (project_lang or scene_lang) else "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
    }


def compile_dialogue_authority_for_batch(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch: Any,
    master: Any = None,
) -> dict[str, Any]:
    """Build + attach Manifest from batch.speechWindows; return manifest."""
    auth = ensure_spoken_language_authority(db, project_id, master, persist_promote=True)
    # Prefer scene field on master when set
    if master is not None and auth.get("sceneLanguage") is None:
        # allow setting from master after ensure
        pass
    manifest = build_dialogue_manifest(
        project_id=project_id,
        scene_id=scene_id,
        batch_id=getattr(batch, "id", None),
        speech_windows=list(getattr(batch, "speechWindows", None) or []),
        scene_language=auth.get("sceneLanguage"),
        project_language=auth.get("projectLanguage"),
        allow_adlibs=DEFAULT_ALLOW_ADLIBS,
        allow_language_switch=DEFAULT_ALLOW_LANGUAGE_SWITCH,
    )
    attach_manifest_to_batch(batch, manifest)
    return manifest

