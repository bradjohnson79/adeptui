"""Camera-control metadata registration helpers (unavailable; no install)."""

from __future__ import annotations

from typing import Any

from .flags import m210b_camera_metadata_enabled

CAMERA_CAPABILITY_IDS: tuple[str, ...] = (
    "scene.camera.control",
    "scene.camera.control.still",
    "scene.camera.control.video",
    "scene.camera.orbit",
    "scene.camera.trajectory",
)


def camera_metadata_records() -> list[dict[str, Any]]:
    """Return metadata-only capability rows — always unavailable / not installed."""
    records: list[dict[str, Any]] = []
    for cap_id in CAMERA_CAPABILITY_IDS:
        records.append(
            {
                "capabilityId": cap_id,
                "status": "unavailable",
                "operational": False,
                "installationAuthorized": False,
                "executionAuthorized": False,
                "weightDownloadAuthorized": False,
                "productionApproved": False,
                "sandboxOnly": True,
                "metadataOnly": True,
                "note": (
                    "M2.10b camera metadata discovery only. "
                    "No camera candidate may be installed or executed without "
                    "a Product-approved camera execution lock."
                ),
            }
        )
    return records


def register_camera_metadata_capabilities(
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Expose camera capability IDs as unavailable metadata (no install side effects)."""
    if not force and not m210b_camera_metadata_enabled():
        return {
            "registered": False,
            "reason": "STUDIO_FEATURE_M210B_CAMERA_METADATA_V1 is disabled",
            "capabilities": [],
        }
    records = camera_metadata_records()
    return {
        "registered": True,
        "metadataOnly": True,
        "installationPerformed": False,
        "capabilities": records,
    }
