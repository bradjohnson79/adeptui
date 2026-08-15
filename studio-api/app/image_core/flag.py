"""Internal flag. Certification runs with SCENE_IMAGE_CORE enabled (default ON)."""

from __future__ import annotations

import os

_FALSE = frozenset({"0", "false", "no", "off"})


def scene_image_core_enabled() -> bool:
    raw = (os.environ.get("SCENE_IMAGE_CORE") or "1").strip().lower()
    return raw not in _FALSE
