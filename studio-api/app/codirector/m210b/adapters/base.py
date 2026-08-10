"""Base sandbox audio adapter with isolated provider root."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....config import settings
from ...m29.providers import ProviderUnavailable
from ..contract import AudioGenerationProviderABC
from ..execution_lock import is_execution_authorized
from ..schemas import AudioGenerateRequest, AudioGenerateResult


def sandbox_providers_root() -> Path:
    return Path(settings.data_dir) / "m210b-sandbox" / "providers"


class BaseSandboxAudioAdapter(AudioGenerationProviderABC):
    """Shared sandbox root + install/health helpers for audio candidates."""

    id: str = "m210b-base"
    capabilities: list[str] = []
    source_key: str | None = None

    def __init__(self, registry_id: str, *, capabilities: list[str] | None = None) -> None:
        self.id = registry_id
        if capabilities is not None:
            self.capabilities = list(capabilities)

    @property
    def sandbox_root(self) -> Path:
        return sandbox_providers_root() / self.id

    def ensure_dirs(self) -> Path:
        root = self.sandbox_root
        for sub in ("venv", "models", "output", "cache", "logs"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root

    def install_manifest_path(self) -> Path:
        return self.sandbox_root / "install-manifest.json"

    def is_installed(self) -> bool:
        manifest = self.install_manifest_path()
        if not manifest.is_file():
            return False
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        return bool(data.get("installed"))

    def assert_authorized(self) -> None:
        if not is_execution_authorized(self.id):
            if self.source_key and is_execution_authorized(self.source_key):
                return
            raise ProviderUnavailable(
                f"M2.10b candidate {self.id!r} is not execution-authorized "
                "(missing from execution lock or productionAuthorized)."
            )

    def health_check(self) -> dict[str, Any]:
        installed = self.is_installed()
        return {
            "id": self.id,
            "ok": installed,
            "installed": installed,
            "sandboxRoot": str(self.sandbox_root),
            "sandboxOnly": True,
            "productionApproved": False,
            "capabilities": list(self.capabilities),
        }

    def validate_request(self, request: AudioGenerateRequest) -> dict[str, Any]:
        errors: list[str] = []
        if not request.prompt or not str(request.prompt).strip():
            errors.append("prompt is required")
        if request.durationSec is not None and float(request.durationSec) <= 0:
            errors.append("durationSec must be > 0")
        if request.capabilityId and self.capabilities:
            if request.capabilityId not in self.capabilities:
                errors.append(
                    f"capability {request.capabilityId!r} not supported by {self.id}"
                )
        return {"ok": not errors, "errors": errors}

    def cancel(self, job_id: str) -> None:
        """Certified cancel-to-source for tracked sandbox audio workers."""
        try:
            from ....audio_studio.process_registry import terminate_job

            terminate_job(str(job_id))
        except Exception:
            return None

    def dispose(self) -> None:
        return None

    def _output_path(self, stem: str, fmt: str = "wav") -> Path:
        self.ensure_dirs()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return self.sandbox_root / "output" / f"{stem}-{stamp}.{fmt}"

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _result(
        self,
        *,
        path: Path,
        request: AudioGenerateRequest,
        duration_sec: float,
        sample_rate: int,
        extra_provenance: dict[str, Any] | None = None,
        fixture: bool = False,
    ) -> AudioGenerateResult:
        digest = self._sha256_file(path)
        provenance = {
            "registryId": self.id,
            "sourceKey": self.source_key,
            "sandboxOnly": True,
            "productionApproved": False,
            "sandboxRoot": str(self.sandbox_root),
            "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "fixture": fixture,
        }
        if extra_provenance:
            provenance.update(extra_provenance)
        return AudioGenerateResult(
            assetPath=str(path),
            sha256=digest,
            durationSec=float(duration_sec),
            sampleRate=int(sample_rate),
            sandboxOnly=True,
            provenance=provenance,
            providerId=self.id,
            capabilityId=request.capabilityId,
            prompt=request.prompt,
            seed=request.seed,
            channels=int(request.channels or 1),
            format=request.format or "wav",
            fixture=fixture,
            productionApproved=False,
        )

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        raise ProviderUnavailable(f"{self.id} generate() not implemented")
