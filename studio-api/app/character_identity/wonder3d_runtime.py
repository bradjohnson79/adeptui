"""Isolated Wonder3D multi-view runtime probe.

Wonder3D production weights (`flamehaze1115/wonder3d-v1.0`) are AGPL-3.0.
This adapter never downloads weights, never imports torch into Studio API,
and never reports Ready because files exist.
"""

from __future__ import annotations

from typing import Any

WONDER3D_CODE_REPO = "https://github.com/xxlong0/Wonder3D"
WONDER3D_WEIGHTS_ID = "flamehaze1115/wonder3d-v1.0"
WONDER3D_CODE_LICENSE = "MIT"
WONDER3D_WEIGHTS_LICENSE = "AGPL-3.0"
LICENSE_BLOCKER = "WONDER3D MODEL WEIGHTS ARE AGPL-3.0"

# Intended V3 camera convention. Live GPU mapping is UNMEASURED until a
# license-cleared checkpoint is run on this machine.
CAMERA_CONVENTION = {
    "front": {"wonder3d_view": "front", "approx_deg": 0, "label": "Front"},
    "three_quarter": {"wonder3d_view": "front_right", "approx_deg": 45, "label": "3/4 (right)"},
    "side": {"wonder3d_view": "right", "approx_deg": 90, "label": "Side (right)"},
    "back": {"wonder3d_view": "back", "approx_deg": 180, "label": "Back"},
}
CAMERA_CONVENTION_STATUS = "UNMEASURED — license-blocked; not live-mapped"


def runtime_status() -> dict[str, Any]:
    """Truthful readiness. Files on disk never imply Ready."""
    return {
        "engine": "wonder3d",
        "role": "multi_view",
        "installed": False,
        "runtimeReady": False,
        "gpuReady": False,
        "modelReady": False,
        "available": False,
        "status": "license_blocked",
        "blocker": LICENSE_BLOCKER,
        "codeRepo": WONDER3D_CODE_REPO,
        "codeLicense": WONDER3D_CODE_LICENSE,
        "weightsId": WONDER3D_WEIGHTS_ID,
        "weightsLicense": WONDER3D_WEIGHTS_LICENSE,
        "isolation": "dedicated venv under data/runtimes/wonder3d — never Comfy or studio-api/.venv",
        "cameraConvention": CAMERA_CONVENTION,
        "cameraConventionStatus": CAMERA_CONVENTION_STATUS,
        "creatorMessage": "Character Angles are unavailable. Wonder3D model weights are AGPL-3.0 and cannot be installed into Adept UI.",
    }


def assert_can_generate() -> None:
    from fastapi import HTTPException

    status = runtime_status()
    raise HTTPException(
        status_code=409,
        detail={
            "code": "WONDER3D_LICENSE_BLOCKED",
            "message": status["creatorMessage"],
            "blocker": LICENSE_BLOCKER,
            "runtime": status,
        },
    )
