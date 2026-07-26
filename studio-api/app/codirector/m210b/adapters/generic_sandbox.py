"""Generic stub adapter for non-Kokoro authorized audio candidates."""

from __future__ import annotations

from typing import Any

from ...m29.providers import ProviderUnavailable
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter

# registryId -> (sourceKey, capabilityId)
GENERIC_CANDIDATES: dict[str, tuple[str, str]] = {
    "m2101-dialogue-002": ("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "audio.dialogue.generate"),
    "m2101-dialogue-003": ("ResembleAI/chatterbox", "audio.dialogue.generate"),
    "m2101-sfx-021": ("Stability-AI/stable-audio-tools", "audio.sfx.generate"),
    "m2101-sfx-030": ("open-mmlab/Amphion", "audio.sfx.generate"),
    "m2101-sfx-031": ("hkchengrex/MMAudio", "audio.sfx.generate"),
    "m2101-music-045": ("ace-step/ACE-Step", "audio.music.generate"),
    "m2101-music-048": ("multimodal-art-projection/YuE", "audio.music.generate"),
    "m2101-music-049": ("riffusion/riffusion-hobby", "audio.music.generate"),
}


class GenericSandboxAudioAdapter(BaseSandboxAudioAdapter):
    """Lock-gated stub: honest ProviderUnavailable until sandbox install completes."""

    def __init__(self, registry_id: str) -> None:
        if registry_id not in GENERIC_CANDIDATES:
            raise ValueError(f"unknown generic sandbox candidate: {registry_id}")
        source_key, cap = GENERIC_CANDIDATES[registry_id]
        self.source_key = source_key
        super().__init__(registry_id, capabilities=[cap])

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        base.update(
            {
                "provider": "generic_sandbox",
                "sourceKey": self.source_key,
                "stub": True,
                "note": "Adapter scaffold only; runtime not installed.",
            }
        )
        return base

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        self.assert_authorized()
        validation = self.validate_request(request)
        if not validation.get("ok"):
            raise ProviderUnavailable(
                f"{self.id} request invalid: {', '.join(validation.get('errors') or [])}"
            )
        if not self.is_installed():
            raise ProviderUnavailable(
                f"Sandbox provider {self.id} ({self.source_key}) is execution-authorized "
                f"but not installed under {self.sandbox_root}. "
                "Complete M2.10b sandbox installation before generate; "
                "no automatic weight download."
            )
        raise ProviderUnavailable(
            f"Sandbox provider {self.id} ({self.source_key}) install marker present "
            "but no real generate implementation is wired yet. "
            "Refusing silent stub audio."
        )


def build_generic_adapter(registry_id: str) -> GenericSandboxAudioAdapter:
    return GenericSandboxAudioAdapter(registry_id)
