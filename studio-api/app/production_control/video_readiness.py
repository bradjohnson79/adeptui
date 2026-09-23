"""Derived video-generator facts. Not a second catalog and not a label table."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..hosted_providers import video_registry

# Derived views of the canonical video registry
# (app.hosted_providers.video_registry). The registry is the one source of
# truth; these names keep their exact historical values (parity-tested).

# Product IDs (Production Control) — aliases never become a second product.
PRODUCT_ALIASES: dict[str, str] = dict(video_registry.product_aliases())

# Product → Timeline adapter id. Provider variants are not collapsed.
# LTX 2.5 must not bind ltx-local (that is LTX 2.3).
PRODUCT_ADAPTER: dict[str, str] = dict(video_registry.product_adapter_map())

# Adapters whose submit() actually reaches a runtime or provider.
LIVE_SUBMIT_ADAPTERS = video_registry.live_submit_adapters()

# Hosted products that would silently use the wrong provider if aliased.
HOSTED_LIVE_ONLY = dict(video_registry.hosted_live_only())

SETUP_COMPONENTS: dict[str, tuple[str, ...]] = video_registry.setup_components()

REQUIRED_NODES: dict[str, tuple[str, ...]] = video_registry.required_nodes()

TESTING_UNCERTIFIED = frozenset(
    {
        "ltx-2.5-full",
        "ltx-2.5-comfy",
    }
)

READINESS_STATES = frozenset(
    {
        "Ready",
        "Requires Setup",
        "Provider Not Configured",
        "Runtime Offline",
        "Testing",
        "Unsupported",
    }
)

_FACT_TTL_SEC = 45.0
_fact_cache: dict[str, tuple[float, "VideoFacts"]] = {}
_comfy_nodes_cache: tuple[float, set[str]] | None = None
_comfy_health_cache: tuple[float, dict[str, Any]] | None = None
_route_a_cache: tuple[float, tuple[bool, str]] | None = None
_minimax_weights_cache: tuple[float, tuple[bool, str]] | None = None


def canonical_product_id(model_id: str | None) -> str:
    token = str(model_id or "").strip()
    if not token:
        return ""
    return PRODUCT_ALIASES.get(token, token)


def adapter_for_product(model_id: str | None) -> str | None:
    product = canonical_product_id(model_id)
    if not product:
        return None
    return PRODUCT_ADAPTER.get(product) or PRODUCT_ADAPTER.get(str(model_id or "").strip())


@dataclass
class VideoFacts:
    product_id: str
    locality: str
    adapter_id: str | None = None
    adapter_registered: bool = False
    live_submit: bool = False
    checkpoint_ok: bool | None = None
    checkpoint_reason: str = ""
    runtime_ok: bool | None = None
    runtime_reason: str = ""
    nodes_ok: bool | None = None
    nodes_reason: str = ""
    credentials_ok: bool | None = None
    credentials_reason: str = ""
    vram_ok: bool | None = None
    vram_reason: str = ""
    workflow_ok: bool | None = None
    workflow_reason: str = ""
    admission_ok: bool | None = None
    admission_reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def _secret_configured(name: str) -> bool:
    try:
        from ..secrets_store import secret_status

        status = secret_status(name)
        if isinstance(status, dict):
            return bool(status.get("configured"))
        return bool(getattr(status, "configured", False))
    except Exception:
        return False


def _verify_components(component_ids: tuple[str, ...]) -> tuple[bool, str]:
    if not component_ids:
        return True, ""
    try:
        from ..setup.diagnostics import verify_component
    except Exception as exc:
        return False, f"Checkpoint Missing — verifier unavailable: {exc}"
    missing: list[str] = []
    for cid in component_ids:
        try:
            result = verify_component(cid)
        except Exception:
            missing.append(cid)
            continue
        if not bool(getattr(result, "healthy", False)):
            missing.append(cid)
    if missing:
        return False, f"Checkpoint Missing — {', '.join(missing)}"
    return True, ""


def _comfy_health() -> dict[str, Any]:
    global _comfy_health_cache
    now = time.monotonic()
    if _comfy_health_cache and now - _comfy_health_cache[0] < _FACT_TTL_SEC:
        return _comfy_health_cache[1]
    payload: dict[str, Any] = {"ok": False, "vram_total": 0, "vram_free": 0}
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
        devices = stats.get("devices") or [{}]
        device = devices[0] if devices else {}
        payload = {
            "ok": True,
            "vram_total": int(device.get("vram_total") or 0),
            "vram_free": int(device.get("vram_free") or 0),
            "device": device.get("name"),
        }
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        payload = {"ok": False, "vram_total": 0, "vram_free": 0}
    _comfy_health_cache = (now, payload)
    return payload


def _comfy_nodes() -> set[str]:
    global _comfy_nodes_cache
    now = time.monotonic()
    if _comfy_nodes_cache and now - _comfy_nodes_cache[0] < 30.0:
        return _comfy_nodes_cache[1]
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=8) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        names = set(info.keys()) if isinstance(info, dict) else set()
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        names = set()
    _comfy_nodes_cache = (now, names)
    return names


def _adept_h3_ref2v_weights_ok() -> tuple[bool, str]:
    """Adept Comfy :8188 must have the ref2va UNET and H3 CLIP/VAEs."""
    try:
        from ..config import settings
        from ..workflows.h3_ref2v_builder import (
            H3_AUDIO_VAE,
            H3_CLIP,
            H3_REF2VA_UNET,
            H3_VIDEO_VAE,
        )

        root = getattr(settings, "comfy_models_dir", None)
        names = (H3_REF2VA_UNET, H3_CLIP, H3_VIDEO_VAE, H3_AUDIO_VAE)
        if root is None:
            return True, ""
        from pathlib import Path

        base = Path(root)
        folders = ("", "diffusion_models", "text_encoders", "vae", "checkpoints")
        missing: list[str] = []
        for name in names:
            found = False
            for folder in folders:
                candidate = base / folder / name if folder else base / name
                if candidate.is_file() and candidate.stat().st_size > 0:
                    found = True
                    break
            if not found:
                missing.append(name)
        if missing:
            return False, f"Checkpoint Missing — {', '.join(missing)}"
        return True, ""
    except Exception as exc:
        return False, f"Checkpoint Missing — {exc}"


def _minimax_weights_ok() -> tuple[bool, str]:
    global _minimax_weights_cache
    now = time.monotonic()
    if _minimax_weights_cache and now - _minimax_weights_cache[0] < 30.0:
        return _minimax_weights_cache[1]
    try:
        from ..minimax_h3.route_a_adapter import required_checkpoint_paths

        missing = [
            role
            for role, path in required_checkpoint_paths().items()
            if not path.is_file() or path.stat().st_size <= 0
        ]
        result = (False, f"Checkpoint Missing — {', '.join(missing)}") if missing else (True, "")
    except Exception as exc:
        result = (False, f"Checkpoint Missing — {exc}")
    _minimax_weights_cache = (now, result)
    return result


def _route_a_listener_up() -> bool:
    """True when something answers on :8192 (including stub8192 placeholders)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8192/system_stats", timeout=3) as resp:
            return int(resp.status) == 200
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _route_a_vram_resident() -> bool:
    """True only when MiniMax Route A holds real GPU residency.

    stub8192 answers /system_stats with comfyui_version=stub and devices=[] —
    that must NOT block Desktop Comfy LTX / LTXVImgToVideo admission.
    """
    try:
        with urllib.request.urlopen("http://127.0.0.1:8192/system_stats", timeout=3) as resp:
            if int(resp.status) != 200:
                return False
            raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw or "{}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    system = data.get("system") if isinstance(data.get("system"), dict) else {}
    version = str(system.get("comfyui_version") or "").strip().lower()
    if version == "stub" or version.startswith("stub"):
        return False
    devices = data.get("devices")
    if not isinstance(devices, list) or not devices:
        return False
    return True


def route_a_runtime_ready() -> bool:
    """Shared Route A probe. Fail-fast when :8192 is down; cached."""
    return _route_a_ready()[0]


def _route_a_ready() -> tuple[bool, str]:
    global _route_a_cache
    now = time.monotonic()
    if _route_a_cache and now - _route_a_cache[0] < _FACT_TTL_SEC:
        return _route_a_cache[1]
    if not _route_a_listener_up():
        result = (False, "Comfy Runtime Offline — MiniMax Route A is not ready")
        _route_a_cache = (now, result)
        return result
    try:
        from ..minimax_h3.route_a_adapter import RouteARuntimeAdapter

        payload = RouteARuntimeAdapter().readiness()
        ready = bool(payload.get("ready") if isinstance(payload, dict) else getattr(payload, "ready", False))
        result = (True, "") if ready else (False, "Comfy Runtime Offline — MiniMax Route A is not ready")
    except Exception as exc:
        result = (False, f"Comfy Runtime Offline — MiniMax Route A: {exc}")
    _route_a_cache = (now, result)
    return result


def _adapter_registered(adapter_id: str | None) -> bool:
    if not adapter_id:
        return False
    try:
        from ..director_timeline_w46.generation.registry import get_registry

        get_registry().capabilities(adapter_id)
        return True
    except Exception:
        return False


def collect_video_facts(model_id: str, *, locality: str, estimated_vram_gb: float | None = None) -> VideoFacts:
    product = canonical_product_id(model_id) or str(model_id or "").strip()
    if video_registry.is_retired_local_video(product) or video_registry.is_retired_local_video(model_id) or product == "optional-wan":
        # Retired locals are not products — no probe, no cache, no NOT_INSTALLED row.
        return VideoFacts(
            product_id=product,
            locality="hosted" if locality == "hosted" else "local",
            details={"retired": True},
        )
    now = time.monotonic()
    cached = _fact_cache.get(product)
    if cached and now - cached[0] < _FACT_TTL_SEC:
        return cached[1]

    adapter_id = adapter_for_product(product)
    facts = VideoFacts(
        product_id=product,
        locality="hosted" if locality == "hosted" else "local",
        adapter_id=adapter_id,
        adapter_registered=_adapter_registered(adapter_id),
        live_submit=bool(adapter_id and adapter_id in LIVE_SUBMIT_ADAPTERS),
    )

    if product in HOSTED_LIVE_ONLY:
        secret = HOSTED_LIVE_ONLY[product]
        facts.credentials_ok = _secret_configured(secret)
        if not facts.credentials_ok:
            facts.credentials_reason = "Provider API Key Missing"
        if product not in {"seedance-2.0", "seedance-2.0-mini", "seedance-2.5"}:
            facts.live_submit = False

    if product.startswith("minimax-h3"):
        # Timeline H3 is Adept Comfy Reference-to-Video, not isolated Route A I2V/T2V.
        health = _comfy_health()
        facts.runtime_ok = bool(health.get("ok"))
        if not facts.runtime_ok:
            facts.runtime_reason = "Comfy Runtime Offline"
        needed = REQUIRED_NODES.get(product) or REQUIRED_NODES["minimax-h3"]
        if not facts.runtime_ok:
            facts.nodes_ok = False
            facts.nodes_reason = "Workflow Node Missing — Comfy Runtime Offline"
        else:
            present = _comfy_nodes()
            missing = [name for name in needed if name not in present]
            facts.nodes_ok = not missing
            if missing:
                facts.nodes_reason = f"Workflow Node Missing — {', '.join(missing)}"
        facts.checkpoint_ok, facts.checkpoint_reason = _adept_h3_ref2v_weights_ok()
        facts.details["comfy"] = health
        facts.details["h3Mechanism"] = "h3_ref2va"
    elif facts.locality == "local":
        components = SETUP_COMPONENTS.get(product)
        if components:
            facts.checkpoint_ok, facts.checkpoint_reason = _verify_components(components)
        else:
            facts.checkpoint_ok = None
        health = _comfy_health()
        facts.runtime_ok = bool(health.get("ok"))
        if not facts.runtime_ok:
            facts.runtime_reason = "Comfy Runtime Offline"
        needed = REQUIRED_NODES.get(product) or ()
        if needed:
            if not facts.runtime_ok:
                facts.nodes_ok = False
                facts.nodes_reason = "Workflow Node Missing — Comfy Runtime Offline"
            else:
                present = _comfy_nodes()
                missing = video_registry.missing_required_nodes(product, present)
                facts.nodes_ok = not missing
                if missing:
                    facts.nodes_reason = f"Workflow Node Missing — {', '.join(missing)}"
        if estimated_vram_gb and health.get("ok") and health.get("vram_total"):
            total_gb = float(health["vram_total"]) / (1024**3)
            # A 32 GB estimate on a 32 GB card is ON_DEMAND, not a missing GPU.
            facts.vram_ok = estimated_vram_gb <= total_gb + 1.0
            if not facts.vram_ok:
                facts.vram_reason = (
                    f"VRAM insufficient — needs ~{estimated_vram_gb:.0f} GB, GPU has {total_gb:.0f} GB"
                )
        facts.details["comfy"] = health
        if facts.runtime_ok and _route_a_vram_resident():
            facts.admission_ok = False
            facts.admission_reason = (
                "GPU admission — MiniMax Route A is resident; Desktop Comfy generators require handoff"
            )

    _fact_cache[product] = (now, facts)
    return facts


def derive_video_readiness(facts: VideoFacts) -> tuple[str, str, bool]:
    """Return (readiness, disabledReason, executable).

    Ready means installed + compatible + runtime available. A model that is
    not currently VRAM-resident can still be Ready / executable (on-demand
    load through the existing execution host). Route A uses a separate
    onDemand flag when its isolated process is down but startable.
    """
    if video_registry.is_retired_local_video(facts.product_id) or facts.product_id == "optional-wan" or facts.details.get("retired"):
        return "Unsupported", "Retired — not a product", False

    if facts.locality == "hosted":
        if facts.product_id == "seedance-kie":
            return "Unsupported", "Unsupported — Kie submit path is not implemented (will not use fal)", False
        if facts.credentials_ok is False:
            return "Requires Setup", facts.credentials_reason or "Provider API Key Missing", False
        if not facts.adapter_registered:
            return "Unsupported", "Unsupported — no Timeline adapter", False
        if not facts.live_submit:
            return "Testing", "Testing — adapter does not call this provider", False
        return "Ready", "", True

    if not facts.adapter_registered:
        if facts.checkpoint_ok is False:
            return "Requires Setup", facts.checkpoint_reason or "Model Not Installed", False
        return "Unsupported", "Unsupported — no Timeline adapter", False

    if facts.checkpoint_ok is False:
        return "Requires Setup", facts.checkpoint_reason or "Checkpoint Missing", False
    if facts.runtime_ok is False:
        return "Runtime Offline", facts.runtime_reason or "Comfy Runtime Offline", False
    if facts.nodes_ok is False:
        return "Requires Setup", facts.nodes_reason or "Workflow Node Missing", False
    if facts.vram_ok is False:
        return "Testing", facts.vram_reason or "VRAM insufficient", False
    if facts.workflow_ok is False:
        return "Testing", facts.workflow_reason or "Workflow graph drift", False
    if facts.admission_ok is False:
        return "Testing", facts.admission_reason or "GPU admission blocked", False
    if not facts.live_submit:
        return "Testing", "Testing — adapter does not execute a runtime job", False
    if facts.product_id in TESTING_UNCERTIFIED:
        return "Testing", "Testing — implementation exists but is not certified for normal use", False
    return "Ready", "", True
