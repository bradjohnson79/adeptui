"""ACE-Step music adapter — isolated subprocess, music.generate only."""

from __future__ import annotations

import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ...m29.providers import ProviderUnavailable
from ..schemas import AudioGenerateRequest, AudioGenerateResult
from .base import BaseSandboxAudioAdapter
from .generic_sandbox import GENERIC_CANDIDATES

ACE_STEP_REGISTRY_ID = "m2101-music-045"
ACE_STEP_SOURCE = GENERIC_CANDIDATES[ACE_STEP_REGISTRY_ID][0]


class AceStepSandboxAdapter(BaseSandboxAudioAdapter):
    capabilities = ["music.generate", "audio.music.generate"]
    source_key = ACE_STEP_SOURCE

    def __init__(self) -> None:
        super().__init__(ACE_STEP_REGISTRY_ID, capabilities=self.capabilities)

    def _repo_root(self) -> Path:
        # adapters -> m210b -> codirector -> app -> studio-api -> repo
        return Path(__file__).resolve().parents[5]

    def _venv_python(self) -> Path | None:
        repo = self._repo_root()
        for candidate in (
            repo / "data" / "m210b-ace-venv" / "Scripts" / "python.exe",
            self.sandbox_root / "venv" / "Scripts" / "python.exe",
            self.sandbox_root / "venv" / "bin" / "python",
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
                "provider": "ace-step",
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
                f"ace-step request invalid: {', '.join(validation.get('errors') or [])}"
            )
        kind = str(request.kind or "music").lower()
        if kind not in ("music", ""):
            raise ProviderUnavailable("ace-step is certified for music.generate only")
        if request.capabilityId and request.capabilityId not in (
            "music.generate",
            "audio.music.generate",
        ):
            raise ProviderUnavailable(
                f"ace-step refuses capability {request.capabilityId!r} (music only)"
            )
        py = self._venv_python()
        if not py:
            raise ProviderUnavailable("ACE-Step venv python not found (m210b-ace-venv)")
        if not self.is_installed():
            raise ProviderUnavailable("ACE-Step sandbox not installed")

        self.ensure_dirs()
        out = self.sandbox_root / "output" / f"ace_step_{uuid.uuid4().hex[:10]}.wav"
        worker = Path(__file__).resolve().parents[2] / "native_audio" / "ace_step_worker.py"
        # Studio candidates: allow shorter clips; keep a practical upper bound.
        duration = max(4.0, min(30.0, float(request.durationSec or 12.0)))
        prompt = str(request.prompt or "cinematic ambient underscore, no vocals")
        checkpoint_dir = self.sandbox_root / "models"
        # Faster first-pass defaults for Audio Studio batches (quality still usable).
        infer_step = 18
        try:
            extra = getattr(request, "timelineIntent", None) or {}
            if isinstance(extra, dict) and extra.get("inferStep") is not None:
                infer_step = max(8, min(60, int(extra.get("inferStep"))))
        except Exception:
            pass
        cmd = [
            str(py),
            str(worker),
            "--prompt",
            prompt,
            "--duration",
            str(duration),
            "--out",
            str(out),
            "--seed",
            str(int(request.seed) if request.seed is not None else secrets.randbelow(2_147_483_647) or 1),
            "--checkpoint_dir",
            str(checkpoint_dir),
            "--device_id",
            "0",
            "--infer_step",
            str(infer_step),
            "--cpu_offload",
            "0",
        ]
        # Prefer cancel-to-source tracked Popen when Audio Studio execution scope is active.
        try:
            from ....audio_studio import process_registry as preg

            ctx = preg.current_execution()
        except Exception:
            ctx = None
        if ctx is not None:
            proc = preg.run_tracked(
                cmd,
                job_id=ctx.job_id,
                runtime="ACE-Step",
                project_id=ctx.project_id or request.projectId,
                batch_id=ctx.batch_id,
                candidate_id=ctx.candidate_id,
                timeout=900,
            )
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size < 1000:
            raise ProviderUnavailable(
                f"ACE-Step generate failed (code={proc.returncode}): "
                f"{(proc.stderr or proc.stdout or '')[-1500:]}"
            )
        return self._result(
            path=out,
            request=request,
            duration_sec=duration,
            sample_rate=int(request.sampleRate or 48000),
            extra_provenance={
                "provider": "ace-step",
                "capability": "music.generate",
                "route": "isolated_worker_subprocess",
                "stdoutTail": (proc.stdout or "")[-500:],
            },
        )
