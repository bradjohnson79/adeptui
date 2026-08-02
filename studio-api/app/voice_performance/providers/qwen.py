from __future__ import annotations

from typing import Any

from ..schemas import PerformanceSegmentOut
from .base import BaseAdapter


class QwenAdapter(BaseAdapter):
    provider_key = "qwen3-tts"

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        out = super().translate(voice, segments)
        out["adapter"] = "qwen"
        return out
