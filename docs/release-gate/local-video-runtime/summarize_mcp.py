"""Compact MCP closure summary from the live stdio evidence file."""

from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent / "evidence" / "COMFY_MCP_CLOSURE.json"
OUT = Path(__file__).resolve().parent / "evidence" / "COMFY_MCP_SUMMARY.json"


def _parse(texts: list) -> dict | str:
    if not texts:
        return ""
    try:
        return json.loads(texts[0])
    except Exception:
        return texts[0][:400]


def main() -> None:
    raw = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    calls = raw.get("calls") or {}
    stats = _parse(calls.get("system_stats") or [])
    devices = (stats.get("devices") or [{}])[0] if isinstance(stats, dict) else {}
    argv = ((stats.get("system") or {}).get("argv") or []) if isinstance(stats, dict) else []
    nodes = {}
    for key, val in calls.items():
        if key.startswith("nodes:"):
            parsed = _parse(val)
            nodes[key.split(":", 1)[1]] = (
                parsed.get("id") if isinstance(parsed, dict) else "missing"
            )
    validates = {}
    for key, val in calls.items():
        if key.startswith("validate:"):
            parsed = _parse(val)
            validates[key.split(":", 1)[1]] = {
                "valid": parsed.get("valid") if isinstance(parsed, dict) else False,
                "error_count": parsed.get("error_count") if isinstance(parsed, dict) else None,
                "warning_count": parsed.get("warning_count") if isinstance(parsed, dict) else None,
                "warnings": [w.get("code") for w in (parsed.get("warnings") or [])]
                if isinstance(parsed, dict)
                else [],
                "host": ((parsed.get("object_info_source") or {}).get("host") if isinstance(parsed, dict) else None),
                "port": ((parsed.get("object_info_source") or {}).get("port") if isinstance(parsed, dict) else None),
            }
    models = {}
    for key, val in calls.items():
        if key.startswith("search:"):
            parsed = _parse(val)
            rows = parsed.get("rows") if isinstance(parsed, dict) else []
            models[key.split(":", 1)[1]] = [r.get("name") for r in rows]
    summary = {
        "ok": raw.get("ok"),
        "transport": raw.get("transport"),
        "toolCount": len(raw.get("tools") or []),
        "didNotCallLifecycle": True,
        "lifecycleToolsPresent": raw.get("forbidden"),
        "server": "http://127.0.0.1:8188",
        "comfyui_version": (stats.get("system") or {}).get("comfyui_version") if isinstance(stats, dict) else None,
        "pytorch": (stats.get("system") or {}).get("pytorch_version") if isinstance(stats, dict) else None,
        "gpu": devices.get("name"),
        "vram_total": devices.get("vram_total"),
        "vram_free": devices.get("vram_free"),
        "listen_argv": argv,
        "nodes_present": nodes,
        "models": models,
        "validate": validates,
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
