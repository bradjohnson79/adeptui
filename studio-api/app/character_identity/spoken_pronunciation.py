"""Rewrite spoken TTS text for known pronunciations.

Stored scripts, Library names, and Timeline dialogue stay as the creator wrote
them. Only the string sent to Qwen3-TTS / Kokoro / IndexTTS2 is respelt.

Qwen3-TTS has no phoneme or SSML lexicon. Respelling is the working steer.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Spoken respellings. No hyphen splits for Owner-ear forms.
# Adept: intentionally OMITTED from the platform table so TTS hears "Adept" as Adept
# (not Add-ept / A-dept / Ah-Dept / any hyphen split). Voice-level entries may still override.
# Anadriya: Annadreeya (NOT Annadreeya / Annadreeyah / other hyphenated forms).
PLATFORM_SPOKEN_PRONUNCIATIONS: tuple[tuple[str, str], ...] = (
    ("Anadriya", "Annadreeya"),
)


def platform_spoken_pronunciations() -> list[dict[str, str]]:
    return [
        {"word": word, "phonetic": spoken, "source": "platform"}
        for word, spoken in PLATFORM_SPOKEN_PRONUNCIATIONS
    ]


def entries_from_voice(voice: Any) -> list[dict[str, Any]]:
    if voice is None:
        return []
    if isinstance(voice, dict):
        raw_entries = voice.get("pronunciations")
        if isinstance(raw_entries, list):
            return [e for e in raw_entries if isinstance(e, dict)]
        raw = voice.get("lineage_json")
    else:
        raw = getattr(voice, "lineage_json", None)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        if isinstance(data, dict):
            entries = data.get("pronunciations") or []
            return [e for e in entries if isinstance(e, dict)]
    return []


def merge_spoken_pronunciations(voice_entries: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for entry in platform_spoken_pronunciations():
        merged[entry["word"].lower()] = dict(entry)
    for entry in voice_entries or []:
        word = str(entry.get("word") or "").strip()
        phonetic = str(entry.get("phonetic") or "").strip()
        if not word or not phonetic:
            continue
        merged[word.lower()] = {
            **entry,
            "word": word,
            "phonetic": phonetic,
            "source": str(entry.get("source") or "voice"),
        }
    return sorted(merged.values(), key=lambda item: len(str(item.get("word") or "")), reverse=True)


def apply_spoken_pronunciations(
    text: str,
    voice_entries: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    spoken = text or ""
    applied: list[dict[str, Any]] = []
    for entry in merge_spoken_pronunciations(voice_entries):
        word = str(entry.get("word") or "").strip()
        phonetic = str(entry.get("phonetic") or "").strip()
        if not word or not phonetic or word.lower() == phonetic.lower():
            continue
        pattern = re.compile(rf"\b{re.escape(word)}('s)?\b", re.IGNORECASE)

        def _replace(match: re.Match[str], spoken_word: str = phonetic) -> str:
            return spoken_word + (match.group(1) or "")

        rewritten, count = pattern.subn(_replace, spoken)
        if count:
            spoken = rewritten
            applied.append(
                {
                    "word": word,
                    "phonetic": phonetic,
                    "count": count,
                    "source": str(entry.get("source") or "platform"),
                }
            )
    return spoken, applied
