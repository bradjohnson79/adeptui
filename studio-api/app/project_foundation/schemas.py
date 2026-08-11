"""Pydantic contracts for the Project Foundation Status service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

PillarStatus = Literal["not_started", "in_progress", "complete"]


class PillarInfo(BaseModel):
    status: PillarStatus
    exists: bool
    last_updated: str | None = None
    item_count: int = 0


class FoundationStatus(BaseModel):
    story: PillarInfo
    script: PillarInfo
    storyboard: PillarInfo
    characters: PillarInfo
    ready_for_timeline: bool
    missing_pillars: list[str]
