"""Isolated stills-perception install roots. Never VideoChat3 or Hunyuan."""

from __future__ import annotations

import os
from pathlib import Path

from ...config import settings

GROUNDING_DINO_ID = "grounding_dino_tiny"
SAM21_ID = "sam21_hiera_tiny"
DEPTH_ANYTHING_ID = "depth_anything_v2_small"
STILLS_COMPONENT_IDS = (GROUNDING_DINO_ID, SAM21_ID, DEPTH_ANYTHING_ID)

GROUNDING_DINO_HF = "IDEA-Research/grounding-dino-tiny"
GROUNDING_DINO_REVISION = "a2bb814dd30d776dcf7e30523b00659f4f141c71"
SAM21_HF = "facebook/sam2.1-hiera-tiny"
SAM21_REVISION = "de431c4043854a71d8101e17995dfe596bf101a5"
DEPTH_ANYTHING_HF = "depth-anything/Depth-Anything-V2-Small-hf"
DEPTH_ANYTHING_REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"

GROUNDING_DINO_MARKERS = ("config.json",)
SAM21_MARKERS = ("config.json",)
DEPTH_ANYTHING_MARKERS = ("config.json", "preprocessor_config.json")


def stills_root() -> Path:
    return Path(settings.data_dir) / "models" / "stills_perception"


def component_dir(component_id: str) -> Path:
    return stills_root() / component_id


def grounding_dino_dir() -> Path:
    return component_dir(GROUNDING_DINO_ID)


def sam21_dir() -> Path:
    return component_dir(SAM21_ID)


def depth_anything_dir() -> Path:
    return component_dir(DEPTH_ANYTHING_ID)


def model_present(dest: Path, markers: tuple[str, ...]) -> bool:
    return dest.is_dir() and all((dest / name).is_file() for name in markers)


def geometry_models_present() -> bool:
    return (
        model_present(grounding_dino_dir(), GROUNDING_DINO_MARKERS)
        and model_present(sam21_dir(), SAM21_MARKERS)
        and model_present(depth_anything_dir(), DEPTH_ANYTHING_MARKERS)
    )


def venv_root() -> Path:
    return Path(settings.data_dir) / "venvs" / "stills-perception-worker"


def worker_python() -> Path:
    """Isolated stills-perception interpreter. Never VideoChat3. Never silent API fallback."""
    override = (os.environ.get("ADEPT_STILLS_PERCEPTION_PYTHON") or "").strip()
    if override and Path(override).is_file():
        return Path(override)
    win = venv_root() / "Scripts" / "python.exe"
    unix = venv_root() / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    return win if os.name == "nt" else unix


def ensure_stills_perception_venv() -> Path:
    """Create the isolated venv. Do not install Torch here (GPU wheel is explicit)."""
    import venv

    root = venv_root()
    root.parent.mkdir(parents=True, exist_ok=True)
    py = worker_python()
    if py.is_file() and root.is_dir():
        return py
    venv.create(root, with_pip=True)
    py = worker_python()
    if not py.is_file():
        raise RuntimeError(f"stills-perception-worker python missing: {py}")
    return py


COMPONENT_SPECS: dict[str, dict[str, object]] = {
    GROUNDING_DINO_ID: {
        "repo": GROUNDING_DINO_HF,
        "revision": GROUNDING_DINO_REVISION,
        "dest": grounding_dino_dir,
        "markers": GROUNDING_DINO_MARKERS,
        "license_memo": "docs/models/grounding-dino-tiny/LICENSE_CLEARANCE.md",
    },
    SAM21_ID: {
        "repo": SAM21_HF,
        "revision": SAM21_REVISION,
        "dest": sam21_dir,
        "markers": SAM21_MARKERS,
        "license_memo": "docs/models/sam21-hiera-tiny/LICENSE_CLEARANCE.md",
    },
    DEPTH_ANYTHING_ID: {
        "repo": DEPTH_ANYTHING_HF,
        "revision": DEPTH_ANYTHING_REVISION,
        "dest": depth_anything_dir,
        "markers": DEPTH_ANYTHING_MARKERS,
        "license_memo": "docs/models/depth-anything-v2-small/LICENSE_CLEARANCE.md",
    },
}
