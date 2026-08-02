"""Base provider adapter — never leaks raw provider schemas into Character/Timeline domains."""

from __future__ import annotations

from typing import Any, Protocol

from ..provider_translation import translate_plan
from ..schemas import PerformanceSegmentOut


class ProviderAdapter(Protocol):
    provider_key: str

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        ...


class BaseAdapter:
    provider_key = "base"

    def translate(self, voice: dict[str, Any] | None, segments: list[PerformanceSegmentOut]) -> dict[str, Any]:
        return translate_plan(provider_key=self.provider_key, voice=voice, segments=segments)
