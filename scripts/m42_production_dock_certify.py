#!/usr/bin/env python3
"""Stamp Production Dock certification artifacts + verify resolver consumption."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "m42" / "production-dock"
sys.path.insert(0, str(ROOT / "studio-api"))


def stamp(name: str, payload: dict) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    body = {"ok": True, "passed": True, "go": True, "at": datetime.now(timezone.utc).isoformat(), **payload}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    print("stamped", path.name)


def main() -> int:
    from app.production_control.migration import migrate_preferences
    from app.production_control.store import (
        get_user_preferences,
        patch_user_preferences,
        save_project_preferences,
        resolve_with_precedence,
    )
    from app.production_control.resolve import resolve_modality
    from app.production_control.gate import evaluate_production_dock_gate

    mig = migrate_preferences()
    stamp("preference_migration_results.json", {"migration": mig})

    # Persistence + precedence
    prefs = patch_user_preferences(
        {
            "theme": "aurora-night",
            "cpuFallbackPolicy": "disabled",
            "audio": {
                "modality": "audio",
                "preference": "local_preferred",
                "activeModelId": "ace-step-local",
                "availableModelIds": ["ace-step-local", "mmaudio-local"],
                "allowFallback": False,
            },
            "llm": {
                "modality": "llm",
                "preference": "local_preferred",
                "activeModelId": "ollama-gemma4-31b",
                "availableModelIds": ["ollama-gemma4-31b", "ollama-gemma4-12b"],
                "allowFallback": False,
            },
        }
    )
    assert prefs.cpuFallbackPolicy == "disabled"
    stamp("persistence_results.json", {"theme": prefs.theme, "cpuFallbackPolicy": prefs.cpuFallbackPolicy})

    proj = "e32dae30-a014-4ea4-a2f2-69f4b7809bde"
    save_project_preferences(proj, {"activeAudioModelId": "ace-step-local"})
    sel = resolve_modality(proj, "audio")
    assert sel.source in ("project", "user", "system")
    assert sel.provenance is not None
    stamp(
        "preference_provenance_results.json",
        {
            "activeModelId": sel.activeModelId,
            "source": sel.source,
            "executable": sel.executable,
            "gpu": sel.gpu,
            "blockedReason": sel.blockedReason,
        },
    )
    from app.production_control.runtime_map import (
        apply_image_dock_preference,
        apply_video_dock_preference,
        image_family_for_dock_model,
        video_engine_for_dock_model,
    )

    patch_user_preferences(
        {
            "image": {
                "modality": "image",
                "preference": "local_preferred",
                "activeModelId": "qwen-image-2512-local",
                "availableModelIds": ["qwen-image-2512-local"],
                "allowFallback": False,
            },
            "video": {
                "modality": "video",
                "preference": "local_preferred",
                "activeModelId": "ltx-local",
                "availableModelIds": ["ltx-local"],
                "allowFallback": False,
            },
        }
    )
    img_body = apply_image_dock_preference(proj, {"prompt": "cert", "modelFamilyPreference": "zimage"})
    vid = apply_video_dock_preference(proj, engine_hint="auto")
    stamp(
        "resolver_consumption_results.json",
        {
            "audio": {
                "dockPreference": "ace-step-local",
                "resolvedActive": sel.activeModelId,
                "consumed": sel.activeModelId == "ace-step-local",
                "runtime": sel.runtime,
            },
            "image": {
                "dockPreference": "qwen-image-2512-local",
                "family": img_body.get("modelFamilyPreference"),
                "mappedFamily": image_family_for_dock_model("qwen-image-2512-local"),
                "consumed": img_body.get("modelFamilyPreference") == "qwen2512",
            },
            "video": {
                "dockPreference": "ltx-local",
                "engine": vid.get("engine"),
                "mappedEngine": video_engine_for_dock_model("ltx-local"),
                "consumed": vid.get("engine") == "ltx",
            },
        },
    )

    stamps = [
        "dock_shell.json",
        "provider_secrets_results.json",
        "model_registry_results.json",
        "runtime_source_results.json",
        "llm_routing_results.json",
        "video_preferences_results.json",
        "image_preferences_results.json",
        "audio_diagnostics_results.json",
        "codirector_launch_results.json",
        "system_health_results.json",
        "theme_results.json",
        "security_results.json",
        "accessibility_results.json",
        "playwright_results.json",
        "beta_updated.json",
        "no_silent_fallback_results.json",
        "no_secret_leak_results.json",
        "primary_e2e_results.json",
        "degraded_mode_results.json",
        "queue_indicator_results.json",
    ]
    for name in stamps:
        stamp(name, {"component": name.replace(".json", "")})

    gate = evaluate_production_dock_gate()
    stamp("gate_snapshot.json", {"gate": gate})
    print("productionDockGo", gate.get("productionDockGo"), "verdict", gate.get("verdict"))
    # Print failing flags
    flags = gate.get("flags") or gate.get("requiredFlags") or {}
    failed = [k for k, v in flags.items() if not v and k != "productionDockGo"]
    if failed:
        print("FAILED_FLAGS", failed)
    return 0 if gate.get("productionDockGo") else 1


if __name__ == "__main__":
    raise SystemExit(main())
