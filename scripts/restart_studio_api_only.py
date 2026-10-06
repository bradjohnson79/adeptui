"""Thin client: ask Adept Background Services to recycle Studio API only.

Do not spawn, adopt, or stop Comfy. POST 127.0.0.1:8759/restart-api.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from runtime_supervisor.control_client import call_control, control_plane_reachable  # noqa: E402

if not control_plane_reachable():
    print("ERROR: Adept Background Services manager is not running on :8759.")
    sys.exit(1)

result = call_control("POST", "/restart-api", timeout=180.0)
ok = bool(result.get("ok"))
print(result.get("message") or ("restart-api ok" if ok else "restart-api failed"))
if result.get("oldPid") or result.get("newPid"):
    print(f"  oldPid={result.get('oldPid')} newPid={result.get('newPid')} comfyPid={result.get('comfyPid')} unchanged={result.get('comfyPidUnchanged')}")
sys.exit(0 if ok else 1)
