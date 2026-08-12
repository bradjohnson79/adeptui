"""M42 Wave 4B — Adept UI MAGI Editor product foundation (no Comfy builders)."""

from .production_gate import evaluate_magi_wave4b_gate
from .readiness import deferred_surfaces, production_surfaces

__all__ = [
    "evaluate_magi_wave4b_gate",
    "deferred_surfaces",
    "production_surfaces",
]
