"""CI-only fixture audio adapter (clearly labeled fixture=True)."""

from __future__ import annotations

import struct
import uuid
import wave
from typing import Any

from ...m29.providers import ProviderUnavailable
from ..flags import fixture_mode_enabled
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter

FIXTURE_REGISTRY_ID = "m210b-fixture-ci"


class FixtureCiAudioAdapter(BaseSandboxAudioAdapter):
    """Deterministic WAV writer for CI. Requires ADEPT_M29_FIXTURE_MODE or ADEPT_M210B_FIXTURE_MODE."""

    source_key = "m210b/fixture-ci"
    capabilities = [
        "audio.dialogue.generate",
        "audio.sfx.generate",
        "audio.music.generate",
        "audio.ambience.generate",
    ]

    def __init__(self) -> None:
        super().__init__(FIXTURE_REGISTRY_ID, capabilities=self.capabilities)

    def health_check(self) -> dict[str, Any]:
        enabled = fixture_mode_enabled()
        return {
            "id": self.id,
            "ok": enabled,
            "installed": enabled,
            "fixture": True,
            "sandboxOnly": True,
            "productionApproved": False,
            "capabilities": list(self.capabilities),
            "note": "CI fixture adapter only; never production.",
        }

    def is_installed(self) -> bool:
        return fixture_mode_enabled()

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        if not fixture_mode_enabled():
            raise ProviderUnavailable(
                "FixtureCiAudioAdapter requires ADEPT_M29_FIXTURE_MODE or "
                "ADEPT_M210B_FIXTURE_MODE; refusing outside fixture CI."
            )
        validation = self.validate_request(request)
        if not validation.get("ok"):
            raise ProviderUnavailable(
                f"fixture request invalid: {', '.join(validation.get('errors') or [])}"
            )

        duration = float(request.durationSec or 1.0)
        sample_rate = int(request.sampleRate or 48000)
        out = self._output_path(f"fixture-{uuid.uuid4().hex[:10]}", request.format or "wav")
        nframes = max(1, int(duration * sample_rate))
        # Quiet tone-ish ramp so file is non-trivial but deterministic-ish length.
        frames = []
        for i in range(nframes):
            # very low amplitude saw
            sample = int(((i % 64) - 32) * 20)
            frames.append(max(-32767, min(32767, sample)))
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack("<" + "h" * nframes, *frames))

        result = self._result(
            path=out,
            request=request,
            duration_sec=duration,
            sample_rate=sample_rate,
            extra_provenance={
                "engine": "fixture_ci",
                "fixture": True,
                "mode": "ci_fixture",
            },
            fixture=True,
        )
        result.assetId = f"m210b-fixture-{uuid.uuid4().hex[:12]}"
        result.fixture = True
        result.provenance["fixture"] = True
        return result
