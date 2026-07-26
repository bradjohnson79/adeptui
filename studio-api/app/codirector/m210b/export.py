"""Export stem placements + sandbox provenance manifest (JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import settings
from .install import sandbox_root


def export_dir() -> Path:
    path = sandbox_root() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_stems_manifest(
    *,
    project_id: str,
    scene_id: str | None,
    placements: list[dict[str, Any]],
    provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "m210b-stems-placement-manifest",
        "projectId": project_id,
        "sceneId": scene_id,
        "sandboxOnly": True,
        "productionApproved": False,
        "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "placements": placements,
        "provenance": provenance or [],
        "notes": (
            "Sandbox stems export only. Not a production delivery. "
            "Provider Manifest promotion is out of scope."
        ),
    }


def write_stems_manifest(
    *,
    project_id: str,
    scene_id: str | None = None,
    placements: list[dict[str, Any]] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    filename: str | None = None,
) -> Path:
    """Write stems placement + provenance JSON under data/m210b-sandbox/exports."""
    manifest = build_stems_manifest(
        project_id=project_id,
        scene_id=scene_id,
        placements=placements or [],
        provenance=provenance,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = filename or f"stems-{project_id}-{stamp}.json"
    path = export_dir() / name
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Also mirror under data/exports for discoverability without claiming production.
    mirror = Path(settings.data_dir) / "exports" / "m210b" / name
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
