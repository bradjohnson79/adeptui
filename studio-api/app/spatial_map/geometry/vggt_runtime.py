"""Isolated VGGT-1B-Commercial runtime status.

Official GitHub facebookresearch/vggt. Production weights only
facebook/VGGT-1B-Commercial. A clone is never Ready. Stays
MODEL_ACCESS_GATED until commercial weights exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import settings
from ...setup.license_metadata import license_row

VGGT_CODE_REPO = "https://github.com/facebookresearch/vggt"
VGGT_MODEL_ID = "facebook/VGGT-1B-Commercial"
FORBIDDEN_MODEL_ID = "facebook/VGGT-1B"
COMPONENT_ID = "vggt_1b_commercial"


def runtime_root() -> Path:
    return Path(settings.data_dir) / "runtimes" / "vggt"


def source_present() -> bool:
    root = runtime_root()
    src = root / "src"
    return (
        (src / "vggt").is_dir()
        or (src / ".git").is_dir()
        or (src / "vggt" / "models" / "vggt.py").is_file()
        or (root / "vggt").is_dir()
        or (root / ".git").is_dir()
        or (root / "vggt" / "models" / "vggt.py").is_file()
    )


def commercial_weights_present() -> bool:
    root = runtime_root() / "weights" / "VGGT-1B-Commercial"
    if not root.exists():
        return False
    return any(root.rglob("*.safetensors")) or any(root.rglob("*.pt")) or any(root.rglob("*.bin"))


def runtime_status() -> dict[str, Any]:
    source = source_present()
    weights = commercial_weights_present()
    license_meta = license_row(COMPONENT_ID)
    gated = not weights
    return {
        "engine": "vggt_1b_commercial",
        "componentId": COMPONENT_ID,
        "role": "multi_view_geometry",
        "productClass": "ESSENTIAL",
        "codeRepo": VGGT_CODE_REPO,
        "modelSource": VGGT_MODEL_ID,
        "forbiddenModel": FORBIDDEN_MODEL_ID,
        "licenseStatus": license_meta.get("license_status"),
        "licenseStatusSecondary": license_meta.get("license_status_secondary"),
        "ownerPolicy": license_meta.get("owner_policy"),
        "isolation": "dedicated venv under data/runtimes/vggt — never Comfy, Studio API, Adept Bots, or MCP",
        "sourceInstalled": source,
        "runtimeReady": False,
        "commercialModelAccess": bool(weights),
        "modelReady": False,
        "gpuReady": False,
        "productionCertified": False,
        "installed": source,
        "available": False,
        "status": "model_access_gated" if gated else "not_ready",
        "blocker": "MODEL_ACCESS_GATED" if gated else "VGGT commercial weights exist but the runtime is not certified Ready.",
        "creatorMessage": (
            "VGGT-1B Commercial is an Essential geometry engine for Standard Spatial Map. "
            "Commercial model access is still gated. Cloning GitHub does not make it Ready. "
            "MoGe-2 Express can still be used."
        ),
        "runtimeRoot": str(runtime_root()),
    }


def assert_commercial_model_only(model_id: str) -> None:
    cleaned = (model_id or "").strip()
    if cleaned == FORBIDDEN_MODEL_ID or cleaned.endswith("/VGGT-1B"):
        raise ValueError("facebook/VGGT-1B is forbidden. Use facebook/VGGT-1B-Commercial only.")
    if cleaned and cleaned != VGGT_MODEL_ID:
        raise ValueError(f"VGGT production weights must be {VGGT_MODEL_ID}.")
