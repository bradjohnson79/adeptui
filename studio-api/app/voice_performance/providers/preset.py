from __future__ import annotations

from typing import Any

from ..schemas import PerformanceSegmentOut
from .base import BaseAdapter


class PresetAdapter(BaseAdapter):
    """Approved preset voices only — no invented identity."""

    provider_key = "preset"

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        out = super().translate(voice, segments)
        out["adapter"] = "preset"
        out["warnings"] = list(out.get("warnings") or []) + [
            "Preset adapter uses registered preset voice ids only."
        ]
        return out
