"""One-time migration from legacy preference stores."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..codirector.config_store import load_config
from .store import get_user_preferences, patch_user_preferences

_STAMP_PATH = settings.data_dir / "production_control" / "migration_stamp.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def migration_stamp() -> dict[str, Any]:
    if not _STAMP_PATH.is_file():
        return {"migrated": False, "migratedAt": None, "sources": []}
    try:
        data = json.loads(_STAMP_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"migrated": False}
    except Exception:
        return {"migrated": False, "migratedAt": None, "sources": []}


def _write_stamp(sources: list[str]) -> dict[str, Any]:
    stamp = {"migrated": True, "migratedAt": _now(), "sources": sources}
    _STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STAMP_PATH.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return stamp


def _read_theme_legacy() -> str | None:
    """Best-effort read of UI theme from workspace prefs if present."""
    candidates = [
        settings.data_dir / "workspace_prefs.json",
        settings.data_dir / "ui" / "theme.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                theme = data.get("theme") or data.get("uiTheme")
                if theme in ("aurora-night", "aurora-day", "system"):
                    return theme
        except Exception:
            continue
    return None


def migrate_preferences(*, force: bool = False) -> dict[str, Any]:
    """Migrate codirector_config, hosted_providers prefs, and theme once."""
    stamp = migration_stamp()
    if stamp.get("migrated") and not force:
        return {"ok": True, "alreadyMigrated": True, "stamp": stamp, "changes": []}

    current = get_user_preferences()
    changes: list[str] = []
    patch: dict[str, Any] = {}

    # codirector_config.json → llm routing
    codirector = load_config()
    selected = codirector.get("selectedModel") or codirector.get("primaryModel")
    if selected and not current.llm.activeModelId:
        llm_id = "ollama-gemma4-31b" if "31b" in str(selected).lower() else "ollama-gemma4-12b"
        patch["llm"] = {
            "modality": "llm",
            "activeModelId": llm_id,
            "availableModelIds": [llm_id],
        }
        changes.append(f"codirector_config.selectedModel→llm.activeModelId={llm_id}")

    # hosted_providers/preferences.json → defaultHostedProviderId
    hosted_path = settings.data_dir / "hosted_providers" / "preferences.json"
    hosted: dict[str, Any] = {}
    if hosted_path.is_file():
        try:
            hosted = json.loads(hosted_path.read_text(encoding="utf-8"))
        except Exception:
            hosted = {}
    if not isinstance(hosted, dict):
        hosted = {}
    pref = str(hosted.get("preferredProvider") or "automatic")
    if pref != "automatic" and not current.defaultHostedProviderId:
        patch["defaultHostedProviderId"] = pref
        changes.append(f"hosted_providers.preferredProvider→defaultHostedProviderId={pref}")

    # theme legacy
    theme = _read_theme_legacy()
    if theme and current.theme == "aurora-night" and theme != "aurora-night":
        patch["theme"] = theme
        changes.append(f"legacy.theme→theme={theme}")

    sources = ["codirector_config.json", "hosted_providers/preferences.json"]
    if theme:
        sources.append("legacy.theme")

    if patch:
        patch_user_preferences(patch)
    elif not stamp.get("migrated"):
        # Still stamp even if nothing to migrate — idempotent marker
        pass

    new_stamp = _write_stamp(sources)
    return {
        "ok": True,
        "alreadyMigrated": bool(stamp.get("migrated")),
        "changes": changes,
        "stamp": new_stamp,
        "mock": False,
    }
