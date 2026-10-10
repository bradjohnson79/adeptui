"""Canonical product ports and lifecycle bounds."""

from __future__ import annotations

API_PORT = 8758
COMFY_PORT = 8188
OLLAMA_PORT = 11434
LOGICAL_LOCAL_LLM = "runtime.local_llm"
LOGICAL_COMFY = "runtime.comfy"
LOGICAL_VIDEO = "runtime.video"
DEFAULT_LOCAL_LLM_MODEL = "gemma4:31b-it-qat"
RETIRED_WEB_PORT = 8760
DEV_API_PORT = 8742
H3_COMFY_PORT = 8192
VITE_PORT = 5173
CONTROL_PORT = 8759
CONTROL_PORT_FALLBACK = 8779
TASK_NAME = "AdeptRuntimeService"
LEGACY_TASK_NAMES = ("AdeptUI-Runtime-Manager", "AdeptBetaBackendManager")
RUNTIME_VERSION = "1"

API_HOST = "127.0.0.1"

SERVICES = ("studio_api", "comfyui", "cloudflared", "ollama")
ROUTE_A_SERVICE = "minimax_h3_route_a"
TRACKED_SERVICES = SERVICES + (ROUTE_A_SERVICE,)

MAX_RESTARTS = 5
STORM_WINDOW_SEC = 300
BASE_BACKOFF_SEC = 5
MAX_BACKOFF_SEC = 120
BUSY_ALIVE_CYCLES = 20

# Cold Studio API import on BRAD-5090 often exceeds 120s; 300s avoids restart churn.
API_READY_TIMEOUT_SEC = 300
COMFY_READY_TIMEOUT_SEC = 45
# Isolated Route A :8192 cold-starts after GPU handoff; do not reuse the
# canonical :8188 ready bound. Prepare-on-Generate, not idle watchdog.
ROUTE_A_READY_TIMEOUT_SEC = 120
TUNNEL_READY_TIMEOUT_SEC = 20
OLLAMA_READY_TIMEOUT_SEC = 45
PORT_RELEASE_TIMEOUT_SEC = 15

API_HEALTH_PATH = "/api/healthz"
COMFY_STATS_PATH = "/system_stats"
COMFY_QUEUE_PATH = "/queue"
OLLAMA_TAGS_PATH = "/api/tags"

TUNNEL_NAME = "adept-ui-beta"
TUNNEL_HOSTNAME = "api-beta.adeptui.org"
