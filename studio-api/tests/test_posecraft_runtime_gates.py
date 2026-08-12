"""Master Program Phase 29 — runtime gate preservation.

Locks the two image-runtime ports so a future change cannot silently
substitute one for the other:
- :8188 — production ComfyUI (probe/reuse/ADEPT_COMFY_LAUNCH/
  IMAGE_RUNTIME_STARTUP_FAILED). This is the only port the image runtime
  may use for ComfyUI work.
- :8192 — MiniMax H3 runtime (owner-only, separate from production
  Comfy). PoseCraft never substitutes one for the other.
"""

from __future__ import annotations

from app.config import settings


def test_comfyui_runtime_port_is_8188() -> None:
    """Production ComfyUI must default to 127.0.0.1:8188."""
    assert settings.comfy_url.rstrip("/").endswith(":8188"), settings.comfy_url
    assert settings.comfy_url.startswith("http://127.0.0.1:"), settings.comfy_url


def test_minimax_h3_runtime_port_is_8192() -> None:
    """MiniMax H3 runtime must default to 127.0.0.1:8192 and never be the
    production Comfy port."""
    assert settings.minimax_h3_runtime_url.rstrip("/").endswith(":8192"), settings.minimax_h3_runtime_url
    assert settings.minimax_h3_runtime_url != settings.comfy_url


def test_minimax_h3_is_owner_only_and_public_creator_disabled() -> None:
    """H3 must remain owner-only; public creator / Best Match / general
    routing must stay disabled (out of scope for PoseCraft Master Program)."""
    assert settings.minimax_h3_owner_only is True
    assert settings.minimax_h3_public_creator_enabled is False
    assert settings.minimax_h3_best_match_enabled is False
    assert settings.minimax_h3_general_routing_enabled is False
