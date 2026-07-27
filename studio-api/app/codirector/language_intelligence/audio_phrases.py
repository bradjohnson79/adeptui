"""Multilingual audio-exclusion phrases → same AudioIntent as MIL."""

from __future__ import annotations

from typing import Optional

from ..model_intelligence.schemas import AudioChannelPolicy, AudioIntent, AudioMode

# Phrases that normalize to music=prohibited across the twelve launch languages.
NO_MUSIC_PHRASES: tuple[str, ...] = (
    # en (avoid bare "silent"/"silence" — English heuristics own full mute modes)
    "no background music",
    "no score",
    "no music",
    "without music",
    "no soundtrack",
    # fr
    "pas de musique de fond",
    "sans musique",
    "aucune musique",
    # es
    "sin música de fondo",
    "sin musica de fondo",
    "sin música",
    "sin musica",
    # ja
    "背景音楽なし",
    "音楽なし",
    "BGMなし",
    # zh-Hans
    "不要背景音乐",
    "无背景音乐",
    "不要音乐",
    # hi
    "कोई पृष्ठभूमि संगीत नहीं",
    "बिना संगीत",
    "संगीत नहीं",
    # ru
    "без фоновой музыки",
    "без музыки",
    # pt (BR)
    "sem música de fundo",
    "sem musica de fundo",
    "sem música",
    "sem musica",
    # ar
    "بدون موسيقى خلفية",
    "بدون موسيقى",
    "لا موسيقى",
    # bn
    "কোনো ব্যাকগ্রাউন্ড সংগীত নয়",
    "সংগীত ছাড়া",
    # id
    "tanpa musik latar",
    "tanpa musik",
    "tidak ada musik",
    # ur
    "بغیر پس منظر موسیقی",
    "بغیر موسیقی",
    "کوئی موسیقی نہیں",
)

NO_AUDIO_PHRASES: tuple[str, ...] = (
    "no audio",
    "no sound",
    "mute",
    "sans son",
    "sin audio",
    "音声なし",
    "无声音",
    "без звука",
    "sem áudio",
    "بدون صوت",
    "tanpa audio",
)


def normalize_audio_from_multilingual_text(
    prompt: str, hint: Optional[AudioIntent] = None
) -> AudioIntent:
    base = hint or AudioIntent()
    text = (prompt or "").strip()
    lowered = text.lower()

    if any(p.lower() in lowered or p in text for p in NO_AUDIO_PHRASES):
        return AudioIntent(
            audioMode=AudioMode.NONE,
            music=AudioChannelPolicy.PROHIBITED,
            dialogue=AudioChannelPolicy.PROHIBITED,
            ambience=AudioChannelPolicy.PROHIBITED,
            soundEffects=AudioChannelPolicy.PROHIBITED,
        )

    music = base.music
    if any(p.lower() in lowered or p in text for p in NO_MUSIC_PHRASES):
        music = AudioChannelPolicy.PROHIBITED

    return AudioIntent(
        audioMode=base.audioMode
        if base.audioMode != AudioMode.NONE
        else AudioMode.EXTERNAL_AUDIO_PIPELINE,
        music=music,
        dialogue=base.dialogue,
        ambience=base.ambience,
        soundEffects=base.soundEffects,
    )
