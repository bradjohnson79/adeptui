"""Sync registry Draft/Deferred/Blocked from discovery — never fabricates Certified."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model_discovery import discover_modern_image_models

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY = _REPO_ROOT / "config" / "image-workflows" / "certified-registry.json"


def sync_registry_status_from_discovery(*, dry_run: bool = False) -> dict[str, Any]:
    discovery = discover_modern_image_models()
    families = discovery.get("families") or {}
    reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    changes: list[dict[str, str]] = []
    for entry in reg.get("entries") or []:
        status = entry.get("status")
        if status == "Certified":
            continue  # never demote or invent
        fam = str(entry.get("modelFamily") or entry.get("engine") or "")
        info = families.get(fam) or {}
        key = entry.get("workflowKey")
        if fam == "imagen":
            new_status = "Draft" if info.get("credentialConfigured") else "Blocked"
            reason = info.get("reason") or entry.get("limitations", [""])[0]
        elif fam in {"flux", "qwen"}:
            new_status = "Draft" if info.get("installed") else "Deferred"
            reason = info.get("reason") or ""
        elif fam == "zimage":
            # Required keys stay Certified if already; others Draft/Blocked by install
            new_status = "Draft" if info.get("installed") else "Blocked"
            reason = info.get("reason") or ""
        elif fam == "krea2":
            # Krea 2 entries stay at their registry-declared status (Draft) until the
            # Phase C live certification records evidence — discovery alone never
            # promotes, and gated/missing weights must not demote a cert-in-progress.
            continue
        else:
            continue
        if status != new_status:
            changes.append({"workflowKey": key, "from": status, "to": new_status})
            entry["status"] = new_status
            if reason and isinstance(entry.get("limitations"), list):
                if entry["limitations"]:
                    entry["limitations"][0] = reason
                else:
                    entry["limitations"] = [reason]
    if changes and not dry_run:
        _REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        from .certified_registry import reload_registry

        reload_registry()
    return {"changes": changes, "discoveryComplete": True}
