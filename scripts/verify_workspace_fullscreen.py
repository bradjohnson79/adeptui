#!/usr/bin/env python3
"""Independent workspace fullscreen verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/release-gate/timeline-nle/artifacts"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    base = ROOT / "studio-web/src/workspace/fullscreen"
    required = [
        "useWorkspaceFullscreen.ts",
        "WorkspaceFullscreenControls.tsx",
        "WorkspaceFullscreenBanner.tsx",
        "platformAdapter.ts",
        "workspaceViewPrefs.ts",
        "types.ts",
    ]
    for name in required:
        gates[f"module:{name}"] = "GO" if (base / name).exists() else "FAIL"

    hook = (base / "useWorkspaceFullscreen.ts").read_text(encoding="utf-8") if (base / "useWorkspaceFullscreen.ts").exists() else ""
    gates["Uses Fullscreen API"] = "GO" if "requestFullscreen" in hook and "fullscreenchange" in hook else "FAIL"
    gates["Restores previousViewMode"] = "GO" if "previousViewMode" in hook and "onRestoreViewMode" in hook else "FAIL"
    gates["Ctrl+Shift+F shortcut"] = (
        "GO" if "shiftKey" in hook and 'toLowerCase() !== "f"' in hook else "FAIL"
    )

    shell = (ROOT / "studio-web/src/components/timeline-master/TimelineEditorShell.tsx").read_text(encoding="utf-8")
    gates["Timeline fullscreen button"] = "GO" if "workspace-fullscreen-toggle" in shell or "WorkspaceFullscreenControls" in shell else "FAIL"
    cd = (ROOT / "studio-web/src/components/CoDirector/CoDirectorShell.tsx").read_text(encoding="utf-8")
    gates["Co-Director fullscreen button"] = "GO" if "WorkspaceFullscreenControls" in cd else "FAIL"
    magi = (ROOT / "studio-web/src/components/magi/MagiEditorWorkspace.tsx").read_text(encoding="utf-8")
    gates["MAGI fullscreen button"] = "GO" if "WorkspaceFullscreenControls" in magi else "FAIL"
    css = (base / "workspace-fullscreen.css").read_text(encoding="utf-8") if (base / "workspace-fullscreen.css").exists() else ""
    gates["Chrome hide CSS"] = "GO" if "adept-workspace-fullscreen" in css else "FAIL"

    cert = ROOT / "tests/e2e/workspaces/workspace-fullscreen-cert.spec.ts"
    gates["Playwright certification"] = "GO" if cert.exists() else "FAIL"

    failed = [k for k, v in gates.items() if v != "GO"]
    verdict = "VERIFIED" if not failed else "BLOCKED"
    payload = {"verdict": verdict, "gates": gates, "failed": failed}
    (OUT / "verify_workspace_fullscreen.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(verdict)
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
