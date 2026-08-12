#!/usr/bin/env python3
"""Archive ComfyUI / LTX / still-engine preflight for M3.0h local-first."""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30h-local-first" / "preflight"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "studio-api"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, payload) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _http_json(url: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


def main() -> int:
    from app.config import settings
    from app.setup.diagnostics import verify_component
    from app.workflows.readiness import workflow_readiness

    components = {}
    for cid in ("comfyui", "ltx_checkpoint", "zimage_models", "wan_models"):
        try:
            r = verify_component(cid)
            components[cid] = {
                "healthy": bool(getattr(r, "healthy", False)),
                "summary": getattr(r, "summary", None) or str(r),
            }
        except Exception as exc:
            components[cid] = {"healthy": False, "error": str(exc)}

    readiness = {}
    for wid in ("ltx.scene", "ltx.simple_i2v"):
        try:
            readiness[wid] = workflow_readiness(wid)
        except Exception as exc:
            readiness[wid] = {"status": "error", "error": str(exc)}

    api = _http_json("http://127.0.0.1:8742/api/health")
    comfy = _http_json("http://127.0.0.1:8188/system_stats")

    still_preference = "zimage" if components.get("zimage_models", {}).get("healthy") else "alternate_or_blocked"
    ltx_ready = bool(components.get("ltx_checkpoint", {}).get("healthy"))
    payload = {
        "recordedAt": _now(),
        "ltxCheckpointSetting": settings.ltx_checkpoint,
        "components": components,
        "workflowReadiness": readiness,
        "apiHealth": api,
        "comfySystemStats": comfy if isinstance(comfy, dict) else {"raw": comfy},
        "preferredStillEngine": still_preference,
        "certifiedVideoEngine": "ltx-2.3",
        "localRuntime": "READY" if ltx_ready else "LOCAL_RUNTIME_BLOCKED",
        "falPolicy": "no_new_paid_submission",
        "historicalFalSubmissionCount": 1,
        "m30hLocalCertificationFalSubmissionCount": 0,
    }
    _write("comfy-ltx-preflight.json", payload)
    print(json.dumps({"ok": True, "localRuntime": payload["localRuntime"], "out": str(OUT)}, indent=2))
    return 0 if ltx_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
