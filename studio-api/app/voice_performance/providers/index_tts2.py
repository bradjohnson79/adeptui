from __future__ import annotations

from typing import Any

from ..schemas import PerformanceSegmentOut
from ..runtime import get_index_tts2_runtime
from .base import BaseAdapter


class IndexTTS2Adapter(BaseAdapter):
    provider_key = "index-tts2-local"

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        out = super().translate(voice, segments)
        out["adapter"] = "index_tts2"
        out["providerId"] = self.provider_key
        out["runtime"] = get_index_tts2_runtime().inspect_installation()
        return out


def runtime_manager():
    return get_index_tts2_runtime()


def health_check(*, allow_cpu_fallback: bool = False) -> dict[str, Any]:
    return get_index_tts2_runtime().health_check(allow_cpu_fallback=allow_cpu_fallback)


def synthesize_take(request: dict[str, Any] | Any) -> dict[str, Any]:
    return get_index_tts2_runtime().generate_take(request)


def synthesize_scene(request: dict[str, Any] | Any) -> dict[str, Any]:
    return get_index_tts2_runtime().generate_scene(request)


def capability_metadata() -> dict[str, Any]:
    return get_index_tts2_runtime().capability_metadata()
