"""Install logic for V-JEPA world intelligence models.

Uses huggingface_hub for snapshot download with pinned revisions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .paths import vjepa2_dir, vjepa2_21_dir

logger = logging.getLogger(__name__)

# Pinned revisions (MIT licensed)
VJEPA2_REPO = "facebook/vjepa2-vitl-fpc64-256"
VJEPA2_REVISION = "b3c1679b7c34d3255ef3547f27c7b226aefab26f"

VJEPA2_21_REPO = "facebook/vjepa2.1-vitl-384"
VJEPA2_21_REVISION = "main"  # Pin once stable revision is identified

VJEPA2_21_ALT_REPO = "apiantonio/vjepa2.1-vit-large-384"


def install_vjepa2(
    progress_callback: Optional[callable] = None,
) -> dict:
    """Install V-JEPA 2 ViT-L/16 model."""
    target = vjepa2_dir()
    target.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download

        if progress_callback:
            progress_callback("downloading", "Downloading V-JEPA 2 model...")

        path = snapshot_download(
            repo_id=VJEPA2_REPO,
            revision=VJEPA2_REVISION,
            local_dir=str(target),
            local_dir_use_symlinks=False,
            resume_download=True,
            ignore_patterns=["*.h5", "*.ot", "*.msgpack"],
        )

        if progress_callback:
            progress_callback("verifying", "Verifying installation...")

        return {
            "ok": True,
            "path": str(path),
            "modelId": "vjepa2-vitl-fpc64-256",
            "sizeGb": _dir_size_gb(target),
        }
    except Exception as exc:
        logger.error("Failed to install V-JEPA 2: %s", exc)
        return {
            "ok": False,
            "error": str(exc)[:240],
        }


def install_vjepa2_21(
    progress_callback: Optional[callable] = None,
) -> dict:
    """Install V-JEPA 2.1 ViT-L/16 model.

    Note: V-JEPA 2.1 support in transformers is pending merge (PR #45497).
    This will use the original V-JEPA 2 model as fallback until 2.1 is
    officially supported.
    """
    # TODO: Switch to official facebook repo once 2.1 support is merged
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return {
            "ok": False,
            "error": "huggingface_hub not available",
        }

    target = vjepa2_21_dir()
    target.mkdir(parents=True, exist_ok=True)

    try:
        path = snapshot_download(
            repo_id=VJEPA2_21_ALT_REPO,
            local_dir=str(target),
            local_dir_use_symlinks=False,
            resume_download=True,
        )

        return {
            "ok": True,
            "path": str(path),
            "modelId": "vjepa2.1-vitl-384",
            "sizeGb": _dir_size_gb(target),
        }
    except Exception as exc:
        logger.warning("V-JEPA 2.1 install failed (non-critical): %s", exc)
        return {
            "ok": False,
            "error": str(exc)[:240],
        }


def _dir_size_gb(path: Path) -> float:
    """Get directory size in GB."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return round(total / (1024**3), 2)
