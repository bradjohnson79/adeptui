"""Spoken respelling for Qwen3-TTS / Kokoro / IndexTTS2.

Qwen has no phoneme lexicon or SSML phoneme tags. The only steer is a
hyphenated syllable respell of the string sent to the model. Stored
scripts, Library copy, and Timeline text stay unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Platform defaults. Adept is intentionally omitted so TTS hears "Adept"
# as Adept — do not respell to Add-ept / Ah-Dept / At-Dept.
PLATFORM_SPOKEN_PRONUNCIATIONS: tuple[tuple[str, str], ...] = (
    ("Anadriya", "Anna-Dree-Ya"),
)

_WORD_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _word_pattern(word: str) -> re.Pattern[str]:
    cached = _WORD_PATTERN_CACHE.get(word)
    if cached is None:
        cached = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        _WORD_PATTERN_CACHE[word] = cached
    return cached


def _entry_pair(entry: Any) -> tuple[str, str] | None:
    if isinstance(entry, dict):
        word = str(entry.get("word") or "").strip()
        phonetic = str(entry.get("phonetic") or "").strip()
    elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
        word = str(entry[0] or "").strip()
        phonetic = str(entry[1] or "").strip()
    else:
        return None
    if not word:
        return None
    return word, phonetic


def merge_spoken_pronunciations(
    voice_overrides: Iterable[Any] | None = None,
    platform: Iterable[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """Platform defaults first; voice-level entries win on the same word."""
    merged: dict[str, tuple[str, str]] = {}
    source = PLATFORM_SPOKEN_PRONUNCIATIONS if platform is None else platform
    for entry in source:
        pair = _entry_pair(entry)
        if pair is None:
            continue
        merged[pair[0].lower()] = pair
    for entry in voice_overrides or ():
        pair = _entry_pair(entry)
        if pair is None:
            continue
        merged[pair[0].lower()] = pair
    return list(merged.values())


def apply_spoken_pronunciations(
    text: str,
    pronunciations: Iterable[tuple[str, str]] | None = None,
) -> str:
    """Respell known words in the TTS-only string. No-op when phonetic == word."""
    if not text:
        return text
    pairs = (
        list(PLATFORM_SPOKEN_PRONUNCIATIONS)
        if pronunciations is None
        else [pair for pair in (_entry_pair(entry) for entry in pronunciations) if pair]
    )
    # Longer words first so overlapping terms cannot steal a prefix match.
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    spoken = text
    for word, phonetic in pairs:
        if not phonetic or phonetic == word:
            continue
        spoken = _word_pattern(word).sub(phonetic, spoken)
    return spoken
