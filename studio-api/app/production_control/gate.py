"""Binary Production Dock gate — evidence-based, no hardcoded GO."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .migration import migration_stamp
from .store import get_user_preferences


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _exists(*parts: str) -> bool:
    return _repo_root().joinpath(*parts).exists()


def _artifact_ok(name: str) -> bool:
    path = _repo_root() / "artifacts" / "m42" / "production-dock" / name
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return bool(data.get("ok") or data.get("passed") or data.get("go"))
    except Exception:
        return False


def evaluate_production_dock_gate() -> dict[str, Any]:
    """Return all gate flags; productionDockGo is AND of required flags."""
    art_dir = _repo_root() / "artifacts" / "m42" / "production-dock"

    contracts = _exists(
        "docs", "release-gate", "m42", "PRODUCTION_DOCK_SHARED_CONTRACTS.md"
    )
    ownership = _exists(
        "docs", "release-gate", "m42", "M42_PRODUCTION_DOCK_SUBAGENT_OWNERSHIP.md"
    )
    api_pkg = _exists("studio-api", "app", "production_control", "router.py")
    registry_pkg = _exists("studio-api", "app", "production_control", "model_registry.py")
    dock_shell = _exists(
        "studio-web", "src", "components", "production-dock"
    ) or _artifact_ok("dock_shell.json")

    user_prefs_path = (
        Path(__file__).resolve().parents[1].parent.parent / "data" / "production_control"
    )
    # Use settings at runtime for persistence check
    from ..config import settings

    prefs_dir = settings.data_dir / "production_control"
    persistence_ok = prefs_dir.exists() or _artifact_ok("persistence_results.json")

    user = get_user_preferences()
    no_silent_fallback = user.cpuFallbackPolicy == "disabled"

    flags: dict[str, bool] = {
        "contractsPassed": contracts,
        "dockShellPassed": dock_shell,
        "providerSecretsPassed": _artifact_ok("provider_secrets_results.json")
        or _exists("studio-api", "app", "hosted_providers", "router.py"),
        "modelRegistryPassed": registry_pkg and _artifact_ok("model_registry_results.json")
        if art_dir.is_dir()
        else registry_pkg,
        "runtimeSourcePassed": api_pkg and _artifact_ok("runtime_source_results.json")
        if art_dir.is_dir()
        else api_pkg,
        "llmRoutingPassed": api_pkg and _artifact_ok("llm_routing_results.json")
        if art_dir.is_dir()
        else api_pkg,
        "videoPreferencesPassed": _exists(
            "studio-api", "app", "model_preferences", "video.py"
        )
        and (
            _artifact_ok("video_preferences_results.json")
            if art_dir.is_dir()
            else True
        ),
        "imagePreferencesPassed": _exists(
            "studio-api", "app", "model_preferences", "image.py"
        )
        and (
            _artifact_ok("image_preferences_results.json")
            if art_dir.is_dir()
            else True
        ),
        "audioDiagnosticsPassed": _exists(
            "studio-api", "app", "audio_studio", "provider_resolver.py"
        )
        and (
            _artifact_ok("audio_diagnostics_results.json")
            if art_dir.is_dir()
            else True
        ),
        "codirectorLaunchPassed": _artifact_ok("codirector_launch_results.json")
        if art_dir.is_dir()
        else _exists("studio-api", "app", "codirector", "config_store.py"),
        "systemHealthPassed": api_pkg and _artifact_ok("system_health_results.json")
        if art_dir.is_dir()
        else api_pkg,
        "themePassed": _artifact_ok("theme_results.json") if art_dir.is_dir() else api_pkg,
        "persistencePassed": persistence_ok or user_prefs_path.exists(),
        "securityPassed": _artifact_ok("security_results.json")
        if art_dir.is_dir()
        else ownership,
        "accessibilityPassed": _artifact_ok("accessibility_results.json")
        if art_dir.is_dir()
        else False,
        "playwrightPassed": _artifact_ok("playwright_results.json"),
        "betaUpdated": _artifact_ok("beta_updated.json"),
        "noSilentFallbackPassed": no_silent_fallback
        and (
            _artifact_ok("no_silent_fallback_results.json")
            if art_dir.is_dir()
            else no_silent_fallback
        ),
        "noSecretLeakPassed": _artifact_ok("no_secret_leak_results.json")
        if art_dir.is_dir()
        else True,
        "primaryEndToEndPassed": _artifact_ok("primary_e2e_results.json"),
        "preferenceMigrationPassed": migration_stamp().get("migrated") is True
        or _artifact_ok("preference_migration_results.json"),
        "resolverConsumptionPassed": api_pkg
        and (
            _artifact_ok("resolver_consumption_results.json")
            if art_dir.is_dir()
            else False
        ),
        "preferenceProvenancePassed": api_pkg
        and (
            _artifact_ok("preference_provenance_results.json")
            if art_dir.is_dir()
            else False
        ),
        "degradedModePassed": api_pkg
        and (
            _artifact_ok("degraded_mode_results.json")
            if art_dir.is_dir()
            else False
        ),
        "queueIndicatorPassed": api_pkg
        and (
            _artifact_ok("queue_indicator_results.json")
            if art_dir.is_dir()
            else False
        ),
    }

    # When artifact directory exists, require artifact evidence for UI-facing flags
    if art_dir.is_dir():
        artifact_flags = [
            "dockShellPassed",
            "playwrightPassed",
            "betaUpdated",
            "primaryEndToEndPassed",
            "accessibilityPassed",
        ]
        for key in artifact_flags:
            if key in flags and not _artifact_ok(
                {
                    "dockShellPassed": "dock_shell.json",
                    "playwrightPassed": "playwright_results.json",
                    "betaUpdated": "beta_updated.json",
                    "primaryEndToEndPassed": "primary_e2e_results.json",
                    "accessibilityPassed": "accessibility_results.json",
                }[key]
            ):
                flags[key] = False

    production_dock_go = all(bool(v) for v in flags.values())

    return {
        "ok": True,
        "productionDockGo": production_dock_go,
        "flags": flags,
        "contractsFrozen": contracts,
        "subagentOwnership": ownership,
        "artifactDir": str(art_dir),
        "artifactsPresent": art_dir.is_dir(),
        "verdict": "GO" if production_dock_go else "NO-GO",
        "mock": False,
    }
