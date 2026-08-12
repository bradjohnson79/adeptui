"""M42 Phase 4.5 Audio Studio domain."""

from __future__ import annotations


def ensure_tables() -> None:
    """JSON-backed store — ensure data root exists (no SQL migrations)."""
    from pathlib import Path

    from ..config import settings

    Path(settings.data_dir, "audio_studio").mkdir(parents=True, exist_ok=True)


from .production_gate import evaluate_m42_audio_studio_gate

__all__ = ["ensure_tables", "evaluate_m42_audio_studio_gate"]
