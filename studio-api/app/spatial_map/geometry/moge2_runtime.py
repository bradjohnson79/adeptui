"""Isolated MoGe-2 runtime status.

GitHub first (microsoft/MoGe). Weights from the official Hugging Face card
only when install is authorized. Files on disk never imply Ready. Weights
license stays unconfirmed — never MIT or Apache-2.0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import settings
from ...setup.license_metadata import license_row

MOGE_CODE_REPO = "https://github.com/microsoft/MoGe"
MOGE_CODE_LICENSE = "MIT (DINOv2 subtree Apache-2.0)"
MOGE_WEIGHTS_LICENSE = "unconfirmed"
COMPONENT_ID = "moge2_geometry"


def runtime_root() -> Path:
    return Path(settings.data_dir) / "runtimes" / "moge2"


def source_present() -> bool:
    root = runtime_root()
    return (root / "src").is_dir() or (root / "moge").is_dir() or (root / ".git").is_dir()


def weights_present() -> bool:
    root = runtime_root()
    for pattern in ("**/*.safetensors", "**/*.ckpt", "**/*.pt", "**/*.pth"):
        if any(root.glob(pattern)):
            return True
    return False


def runtime_status() -> dict[str, Any]:
    source = source_present()
    weights = weights_present()
    license_meta = license_row(COMPONENT_ID)
    return {
        "engine": "moge2",
        "componentId": COMPONENT_ID,
        "role": "single_image_geometry",
        "productClass": "ESSENTIAL",
        "codeRepo": MOGE_CODE_REPO,
        "codeLicense": MOGE_CODE_LICENSE,
        "weightsLicense": MOGE_WEIGHTS_LICENSE,
        "licenseStatus": license_meta.get("license_status"),
        "ownerPolicy": license_meta.get("owner_policy"),
        "isolation": "dedicated venv under data/runtimes/moge2 — never Comfy, Studio API, Adept Bots, or MCP",
        "sourceInstalled": source,
        "runtimeReady": False,
        "commercialModelAccess": True,
        "modelReady": False,
        "gpuReady": False,
        "productionCertified": False,
        "installed": source,
        "available": False,
        "status": "not_ready",
        "blocker": None if not weights else "MoGe-2 weights are present but the isolated runtime is not certified Ready.",
        "creatorMessage": (
            "MoGe-2 is an Essential geometry engine. Agree to Essential Components, "
            "then install from GitHub. Weight terms are pending official clarification."
        ),
        "runtimeRoot": str(runtime_root()),
    }
