"""Film Timeline — the only production Timeline owner.

Scene → Shot → Segment. ShotState is the only continuity authority.
Provider adapters remain infrastructure behind the orchestrator.
"""

from .contracts import FilmTimeline

__all__ = ["FilmTimeline"]
