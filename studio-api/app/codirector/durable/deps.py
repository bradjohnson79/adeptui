"""Serializable per-turn dependencies. No database session crosses a workflow boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TurnDeps:
    envelope: dict[str, Any]
    exposed_tool_ids: tuple[str, ...]
