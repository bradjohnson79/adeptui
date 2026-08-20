"""Model paths and discovery for V-JEPA world intelligence worker."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Set


def _data_dir() -> Path:
    override = (os.environ.get("ADEPT_DATA_DIR") or os.environ.get("STUDIO_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    try:
        from ...config import settings

        return Path(settings.data_dir)
    except Exception:
        return Path(os.path.join(os.path.expanduser("~"), ".adept", "data"))


def world_intelligence_root() -> Path:
    return _data_dir() / "models" / "world_intelligence"


def vjepa2_dir() -> Path:
    """V-JEPA 2 ViT-L/16 256px (primary model)."""
    return world_intelligence_root() / "vjepa2-vitl-fpc64-256"


def vjepa2_21_dir() -> Path:
    """V-JEPA 2.1 ViT-L/16 384px (advanced model - pending Transformers PR #45497)."""
    return world_intelligence_root() / "vjepa2.1-vitl-384"


def embedding_cache_dir() -> Path:
    return _data_dir() / "cache" / "world_embeddings"


def world_index_path() -> Path:
    return _data_dir() / "cache" / "world_index.json"


def venv_root() -> Path:
    return _data_dir() / "venvs" / "world-intelligence-worker"


def worker_python() -> Path:
    """Isolated CUDA interpreter for JEPA. Never silently claim the API CPU torch is live."""
    override = (os.environ.get("ADEPT_WORLD_INTELLIGENCE_PYTHON") or "").strip()
    if override and Path(override).is_file():
        return Path(override)
    win = venv_root() / "Scripts" / "python.exe"
    unix = venv_root() / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    videochat_win = _data_dir() / "venvs" / "videochat3-worker" / "Scripts" / "python.exe"
    videochat_unix = _data_dir() / "venvs" / "videochat3-worker" / "bin" / "python"
    if videochat_win.is_file():
        return videochat_win
    if videochat_unix.is_file():
        return videochat_unix
    return Path(sys.executable)


VJEPA2_MARKERS: Set[str] = {"model.safetensors", "config.json"}
VJEPA2_21_MARKERS: Set[str] = {"model.safetensors", "config.json"}


def model_present(model_dir: Path, markers: Set[str]) -> bool:
    """Check if model directory contains all expected marker files."""
    if not model_dir.is_dir():
        return False
    return all((model_dir / m).is_file() for m in markers)


def vjepa2_present() -> bool:
    return model_present(vjepa2_dir(), VJEPA2_MARKERS)


def vjepa2_21_present() -> bool:
    return model_present(vjepa2_21_dir(), VJEPA2_21_MARKERS)


def any_model_present() -> bool:
    return vjepa2_present() or vjepa2_21_present()
