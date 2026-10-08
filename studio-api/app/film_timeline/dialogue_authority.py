"""Film Timeline dialogue authority.

Character Voice reuses the existing ambience-on / speech-off contract:
the video generator keeps environmental audio and is told not to speak.
The character's saved voice stays on the character. Timeline stores only
which authority is selected.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

NATIVE_MODEL = "native_model"
CHARACTER_VOICE = "character_voice"

_SILENT = "This shot has no written dialogue, so nobody speaks."
_AMBIENCE_INSTEAD = "If nobody speaks a character line, keep environmental ambience and room tone."
_LOCK = (
    "Dialogue authority is Character Voice. "
    "Keep environmental ambience, room tone, and other non-dialogue scene sound. "
    "Do not speak any character lines. Character speech is not part of this soundtrack."
)


def normalize_mode(raw: str | None) -> str:
    token = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if token in {CHARACTER_VOICE, "character", "voice", "saved_voice"}:
        return CHARACTER_VOICE
    return NATIVE_MODEL


def mode_from_instruction(text: str) -> str | None:
    """The same shot field Co-Director writes. None when the line does not choose."""

    blob = str(text or "")
    if re.search(r"character(?:'s)?\s+voice", blob, re.I):
        return CHARACTER_VOICE
    if re.search(r"native\s+(?:model|voice|dialogue)", blob, re.I):
        return NATIVE_MODEL
    return None


def prompt_asks_to_speak(prompt: str) -> bool:
    """True when the creator wrote a line for this shot to say."""

    text = str(prompt or "")
    if re.search(r'["“”]', text):
        return True
    return bool(re.search(r"\b(says|said|saying|speaks|speaking|whispers|shouts|asks)\b", text, re.I))


def continue_dialogue_instruction(prompt: str) -> str:
    """Keep a continued shot on the new line. The previous clip must not supply the words."""

    if not str(prompt or "").strip():
        return ""
    return (
        "This shot continues the picture only. "
        "Speak the dialogue written in this prompt, and no earlier line. "
        "Do not repeat the previous shot's spoken line."
    )


def lock_prompt(prompt: str) -> str:
    """Tell the renderer to keep ambience and leave character speech out."""

    body = str(prompt or "").strip().replace(_SILENT, _AMBIENCE_INSTEAD)
    if _LOCK in body:
        return body
    if not body:
        return _LOCK
    return f"{body}\n\n{_LOCK}"


def execution_options(voices: list[dict[str, Any]]) -> dict[str, Any]:
    """The payload the existing job copy already forwards. No voice id is stored."""

    speakers = [
        {
            "characterId": str(item.get("characterId") or ""),
            "name": str(item.get("name") or ""),
            "provider": str(item.get("provider") or ""),
            "voiceName": str(item.get("voiceName") or ""),
        }
        for item in voices
        if item.get("usable")
    ]
    return {
        "dialogueAuthority": {
            "mode": CHARACTER_VOICE,
            "authority": "ambience_speech_off",
            "expectedSpeech": "NONE",
            "allowNonSpeechAudio": True,
            "source": "timeline",
        },
        "audioAuthority": {
            "authority": "ambience_speech_off",
            "dialogue": "speech_locked_empty",
            "generateAudio": True,
            "nativeAudio": "enabled",
            "reason": "film_timeline_character_voice",
        },
        "generate_audio": True,
        "audio_generation": True,
        "characterVoices": {"characters": speakers},
    }


def _alias(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _character_refs(shot) -> list[Any]:
    refs = list(getattr(getattr(shot, "state", None), "references", None) or [])
    return [item for item in refs if str(getattr(item, "type", "") or "") == "character"]


def resolve_speakers(db: Session, project_id: str, shot, extra_refs: list[Any] | None = None) -> list[dict[str, Any]]:
    """character → active voice profile → provider. The voice id stays on the character."""

    from ..character_identity.service import active_voice_authority, list_profiles

    refs = _character_refs(shot)
    seen = {str(getattr(item, "assetId", "") or getattr(item, "id", "")) for item in refs}
    for item in extra_refs or []:
        if str(getattr(item, "type", "") or "") != "character":
            continue
        key = str(getattr(item, "assetId", "") or getattr(item, "id", ""))
        if key and key in seen:
            continue
        refs.append(item)
        if key:
            seen.add(key)
    profiles = list_profiles(db, project_id)
    by_alias = {_alias(getattr(profile, "name", "")): profile for profile in profiles}
    speakers: list[dict[str, Any]] = []
    for ref in refs:
        key = _alias(str(getattr(ref, "tag", "") or "").lstrip("@") or getattr(ref, "label", ""))
        profile = by_alias.get(key)
        if profile is None:
            for candidate in profiles:
                name = _alias(getattr(candidate, "name", ""))
                if key and (name.startswith(key) or key.startswith(name)):
                    profile = candidate
                    break
        if profile is None:
            speakers.append(
                {
                    "characterId": "",
                    "name": str(getattr(ref, "label", "") or getattr(ref, "tag", "") or "This character"),
                    "provider": "",
                    "voiceName": "",
                    "usable": False,
                }
            )
            continue
        authority = active_voice_authority(db, project_id, str(profile.id))
        provider = str(authority.get("provider") or "")
        speakers.append(
            {
                "characterId": str(profile.id),
                "name": str(getattr(profile, "name", "") or ""),
                "provider": provider,
                "voiceName": str(authority.get("voiceName") or ""),
                "usable": bool(authority.get("approved")) and provider in {"local", "elevenlabs"},
                "voice": authority,
            }
        )
    return speakers


def availability_message(speakers: list[dict[str, Any]], *, has_character: bool) -> str:
    if not has_character:
        return "Choose the character who speaks in this shot."
    missing = next((item for item in speakers if not item.get("usable")), None)
    if missing is None:
        return ""
    name = str((missing or {}).get("name") or "").strip() or "This character"
    return f"{name} has no Character Voice currently approved."


def apply_instruction(db: Session, project_id: str, scene_id: str, shot_id: str, text: str) -> str | None:
    """Write the Timeline shot when Co-Director names Character Voice or Native Model."""

    mode = mode_from_instruction(text)
    if mode is None or not scene_id or not shot_id:
        return None
    from .orchestrator import set_shot_dialogue_authority

    set_shot_dialogue_authority(db, project_id, scene_id, shot_id, mode)
    return mode


def apply_to_request(request, shot, speakers: list[dict[str, Any]]) -> None:
    if normalize_mode(getattr(getattr(shot, "state", None), "dialogueAuthority", "")) != CHARACTER_VOICE:
        return
    request.prompt = lock_prompt(request.prompt or "")
    options = request.providerOptions if isinstance(request.providerOptions, dict) else {}
    options.update(execution_options(speakers))
    request.providerOptions = options
