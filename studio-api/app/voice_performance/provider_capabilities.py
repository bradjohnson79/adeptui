"""Canonical voice provider capability registry — UI must not guess support."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class VoiceProviderCapability:
    provider_key: str
    adapter_version: str
    supports_emotion_tags: bool
    supports_delivery_tags: bool
    supports_pause_control: bool
    supports_pitch_control: bool
    supports_speed_control: bool
    supports_volume_control: bool
    supports_phonemes: bool
    supports_ssml: bool
    supports_reactions: bool
    supports_segment_seed: bool
    supports_voice_clone: bool
    supports_voice_design: bool
    supports_streaming: bool
    maximum_text_length: int | None
    supported_audio_formats: list[str]
    supported_sample_rates: list[int]
    prompt_guidance_fallback: bool
    capability_version: str


CAPABILITIES: dict[str, VoiceProviderCapability] = {
    "index-tts2-local": VoiceProviderCapability(
        provider_key="index-tts2-local",
        adapter_version="m4.10",
        supports_emotion_tags=False,
        supports_delivery_tags=False,
        supports_pause_control=False,
        supports_pitch_control=False,
        supports_speed_control=False,
        supports_volume_control=False,
        supports_phonemes=False,
        supports_ssml=False,
        supports_reactions=False,
        supports_segment_seed=False,
        supports_voice_clone=True,
        supports_voice_design=False,
        supports_streaming=False,
        maximum_text_length=400,
        supported_audio_formats=["wav"],
        supported_sample_rates=[22050],
        prompt_guidance_fallback=True,
        capability_version="1",
    ),
    "qwen3-tts": VoiceProviderCapability(
        provider_key="qwen3-tts",
        adapter_version="w44.1",
        supports_emotion_tags=False,  # prompt-guided only for now
        supports_delivery_tags=False,
        supports_pause_control=False,  # assembled via segmentation
        supports_pitch_control=False,
        supports_speed_control=False,
        supports_volume_control=False,
        supports_phonemes=False,
        supports_ssml=False,
        supports_reactions=False,
        supports_segment_seed=True,
        supports_voice_clone=True,
        supports_voice_design=True,
        supports_streaming=False,
        maximum_text_length=400,
        supported_audio_formats=["wav"],
        supported_sample_rates=[24000],
        prompt_guidance_fallback=True,
        capability_version="1",
    ),
    "kokoro": VoiceProviderCapability(
        provider_key="kokoro",
        adapter_version="w44.1",
        supports_emotion_tags=False,
        supports_delivery_tags=False,
        supports_pause_control=False,
        supports_pitch_control=False,
        supports_speed_control=True,
        supports_volume_control=False,
        supports_phonemes=False,
        supports_ssml=False,
        supports_reactions=False,
        supports_segment_seed=True,
        supports_voice_clone=False,
        supports_voice_design=False,
        supports_streaming=False,
        maximum_text_length=500,
        supported_audio_formats=["wav"],
        supported_sample_rates=[24000],
        prompt_guidance_fallback=True,
        capability_version="1",
    ),
}


def list_capabilities() -> list[dict[str, Any]]:
    return [asdict(c) for c in CAPABILITIES.values()]


def get_capability(provider_key: str) -> VoiceProviderCapability | None:
    return CAPABILITIES.get(provider_key)


SupportMode = str  # Native | Translated | Prompt-guided | Pre-rendered asset | Unsupported


def classify_feature(provider_key: str, feature: str, *, has_asset: bool = False) -> SupportMode:
    if has_asset and feature == "reaction":
        return "Pre-rendered asset"
    cap = get_capability(provider_key)
    if not cap:
        return "Unsupported"
    mapping = {
        "emotion": (cap.supports_emotion_tags, cap.prompt_guidance_fallback),
        "delivery": (cap.supports_delivery_tags, cap.prompt_guidance_fallback),
        "pause": (cap.supports_pause_control, True),  # assembled
        "pace": (cap.supports_speed_control, cap.prompt_guidance_fallback),
        "pitch": (cap.supports_pitch_control, False),
        "volume": (cap.supports_volume_control, False),
        "reaction": (cap.supports_reactions, cap.prompt_guidance_fallback),
        "pronunciation": (cap.supports_phonemes, cap.prompt_guidance_fallback),
    }
    native, fallback = mapping.get(feature, (False, False))
    if feature == "pause" and not native:
        return "Translated"  # segmented assembly
    if native:
        return "Native"
    if fallback:
        return "Prompt-guided"
    return "Unsupported"
