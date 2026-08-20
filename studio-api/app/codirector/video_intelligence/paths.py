"""Isolated install roots — never overwrite LTX / WAN / Hunyuan."""

from __future__ import annotations

from pathlib import Path

from ...config import settings

VIDEOCHAT3_HF_ID = "MCG-NJU/VideoChat3-4B"
VIDEOCHAT3_REVISION = "37fa901ec5913f84bc31108ebc1e60ad1903634c"
INTERNVIDEO3_HF_ID = "yanziang/InternVideo3-8B-Instruct"
INTERNVIDEO3_REVISION = "c4602918b65225650d152db2850fe34e01d21fcd"

VIDEOCHAT3_MARKERS = ("config.json", "model.safetensors.index.json")
INTERNVIDEO3_MARKERS = ("config.json", "model.safetensors.index.json")


def understanding_root() -> Path:
    return Path(settings.data_dir) / "models" / "video_understanding"


def videochat3_dir() -> Path:
    return understanding_root() / "videochat3-4b"


def internvideo3_dir() -> Path:
    return understanding_root() / "internvideo3-8b"


def model_present(root: Path, markers: tuple[str, ...]) -> bool:
    if not root.is_dir():
        return False
    return all((root / name).is_file() for name in markers) and any(root.glob("*.safetensors"))
