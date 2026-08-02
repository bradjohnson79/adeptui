from __future__ import annotations

from typing import Any

from ..schemas import PerformanceSegmentOut
from .base import BaseAdapter


class KokoroAdapter(BaseAdapter):
    provider_key = "kokoro"

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        out = super().translate(voice, segments)
        out["adapter"] = "kokoro"
        return out
