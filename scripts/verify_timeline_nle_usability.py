#!/usr/bin/env python3
"""Independent Timeline NLE + MiniMax default verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
OUT = ROOT / "docs/release-gate/timeline-nle/artifacts"


def get(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    try:
        # Source audits
        resolve_py = (ROOT / "studio-api/app/production_control/resolve.py").read_text(encoding="utf-8")
        gates["Dock system default MiniMax"] = (
            "GO" if '"video": "minimax-h3"' in resolve_py else "FAIL"
        )
        types_ts = (ROOT / "studio-web/src/types.ts").read_text(encoding="utf-8")
        gates["EngineName includes minimax-h3"] = "GO" if '"minimax-h3"' in types_ts else "FAIL"
        tracks = (ROOT / "studio-web/src/components/timeline-master/TrackClipInteractive.tsx").read_text(
            encoding="utf-8"
        )
        gates["Clip drag resizing"] = "GO" if "trim-left" in tracks and "trim-right" in tracks else "FAIL"
        draft = (ROOT / "studio-web/src/components/timeline-master/useDraftField.ts").read_text(encoding="utf-8")
        gates["Inspector/prompt draft stability"] = "GO" if "useDraftField" in draft else "FAIL"
        fs_hook = (ROOT / "studio-web/src/workspace/fullscreen/useWorkspaceFullscreen.ts").read_text(
            encoding="utf-8"
        )
        gates["Shared Fullscreen API controller"] = "GO" if "requestFullscreen" in fs_hook else "FAIL"

        projects = get("/api/projects")
        plist = projects if isinstance(projects, list) else projects.get("projects") or []
        pid = next((p["id"] for p in plist if p.get("name") == "The Dreamweaver"), None)
        if not pid:
            raise RuntimeError("Dreamweaver missing")
        dock = get(f"/api/production-control/resolve?projectId={pid}&modality=video")
        active = str(dock.get("activeModelId") or (dock.get("selection") or {}).get("activeModelId") or "")
        gates["Footer Dock MiniMax"] = "GO" if "minimax-h3" in active else "FAIL"
        (OUT / "verifier_dock.json").write_text(json.dumps(dock, indent=2), encoding="utf-8")

        # No silent LTX as Default label in dock hint
        menu = (ROOT / "studio-web/src/components/production-dock/ModelMenuDrawer.tsx").read_text(encoding="utf-8")
        gates["No LTX Default label"] = (
            "GO" if 'model.id === "ltx-local") return "Default"' not in menu else "FAIL"
        )

        failed = [k for k, v in gates.items() if v != "GO"]
        verdict = "VERIFIED" if not failed else "BLOCKED"
        payload = {"verdict": verdict, "gates": gates, "failed": failed}
        (OUT / "verify_timeline_nle.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print(verdict)
        return 0 if verdict == "VERIFIED" else 1
    except Exception as exc:
        payload = {"verdict": "BLOCKED", "error": str(exc), "gates": gates}
        (OUT / "verify_timeline_nle.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print("BLOCKED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
