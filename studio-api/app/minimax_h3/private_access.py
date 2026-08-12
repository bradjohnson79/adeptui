"""Private owner-only access gate for MiniMax H3 Route A."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..config import settings
from ..feature_flags import feature_flags


ALLOWED_RUNTIME_HOSTS = frozenset({"127.0.0.1", "localhost"})
DEFAULT_RUNTIME_PORT = 8192


def private_local_enabled() -> bool:
    return bool(getattr(feature_flags, "minimax_h3_private_local", False))


def public_creator_enabled() -> bool:
    return bool(getattr(settings, "minimax_h3_public_creator_enabled", False))


def best_match_enabled() -> bool:
    return bool(getattr(settings, "minimax_h3_best_match_enabled", False))


def general_routing_enabled() -> bool:
    return bool(getattr(settings, "minimax_h3_general_routing_enabled", False))


def owner_only_required() -> bool:
    return bool(getattr(settings, "minimax_h3_owner_only", True))


def runtime_url() -> str:
    return str(getattr(settings, "minimax_h3_runtime_url", "http://127.0.0.1:8192")).rstrip("/")


def model_root() -> str:
    return str(getattr(settings, "minimax_h3_model_root", r"D:\01_Models"))


def runtime_url_is_isolated_route_a(url: str | None = None) -> bool:
    raw = url or runtime_url()
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if host not in ALLOWED_RUNTIME_HOSTS:
        return False
    if port != DEFAULT_RUNTIME_PORT:
        return False
    return parsed.scheme in {"http", "https"}


def access_snapshot() -> dict[str, Any]:
    enabled = private_local_enabled()
    isolated = runtime_url_is_isolated_route_a()
    return {
        "privateLocalEnabled": enabled,
        "ownerOnly": owner_only_required(),
        "publicCreatorEnabled": public_creator_enabled(),
        "bestMatchEnabled": best_match_enabled(),
        "generalRoutingEnabled": general_routing_enabled(),
        "runtimeUrl": runtime_url(),
        "modelRoot": model_root(),
        "runtimeIsIsolatedRouteA": isolated,
        "ownerAccessActive": enabled and isolated and not public_creator_enabled(),
    }


def assert_private_owner_access() -> dict[str, Any]:
    """Fail closed unless private local owner access is active."""
    snap = access_snapshot()
    if not snap["privateLocalEnabled"]:
        raise PermissionError("MiniMax H3 private local access is disabled.")
    if snap["publicCreatorEnabled"]:
        raise PermissionError("MiniMax H3 public creator access must remain disabled.")
    if not snap["runtimeIsIsolatedRouteA"]:
        raise PermissionError("MiniMax H3 runtime URL must be the isolated Route A host on port 8192.")
    if snap["ownerOnly"] and not snap["ownerAccessActive"]:
        raise PermissionError("MiniMax H3 is available for private owner use only.")
    return snap
