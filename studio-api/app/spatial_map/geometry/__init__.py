"""Deterministic Spatial Map geometry: reconstruct, then render.

MoGe-2 and VGGT feed the same TOP_DOWN_ORTHOGRAPHIC renderer.
A git clone is never Ready. VGGT stays MODEL_ACCESS_GATED until
facebook/VGGT-1B-Commercial weights exist.
"""

from .moge2_runtime import runtime_status as moge2_runtime_status
from .vggt_runtime import runtime_status as vggt_runtime_status

__all__ = ["moge2_runtime_status", "vggt_runtime_status"]
