"""Re-export shim — canonical Co-Director Dialogue Authority.

Canonical module: ``app.codirector.dialogue_authority``.
Timeline Gen and legacy relative imports keep working with no behavior fork.
Private helpers (``_norm_lang``, etc.) are re-exported intentionally.
"""
from __future__ import annotations

from app.codirector import dialogue_authority as _canonical

# Full alias: public + private names (star-import would drop leading underscores).
globals().update(
    {name: getattr(_canonical, name) for name in dir(_canonical) if name != "__builtins__"}
)
__all__ = [name for name in dir(_canonical) if not name.startswith("__")]
