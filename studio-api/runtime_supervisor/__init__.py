"""Adept UI Python Runtime Supervisor.

Authoritative lifecycle owner for Studio API, ComfyUI, Cloudflare tunnel,
and optional Ollama. Absorbs the certified BetaBackend laws without
starting retired :8760 and without spawning uvicorn --workers.

This package must not import FastAPI or app.main so it can start the API.
"""

from .identity import PortState, classify_listener
from .state import SupervisorState

__all__ = ["PortState", "SupervisorState", "classify_listener", "ensure_studio_api_running", "ensureStudioApiRunning"]


def __getattr__(name: str):
    if name in {"ensure_studio_api_running", "ensureStudioApiRunning"}:
        from .ensure_studio_api import ensureStudioApiRunning, ensure_studio_api_running

        return ensure_studio_api_running if name == "ensure_studio_api_running" else ensureStudioApiRunning
    raise AttributeError(name)
