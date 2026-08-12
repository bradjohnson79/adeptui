"""Project image generation history persistence (M42 W3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .store import read_json, write_json


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_history(project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    data = read_json(project_id, "history.json", {"entries": []})
    rec = {
        "recordedAt": _now(),
        **entry,
    }
    data.setdefault("entries", []).insert(0, rec)
    data["entries"] = data["entries"][:500]
    # Prompt history (unique accepted prompts)
    prompts = data.setdefault("prompts", [])
    ap = entry.get("prompt") or (entry.get("promptIntel") or {}).get("acceptedPrompt")
    if ap and ap not in prompts:
        prompts.insert(0, ap)
        data["prompts"] = prompts[:100]
    write_json(project_id, "history.json", data)
    return rec


def list_history(project_id: str, *, limit: int = 50) -> dict[str, Any]:
    data = read_json(project_id, "history.json", {"entries": [], "prompts": []})
    return {
        "entries": list(data.get("entries") or [])[:limit],
        "prompts": list(data.get("prompts") or [])[:50],
    }


def list_prompt_history(project_id: str) -> list[str]:
    return list_history(project_id).get("prompts") or []
