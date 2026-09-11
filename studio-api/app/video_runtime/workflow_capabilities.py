"""Per-surface local video workflow truth.

Eligibility is surface + model + workflow. A Timeline R2V adapter flag never
decides whether the same family can run T2V or I2V on a CREATE surface.
"""

from __future__ import annotations

from typing import Literal

from ..hosted_providers import video_registry

Surface = Literal["t2v", "i2v", "multiFrame", "r2v"]

# Product → surface → workflow key, derived from the canonical video registry
# (app.hosted_providers.video_registry.surface_workflow_map). Genuine local
# workflows PLUS hosted entries for products with a real provider submit path
# (kling-fal / veo-fal / runway) — the intended new honesty for CREATE
# surfaces. Seedance entries are byte-identical to the historical literal.
_LOCAL_WORKFLOW: dict[str, dict[Surface, str]] = video_registry.surface_workflow_map()  # type: ignore[assignment]

_SEEDANCE_PRODUCTS = frozenset({"seedance-2.0", "seedance-2.5"})

_LTX25_PRODUCTS = frozenset({"ltx-2.5-distilled", "ltx-2.5-full", "ltx-2.5-comfy"})
_MINIMAX_PRODUCTS = frozenset({"minimax-h3", "minimax-h3-i2v-local"})


def _canonical(product_id: str) -> str:
    from ..production_control.video_readiness import canonical_product_id

    return canonical_product_id(product_id) or str(product_id or "").strip()


def workflow_key_for(product_id: str, surface: Surface) -> str | None:
    return _LOCAL_WORKFLOW.get(_canonical(product_id), {}).get(surface)


def _route_a_facts() -> tuple[bool, str, bool]:
    """(weights_ok, reason, runtime_up). Route A may start on Generate."""
    from ..production_control.video_readiness import _minimax_weights_ok, _route_a_listener_up

    ok, reason = _minimax_weights_ok()
    return ok, reason, _route_a_listener_up()


def surface_workflow_status(product_id: str, surface: Surface) -> dict[str, object]:
    """Truth for one model on one surface. Never inherits another surface's flags."""
    product = _canonical(product_id)
    key = workflow_key_for(product, surface)
    if not key:
        return {
            "productId": product,
            "surface": surface,
            "supported": False,
            "installed": False,
            "executable": False,
            "runtime": None,
            "workflowKey": None,
            "readiness": "Unsupported",
            "reason": "No workflow for this surface",
        }

    if product in _MINIMAX_PRODUCTS and key.startswith("route_a."):
        weights_ok, reason, runtime_up = _route_a_facts()
        installed = weights_ok
        executable = weights_ok  # on-demand Route A start is allowed
        readiness = "Ready" if weights_ok else "Requires Setup"
        if weights_ok and not runtime_up:
            readiness = "Available on demand"
        return {
            "productId": product,
            "surface": surface,
            "supported": True,
            "installed": installed,
            "executable": executable,
            "runtime": "route-a",
            "workflowKey": key,
            "readiness": readiness,
            "reason": "" if weights_ok else reason,
        }

    if product in _SEEDANCE_PRODUCTS:
        from ..production_control.video_readiness import HOSTED_LIVE_ONLY, _secret_configured

        secret = HOSTED_LIVE_ONLY.get(product, "fal_api_key")
        creds_ok = _secret_configured(secret)
        executable = creds_ok
        readiness = "Ready" if executable else "Requires Setup"
        return {
            "productId": product,
            "surface": surface,
            "supported": True,
            "installed": creds_ok,
            "executable": executable,
            "runtime": "fal",
            "workflowKey": key,
            "readiness": readiness,
            "reason": "" if executable else "Provider API Key Missing",
            "locality": "hosted",
        }

    # Hosted registry products (Kling / Veo / Runway) with a certified workflow
    # key but no local runtime: honest provider-secret gate, never a fake Ready.
    registration = video_registry.core_registration(product)
    if registration is not None and registration.locality == "hosted" and registration.hosted_secret:
        from ..production_control.video_readiness import _secret_configured

        secret_ok = _secret_configured(registration.hosted_secret)
        executable = bool(secret_ok and (registration.create_live or registration.live_submit))
        if executable:
            readiness = "Ready"
            reason = ""
        elif not secret_ok:
            readiness = "Provider Not Configured"
            reason = "Provider API Key Missing"
        else:
            readiness = "Testing — live submit not certified"
            reason = "Testing — live submit not certified"
        return {
            "productId": product,
            "surface": surface,
            "supported": True,
            "installed": secret_ok,
            "executable": executable,
            "runtime": registration.provider,
            "workflowKey": key,
            "readiness": readiness,
            "reason": reason,
            "locality": "hosted",
        }

    if product in _MINIMAX_PRODUCTS and key == "h3.ref2v":
        from ..production_control.video_readiness import _adept_h3_ref2v_weights_ok, _comfy_health

        weights_ok, reason = _adept_h3_ref2v_weights_ok()
        runtime_ok = bool(_comfy_health().get("ok"))
        executable = bool(weights_ok and runtime_ok)
        readiness = "Ready" if executable else ("Requires Setup" if not weights_ok else "Runtime Offline")
        return {
            "productId": product,
            "surface": surface,
            "supported": True,
            "installed": weights_ok,
            "executable": executable,
            "runtime": "comfy",
            "workflowKey": key,
            "readiness": readiness,
            "reason": "" if executable else (reason or "Comfy Runtime Offline"),
        }

    # Comfy-backed LTX / WAN
    from ..production_control.video_readiness import SETUP_COMPONENTS, _comfy_health, _verify_components

    components = SETUP_COMPONENTS.get(product)
    weights_ok, reason = _verify_components(components) if components else (True, "")
    runtime_ok = bool(_comfy_health().get("ok"))
    executable = bool(weights_ok and runtime_ok)
    readiness = "Ready" if executable else ("Requires Setup" if not weights_ok else "Runtime Offline")
    return {
        "productId": product,
        "surface": surface,
        "supported": True,
        "installed": weights_ok,
        "executable": executable,
        "runtime": "comfy",
        "workflowKey": key,
        "readiness": readiness,
        "reason": "" if executable else (reason or "Comfy Runtime Offline"),
    }


def supports_surface(product_id: str, surface: Surface) -> bool:
    return bool(surface_workflow_status(product_id, surface).get("supported"))


def supports_any_local_surface(product_id: str) -> bool:
    """True when the product has at least one workflow record in the canonical
    video registry — local or hosted (the name predates hosted entries)."""
    return bool(_LOCAL_WORKFLOW.get(_canonical(product_id)))
