"""MMAudio SFX adapter — isolated subprocess; sfx/ambience/foley only."""

from __future__ import annotations

import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ...m29.providers import ProviderUnavailable
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter

MMAUDIO_REGISTRY_ID = "m2101-sfx-031"
MMAUDIO_SOURCE = "hkchengrex/MMAudio"


class MMAudioSandboxAdapter(BaseSandboxAudioAdapter):
    capabilities = [
        "sfx.generate",
        "ambience.generate",
        "foley.generate",
        "audio.sfx.generate",
    ]
    source_key = MMAUDIO_SOURCE

    def __init__(self) -> None:
        super().__init__(MMAUDIO_REGISTRY_ID, capabilities=self.capabilities)

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[5]

    def _venv_python(self) -> Path | None:
        repo = self._repo_root()
        for candidate in (
            repo / "data" / "m210b-sfx-venv" / "Scripts" / "python.exe",
            self.sandbox_root / "venv" / "Scripts" / "python.exe",
        ):
            if candidate.is_file():
                return candidate
        return None

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        py = self._venv_python()
        cuda = False
        device_name = None
        torch_version = None
        if py:
            try:
                import subprocess as _sp

                probe = _sp.run(
                    [
                        str(py),
                        "-c",
                        "import torch; print(torch.__version__); print(int(torch.cuda.is_available())); "
                        "print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                lines = [ln.strip() for ln in (probe.stdout or "").splitlines() if ln.strip()]
                if lines:
                    torch_version = lines[0]
                if len(lines) >= 2:
                    cuda = lines[1] == "1"
                if len(lines) >= 3 and lines[2]:
                    device_name = lines[2]
            except Exception as exc:
                base["cudaProbeError"] = str(exc)
        base.update(
            {
                "provider": "mmaudio",
                "capabilities": self.capabilities,
                "venvPython": str(py) if py else None,
                "runtimeReady": bool(py) and self.is_installed(),
                "route": "isolated_worker_subprocess",
                "cuda": cuda,
                "device": device_name,
                "torchVersion": torch_version,
                "accelerator": "cuda" if cuda else "cpu",
            }
        )
        base["ok"] = bool(py) and self.is_installed()
        return base

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        self.assert_authorized()
        validation = self.validate_request(request)
        if not validation.get("ok"):
            raise ProviderUnavailable(
                f"mmaudio request invalid: {', '.join(validation.get('errors') or [])}"
            )
        kind = str(request.kind or "sfx").lower()
        if kind in ("music", "dialogue", "speech", "tts"):
            raise ProviderUnavailable("mmaudio refuses music/dialogue (sfx/ambience/foley only)")
        py = self._venv_python()
        if not py or not self.is_installed():
            raise ProviderUnavailable("MMAudio sandbox runtime not installed")

        worker = Path(__file__).resolve().parents[2] / "native_audio" / "mmaudio_worker.py"
        self.ensure_dirs()
        out = self.sandbox_root / "output" / f"mmaudio_{uuid.uuid4().hex[:10]}.wav"
        duration = max(1.0, min(20.0, float(request.durationSec or 3.0)))
        repo = self.sandbox_root / "src" / "MMAudio"
        cmd = [
            str(py),
            str(worker),
            "--prompt",
            str(request.prompt),
            "--duration",
            str(duration),
            "--out",
            str(out),
            "--seed",
            str(int(request.seed) if request.seed is not None else secrets.randbelow(2_147_483_647) or 1),
            "--repo",
            str(repo),
        ]
        try:
            from ....audio_studio import process_registry as preg

            ctx = preg.current_execution()
        except Exception:
            ctx = None
        if ctx is not None:
            proc = preg.run_tracked(
                cmd,
                job_id=ctx.job_id,
                runtime="MMAudio",
                project_id=ctx.project_id or request.projectId,
                batch_id=ctx.batch_id,
                candidate_id=ctx.candidate_id,
                timeout=900,
            )
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size < 1000:
            raise ProviderUnavailable(
                f"MMAudio generate failed (code={proc.returncode}): "
                f"{(proc.stderr or proc.stdout or '')[-1500:]}"
            )
        return self._result(
            path=out,
            request=request,
            duration_sec=duration,
            sample_rate=int(request.sampleRate or 48000),
            extra_provenance={
                "provider": "mmaudio",
                "capability": "sfx.generate",
                "route": "isolated_worker_subprocess",
                "stdoutTail": (proc.stdout or "")[-500:],
            },
        )
