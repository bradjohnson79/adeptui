"""Test-only control endpoints. Mounted only when STUDIO_E2E is enabled."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/e2e", tags=["e2e"])


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES")


@router.get("/status")
def e2e_status() -> dict[str, Any]:
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    return {
        "ok": True,
        "studio_e2e": True,
        "data_dir": str(__import__("app.config", fromlist=["settings"]).settings.data_dir),
        "pack_provider": os.environ.get("ADEPT_PACK_PROVIDER"),
        "fixture_base_url": os.environ.get("ADEPT_PACK_FIXTURE_BASE_URL"),
    }


@router.post("/pack-source-override")
def e2e_pack_source_override(body: dict[str, Any]) -> dict[str, Any]:
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    pack_id = str(body.get("pack_id") or "").strip()
    url = body.get("url")
    if not pack_id:
        raise HTTPException(400, "pack_id is required")
    from ..setup.pack_manifests import clear_manifest_cache, set_source_override
    from ..setup.pack_settings import clear_pack_settings_cache

    set_source_override(pack_id, str(url) if url else None)
    clear_manifest_cache()
    clear_pack_settings_cache()
    return {"pack_id": pack_id, "url": url}


@router.post("/clear-pack-overrides")
def e2e_clear_pack_overrides() -> dict[str, Any]:
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    from ..setup.pack_manifests import clear_manifest_cache, clear_source_overrides
    from ..setup.pack_settings import clear_pack_settings_cache

    clear_source_overrides()
    clear_manifest_cache()
    clear_pack_settings_cache()
    return {"cleared": True}


@router.post("/recover-operations")
def e2e_recover_operations() -> dict[str, Any]:
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    from ..setup.operations import recover_stale_operations

    recovered = recover_stale_operations()
    return {"recovered": recovered}


@router.post("/clear-component-location")
def e2e_clear_component_location(body: dict[str, Any]) -> dict[str, Any]:
    """Clear a component install/link path so Retry starts from a clean destination."""
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    component_id = str(body.get("component_id") or "").strip()
    if not component_id:
        raise HTTPException(400, "component_id is required")
    from ..setup.state import update_state

    def mutate(state: dict[str, Any]) -> None:
        locations = state.setdefault("model_locations", {})
        locations.pop(component_id, None)
        packs = state.setdefault("pack_installs", {})
        packs.pop(component_id, None)
        status = state.setdefault("status", {})
        if component_id in status and isinstance(status[component_id], dict):
            status[component_id].pop("installation_path", None)
            status[component_id].pop("path", None)
            status[component_id]["status"] = "not_installed"

    update_state(mutate)
    return {"component_id": component_id, "cleared": True}


@router.post("/seed-stale-operation")
def e2e_seed_stale_operation(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Insert an in-flight setup operation so restart recovery can be asserted."""
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    payload = body or {}
    component_id = str(payload.get("component_id") or "pack_essential_photoreal")
    phase = str(payload.get("phase") or "configuring")
    from ..setup.operations import registry

    op = registry.create("component_action", [component_id])
    registry.update(
        op["operation_id"],
        status=str(payload.get("status") or "running"),
        phase=phase,
        stage=str(payload.get("stage") or "Configuring…"),
        progress=0.35,
    )
    return registry.snapshot(op["operation_id"])


@router.post("/codirector/scenario")
def e2e_codirector_scenario(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Override ADEPT_CODIRECTOR_MOCK_SCENARIO for the running process (mock provider only).

    The mock provider re-reads this env var on every call, so Playwright can flip between
    healthy / connection_refused / no_models / model_missing / timeout / slow mid-suite
    without restarting the API process.
    """
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    payload = body or {}
    scenario = payload.get("scenario")
    if scenario:
        os.environ["ADEPT_CODIRECTOR_MOCK_SCENARIO"] = str(scenario)
    else:
        os.environ.pop("ADEPT_CODIRECTOR_MOCK_SCENARIO", None)
    return {"scenario": os.environ.get("ADEPT_CODIRECTOR_MOCK_SCENARIO")}


@router.post("/feature-flags")
def e2e_feature_flags(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Flip `STUDIO_FEATURE_*` flags for the running process (E2E only).

    Some flags change which surface the UI renders at all — M2.14's unified workspace
    replaces the Co-Director conversation — so a suite-wide env setting would force every
    other chat spec to run against a different screen. This lets one spec prove both the ON
    and OFF states and hand the process back the way it found it. Defaults in
    `feature_flags.py` are untouched: an unset flag is still False.
    """
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    from dataclasses import fields as dataclass_fields

    from .. import feature_flags as feature_flags_mod

    payload = (body or {}).get("flags")
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(400, "flags object is required, e.g. {\"flags\": {\"codirector_unified_experience_v1\": true}}")

    known = {f.name for f in dataclass_fields(feature_flags_mod.FeatureFlags)}
    applied: dict[str, Any] = {}
    for name, value in payload.items():
        key = str(name).strip()
        if key not in known:
            raise HTTPException(400, f"unknown feature flag: {key}")
        env_name = f"STUDIO_FEATURE_{key.upper()}"
        if value is None:
            os.environ.pop(env_name, None)
            applied[key] = None
        else:
            os.environ[env_name] = "1" if value else "0"
            applied[key] = bool(value)

    # Several modules bound `feature_flags` by value at import time, so the live singleton
    # is mutated in place rather than replaced — otherwise those readers keep the old view.
    refreshed = feature_flags_mod.FeatureFlags.from_env(os.environ)
    singleton = feature_flags_mod.feature_flags
    for field in dataclass_fields(feature_flags_mod.FeatureFlags):
        object.__setattr__(singleton, field.name, getattr(refreshed, field.name))
    return {
        "applied": applied,
        "flags": {
            f.name: bool(getattr(singleton, f.name))
            for f in dataclass_fields(feature_flags_mod.FeatureFlags)
            if f.name in applied
        },
    }


@router.post("/cli-mock")
def e2e_cli_mock(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Set ADEPT_CLI_MOCK_JSON for Download Sources detection (process-local)."""
    if not e2e_enabled():
        raise HTTPException(404, "E2E controls disabled")
    import json
    import os

    payload = body or {}
    if payload.get("clear"):
        os.environ.pop("ADEPT_CLI_MOCK_JSON", None)
        return {"cleared": True}
    os.environ["ADEPT_CLI_MOCK_JSON"] = json.dumps(payload)
    return {"ok": True, "mock": payload}
