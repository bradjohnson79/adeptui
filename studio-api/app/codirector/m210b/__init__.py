"""M2.10b audio sandbox package.

Sandbox-only audio generation adapters, execution-lock guards, scene audio planning,
timeline placement wrappers, Gemma brain helpers, and camera metadata registration.

Production routing and Provider Manifest promotion are out of scope. All generative
audio remains gated by ``STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1`` and the M2.10b
execution lock (``productionAuthorized`` stays false).
"""

from __future__ import annotations

__all__ = ["__doc__"]
