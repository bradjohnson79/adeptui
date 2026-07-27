"""Route A: reconstruction adapters — fixture always; real only if binaries detected."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .store import M213Store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class CaptureAssessment:
    image_count: int
    coverage_score: float
    ready: bool
    inferred: bool
    notes: list[str]
    fixture: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "imageCount": self.image_count,
            "coverageScore": self.coverage_score,
            "ready": self.ready,
            "inferred": self.inferred,
            "notes": self.notes,
            "fixture": self.fixture,
            "honesty": (
                "Single-image path is fully/partially inferred — not a measured reconstruction."
                if self.inferred
                else "Multi-view coverage assessed before reconstruct."
            ),
        }


class EnvironmentReconstructionAdapter(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def reconstruct(self, capture: dict[str, Any]) -> dict[str, Any]: ...


class FixtureReconstructionAdapter(EnvironmentReconstructionAdapter):
    name = "fixture"

    def available(self) -> bool:
        return True

    def reconstruct(self, capture: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": self.name,
            "mode": "fixture",
            "mesh": "fixture-proxy.glb",
            "fixture": True,
            "honesty": "Fixture reconstruction for CI. Not a real COLMAP/Nerfstudio result.",
            "capture": capture,
        }


class OptionalBinaryAdapter(EnvironmentReconstructionAdapter):
    def __init__(self, name: str, binary_names: tuple[str, ...], env_keys: tuple[str, ...] = ()) -> None:
        self.name = name
        self.binary_names = binary_names
        self.env_keys = env_keys

    def _bin(self) -> Optional[str]:
        for key in self.env_keys:
            val = os.environ.get(key)
            if val and os.path.exists(val):
                return val
        for b in self.binary_names:
            found = shutil.which(b)
            if found:
                return found
        return None

    def available(self) -> bool:
        return self._bin() is not None

    def reconstruct(self, capture: dict[str, Any]) -> dict[str, Any]:
        bin_path = self._bin()
        if not bin_path:
            return {
                "ok": False,
                "adapter": self.name,
                "mode": "unavailable",
                "message": (
                    f"{self.name} binary not detected. Adept UI will not silently download "
                    "COLMAP/Nerfstudio/gsplat. Install locally and set env path if desired."
                ),
                "fixture": False,
            }
        # Detection-only scaffold: do not invent a successful real reconstruction.
        return {
            "ok": False,
            "adapter": self.name,
            "mode": "detected_not_executed",
            "binary": bin_path,
            "message": (
                f"{self.name} binary detected at {bin_path}, but full reconstruction execution "
                "is not auto-run in M2.13 (safety). Use fixture adapter for CI proofs."
            ),
            "fixture": False,
            "capture": capture,
        }


ADAPTERS: list[EnvironmentReconstructionAdapter] = [
    FixtureReconstructionAdapter(),
    OptionalBinaryAdapter("colmap", ("colmap",), ("STUDIO_COLMAP_BIN", "COLMAP_BIN")),
    OptionalBinaryAdapter("nerfstudio", ("ns-train", "ns-process-data"), ("STUDIO_NERFSTUDIO_BIN",)),
    OptionalBinaryAdapter("gsplat", ("gsplat",), ("STUDIO_GSPLAT_BIN",)),
]


def list_adapters() -> list[dict[str, Any]]:
    out = []
    for a in ADAPTERS:
        out.append(
            {
                "name": a.name,
                "available": a.available(),
                "silentInstall": False,
                "fixture": a.name == "fixture",
            }
        )
    return out


def assess_capture(images: list[str] | None = None, *, fixture: bool = False) -> CaptureAssessment:
    images = images or ([] if not fixture else ["fixture-a.jpg", "fixture-b.jpg", "fixture-c.jpg"])
    count = len(images)
    inferred = count <= 1
    if count == 0:
        return CaptureAssessment(0, 0.0, False, False, ["no images"], fixture)
    if inferred:
        return CaptureAssessment(
            count,
            0.15,
            True,
            True,
            ["single-image: environment will be labeled fully/partially inferred"],
            fixture,
        )
    coverage = min(1.0, 0.25 + 0.1 * count)
    ready = coverage >= 0.45
    notes = ["coverage estimated from view count (scaffold)"]
    if not ready:
        notes.append("coverage below recommended threshold")
    return CaptureAssessment(count, coverage, ready, False, notes, fixture)


def reconstruct_environment(
    db: Session,
    *,
    project_id: str,
    images: list[str] | None = None,
    adapter_name: str = "fixture",
    title: str = "Reconstructed Environment",
    scene_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    ensure_m213_tables()
    fixture = adapter_name == "fixture"
    assessment = assess_capture(images, fixture=fixture)
    if not assessment.ready and not force:
        return {
            "ok": False,
            "assessment": assessment.to_dict(),
            "message": "Capture not ready for reconstruction. Pass force=true to proceed with labels.",
        }
    adapter = next((a for a in ADAPTERS if a.name == adapter_name), None)
    if adapter is None:
        raise ValueError(f"unknown adapter {adapter_name}")
    if not adapter.available():
        return {
            "ok": False,
            "assessment": assessment.to_dict(),
            "adapters": list_adapters(),
            "message": f"Adapter {adapter_name} unavailable (no silent install).",
        }
    result = adapter.reconstruct({"images": images or [], "assessment": assessment.to_dict()})
    if not result.get("ok") and not fixture:
        return {"ok": False, "assessment": assessment.to_dict(), "result": result}
    env_id = str(uuid.uuid4())
    summary = {
        "route": "reconstruction",
        "assessment": assessment.to_dict(),
        "result": result,
        "inferred": assessment.inferred,
        "adapters": list_adapters(),
    }
    db.execute(
        text(
            "INSERT INTO m213_virtual_environments "
            "(id, project_id, scene_id, route, status, title, asset_id, summary_json, approved, approved_at, created_at, updated_at) "
            "VALUES (:id, :project_id, :scene_id, 'reconstruction', :status, :title, NULL, :summary_json, 0, NULL, :ts, :ts)"
        ),
        {
            "id": env_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "status": "registered" if result.get("ok") else "failed",
            "title": title,
            "summary_json": json.dumps(summary),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.environment.reconstruct",
        action="reconstruct",
        project_id=project_id,
        payload={"environmentId": env_id, "adapter": adapter_name, "fixture": fixture},
    )
    return {
        "ok": bool(result.get("ok")),
        "environmentId": env_id,
        "route": "reconstruction",
        "approved": False,
        "approvalGate": "environment",
        "assessment": assessment.to_dict(),
        "result": result,
        "fixture": fixture,
        "inferred": assessment.inferred,
    }
