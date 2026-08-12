"""Typed query results for the Creative Knowledge Framework."""

from __future__ import annotations

from pydantic import BaseModel

from ..contracts import KnowledgeFrame


class KnowledgeHit(BaseModel):
    """A knowledge frame plus its source pack."""

    packId: str
    frame: KnowledgeFrame


__all__ = ["KnowledgeHit"]
