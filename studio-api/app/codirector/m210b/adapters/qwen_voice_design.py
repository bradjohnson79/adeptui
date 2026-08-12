"""Qwen3-TTS VoiceDesign 1.7B sandbox adapter (M3.3)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ...m29.providers import ProviderUnavailable
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter

QWEN_VOICE_DESIGN_REGISTRY_ID = "m2101-voice-design-021"
QWEN_VOICE_DESIGN_SOURCE_KEY = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"


class QwenVoiceDesignSandboxAdapter(BaseSandboxAudioAdapter):
    source_key = QWEN_VOICE_DESIGN_SOURCE_KEY
    capabilities = ["audio.character_voice.design", "audio.dialogue.generate"]

    def __init__(self) -> None:
        super().__init__(
            QWEN_VOICE_DESIGN_REGISTRY_ID,
            capabilities=["audio.character_voice.design", "audio.dialogue.generate"],
        )

    def _venv_python(self) -> Path | None:
        root = self.sandbox_root
        for rel in (("venv", "Scripts", "python.exe"), ("venv", "bin", "python")):
            candidate = root.joinpath(*rel)
            if candidate.is_file():
                return candidate
        # Short-path junction used by install scripts
        from ....config import settings

        alt = Path(settings.data_dir) / "m210b-qwen-voice-design-venv" / ("Scripts" if (Path(settings.data_dir) / "m210b-qwen-voice-design-venv" / "Scripts").is_dir() else "bin") / ("python.exe" if (Path(settings.data_dir) / "m210b-qwen-voice-design-venv" / "Scripts").is_dir() else "python")
        return alt if alt.is_file() else None

    def _runtime_ready(self) -> bool:
        py = self._venv_python()
        models = self.sandbox_root / "models"
        return bool(self.is_installed() and py and models.is_dir() and any(models.iterdir()))

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        ready = self._runtime_ready()
        base.update(
            {
                "ok": ready,
                "ready": ready,
                "stub": not ready,
                "sourceKey": self.source_key,
                "message": None
                if ready
                else "Qwen3-TTS Voice Design 1.7B is not installed. Use Source Manager / m33d install scripts.",
            }
        )
        return base

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        self.assert_authorized()
        if not self._runtime_ready():
            raise ProviderUnavailable(
                "Qwen3-TTS Voice Design 1.7B is not installed or not ready."
            )
        validation = self.validate_request(request)
        if not validation.get("ok"):
            raise ProviderUnavailable(f"Invalid request: {', '.join(validation.get('errors') or [])}")

        out = self._output_path("qwen-voice-design", request.format or "wav")
        worker = Path(__file__).resolve().parents[2] / "native_audio" / "qwen_voice_design_worker.py"
        py = self._venv_python()
        assert py
        voice_desc = getattr(request, "voiceDescription", None) or request.prompt
        cmd = [
            str(py),
            str(worker),
            "--models-dir",
            str(self.sandbox_root / "models"),
            "--output",
            str(out),
            "--text",
            request.prompt,
            "--voice-description",
            str(voice_desc),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
        if proc.returncode != 0 or not out.is_file():
            raise ProviderUnavailable(
                f"Qwen VoiceDesign worker failed: {(proc.stderr or proc.stdout or '')[:800]}"
            )
        return self._result(
            path=out,
            request=request,
            duration_sec=float(request.durationSec or 2.0),
            sample_rate=24000,
            extra_provenance={"worker": "qwen_voice_design_worker", "sourceKey": QWEN_VOICE_DESIGN_SOURCE_KEY},
        )
