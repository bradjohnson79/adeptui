"""Kokoro-82M sandbox adapter (registryId m2101-dialogue-001)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Any

from ....config import settings
from ...m29.providers import ProviderUnavailable
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter

KOKORO_REGISTRY_ID = "m2101-dialogue-001"
KOKORO_SOURCE_KEY = "hexgrad/Kokoro-82M"


class KokoroSandboxAdapter(BaseSandboxAudioAdapter):
    """Try real kokoro/misaki generation when venv+models are present; else honest fail."""

    source_key = KOKORO_SOURCE_KEY
    capabilities = ["audio.dialogue.generate"]

    def __init__(self) -> None:
        super().__init__(KOKORO_REGISTRY_ID, capabilities=self.capabilities)

    def _venv_python(self) -> Path | None:
        data = Path(settings.data_dir)
        for candidate in (
            data / "m210b-kvenv" / "Scripts" / "python.exe",
            data / "m210b-kvenv" / "bin" / "python",
            data / "m210b-kvenv" / "bin" / "python3",
            self.sandbox_root / "venv" / "Scripts" / "python.exe",
            self.sandbox_root / "venv" / "bin" / "python",
            self.sandbox_root / "venv" / "bin" / "python3",
        ):
            if candidate.is_file():
                return candidate
        return None

    def _models_ready(self) -> bool:
        models = self.sandbox_root / "models"
        if not models.is_dir():
            return False
        marker = models / "READY"
        if marker.is_file():
            return True
        try:
            return any(p.name != "READY" for p in models.iterdir())
        except OSError:
            return False

    def _runtime_ready(self) -> bool:
        return self._venv_python() is not None and self._models_ready()

    def is_installed(self) -> bool:
        if super().is_installed():
            return True
        return self._runtime_ready()

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        py = self._venv_python()
        models_ready = self._models_ready()
        runtime_ready = bool(py) and models_ready
        base.update(
            {
                "provider": "kokoro",
                "sourceKey": KOKORO_SOURCE_KEY,
                "venvPython": str(py) if py else None,
                "modelsReady": models_ready,
                "runtimeReady": runtime_ready,
            }
        )
        base["installed"] = self.is_installed()
        base["ok"] = runtime_ready
        return base

    def _try_real_generate(self, request: AudioGenerateRequest, out: Path) -> bool:
        """Attempt real Kokoro/Misaki TTS when local runtime is installed.

        Returns True when a real audio file was written. Never downloads models.
        Runs inside the sandbox venv (host process typically lacks kokoro).
        """
        import subprocess
        import tempfile

        py = self._venv_python()
        if not py or not self._models_ready():
            return False
        out.parent.mkdir(parents=True, exist_ok=True)
        models_dir = self.sandbox_root / "models"
        script = r"""
import sys
from pathlib import Path
prompt = sys.argv[1]
out_path = Path(sys.argv[2])
models_dir = Path(sys.argv[3])
try:
    from kokoro import KPipeline
    import numpy as np
    import soundfile as sf
except Exception as exc:
    print(f"IMPORT_FAIL {exc}", file=sys.stderr)
    sys.exit(2)
# Prefer local model files when present
pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
chunks = []
for item in pipeline(prompt, voice="af_heart"):
    # KPipeline.Result supports index/unpack but is not a tuple/list.
    audio = getattr(item, "audio", None)
    if audio is None:
        try:
            audio = item[2]
        except Exception:
            audio = item
    arr = np.asarray(audio, dtype=np.float32).reshape(-1)
    chunks.append(arr)
if not chunks:
    print("NO_AUDIO", file=sys.stderr)
    sys.exit(3)
audio_arr = np.concatenate(chunks)
sample_rate = 24000
out_path.parent.mkdir(parents=True, exist_ok=True)
# Prefer soundfile; fall back to wave PCM
try:
    sf.write(str(out_path), audio_arr, sample_rate)
except Exception:
    import wave, struct
    pcm = (audio_arr * 32767.0).clip(-32768, 32767).astype("int16").tobytes()
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
print(f"OK {out_path.stat().st_size} {sample_rate}")
"""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix="-kokoro-gen.py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(script)
                tmp_path = Path(tmp.name)
            env = dict(**__import__("os").environ)
            # Keep HF cache inside sandbox when present
            hf = self.sandbox_root / "hf-cache"
            if hf.is_dir():
                env["HF_HOME"] = str(hf)
                env["HUGGINGFACE_HUB_CACHE"] = str(hf)
            proc = subprocess.run(
                [str(py), str(tmp_path), str(request.prompt), str(out), str(models_dir)],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(self.sandbox_root),
                env=env,
            )
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if proc.returncode != 0:
                return False
            return out.is_file() and out.stat().st_size > 44
        except Exception:
            return False

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        self.assert_authorized()
        validation = self.validate_request(request)
        if not validation.get("ok"):
            raise ProviderUnavailable(
                f"Kokoro request invalid: {', '.join(validation.get('errors') or [])}"
            )

        out = self._output_path("kokoro-dialogue", request.format or "wav")
        if self._try_real_generate(request, out):
            duration = float(request.durationSec or 2.0)
            try:
                with wave.open(str(out), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate() or 24000
                    duration = frames / float(rate)
                    sample_rate = rate
            except Exception:
                sample_rate = 24000
            return self._result(
                path=out,
                request=request,
                duration_sec=duration,
                sample_rate=sample_rate,
                extra_provenance={
                    "engine": "kokoro",
                    "mode": "real",
                    "sourceKey": KOKORO_SOURCE_KEY,
                },
            )

        py = self._venv_python()
        models_ready = self._models_ready()
        reasons: list[str] = []
        if not py:
            reasons.append("sandbox venv python missing")
        if not models_ready:
            reasons.append("sandbox models not present")
        if py and models_ready:
            reasons.append("kokoro/misaki import or generate failed")
        raise ProviderUnavailable(
            "Kokoro sandbox adapter cannot generate audio: "
            + "; ".join(reasons)
            + ". Install into data/m210b-sandbox/providers/m2101-dialogue-001 "
            "(venv + models) before execution. No automatic weight download."
        )


def _silent_wav(path: Path, *, duration_sec: float = 0.25, sample_rate: int = 24000) -> None:
    """Internal helper for tests only — not used by production generate path."""
    nframes = max(1, int(duration_sec * sample_rate))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * nframes, *([0] * nframes)))
