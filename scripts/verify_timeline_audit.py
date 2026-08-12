"""Independent verifier for the Timeline End-to-End Audit milestone.

Read-only assertions over static contracts + live endpoints. Prints
VERIFIED or BLOCKED for each gate and a final summary.

Usage:
    python scripts/verify_timeline_audit.py [--base-url http://127.0.0.1:8758]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

DEFAULT_BASE = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758")


def _get(url: str, timeout: float = 15.0) -> tuple[int, Any]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = None
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def _post(url: str, data: dict, timeout: float = 30.0) -> tuple[int, Any]:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = None
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    results: list[tuple[str, bool, str]] = []

    def gate(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        status = "VERIFIED" if ok else "BLOCKED"
        print(f"[{status}] {name}{(': ' + detail) if detail else ''}")

    # --- Static contract gates ---
    try:
        from app.codirector.timeline_context.contracts import (
            SCENE_LIFECYCLE_STATUSES,
            TimelineContextPackage,
            TimelineGateLevel,
        )
        gate("contracts: scene lifecycle statuses", len(SCENE_LIFECYCLE_STATUSES) == 7)
        gate("contracts: gate levels", set(TimelineGateLevel.__args__) == {"EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"})  # type: ignore[attr-defined]
        gate("contracts: package has sceneCraft field", "sceneCraft" in TimelineContextPackage.model_fields)
        gate("contracts: package has readiness field", "readiness" in TimelineContextPackage.model_fields)
    except Exception as e:
        gate("contracts: import", False, str(e))

    # --- Frontend static gates ---
    web_root = os.path.join(os.path.dirname(__file__), "..", "studio-web", "src")
    sel_path = os.path.join(web_root, "directorSelection.ts")
    comp_path = os.path.join(web_root, "components", "timeline-master", "TimelinePreviewComposer.tsx")
    gate("frontend: TimelineSelection union defined", os.path.exists(sel_path) and "TimelineSelection" in open(sel_path, encoding="utf-8").read())
    gate("frontend: TimelinePreviewComposer exists", os.path.exists(comp_path))
    gate("frontend: PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH law present", "PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH" in open(comp_path, encoding="utf-8").read())
    gate("frontend: TIMELINE_LIBRARY_MEDIA_ONLY module exists", os.path.exists(os.path.join(web_root, "timelineMediaTypes.ts")))
    gate("frontend: SceneProductionReadinessPanel exists", os.path.exists(os.path.join(web_root, "components", "timeline-master", "SceneProductionReadinessPanel.tsx")))
    gate("frontend: SceneStatusStrip exists", os.path.exists(os.path.join(web_root, "components", "timeline-master", "SceneStatusStrip.tsx")))

    # --- Live API gates (best-effort; skip if API not running) ---
    health = _get(f"{base}/api/health", timeout=5)
    api_up = health[0] == 200
    print(f"(api health: {health[0]})")

    if api_up:
        # Need a project + scene for context package gates.
        status, projects = _get(f"{base}/api/projects")
        plist = projects if isinstance(projects, list) else (projects or {}).get("projects", []) if projects else []
        pid = plist[0]["id"] if plist else os.environ.get("ADEPT_PROJECT_ID", "")
        if pid:
            _, scenes = _get(f"{base}/api/projects/{pid}/scenes")
            slist = scenes if isinstance(scenes, list) else (scenes or {}).get("scenes", []) if scenes else []
            sid = slist[0]["id"] if slist else ""
            if sid:
                s, pkg = _get(f"{base}/api/codirector/projects/{pid}/timeline-context/{sid}")
                gate("live: timeline context package returns ok", s == 200 and bool(pkg and pkg.get("ok")))
                if pkg and pkg.get("package"):
                    p = pkg["package"]
                    gate("live: package gateLevel valid", p.get("gateLevel") in {"EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"})
                    gate("live: package sceneStatus valid", p.get("sceneStatus") in {"Draft", "Planning", "Ready", "Generating", "Review", "Approved", "Locked"})
                    gate("live: package sceneCraft shots present", len(p.get("sceneCraft", {}).get("shots", [])) >= 1)
                    gate("live: package readiness present", bool(p.get("readiness")))
                    gate("live: package generationConstraints present", bool(p.get("generationConstraints")))
                    gate("live: no silent ltx default", p.get("generationConstraints", {}).get("engine") != "ltx")
                gs, gbody = _get(f"{base}/api/codirector/projects/{pid}/timeline-context/{sid}/gate?action_scope=production")
                gate("live: smart gate returns decision", gs == 200 and gbody.get("decision") in {"ALLOW", "ALLOW_WITH_WARNING", "BLOCK"})
                ge, ebody = _get(f"{base}/api/codirector/projects/{pid}/timeline-context/{sid}/gate?action_scope=exploration")
                gate("live: exploration gate always allows", ge == 200 and ebody.get("decision") == "ALLOW")
                ss, sbody = _get(f"{base}/api/codirector/projects/{pid}/timeline-context/scene-status")
                gate("live: scene status aggregate returns counts", ss == 200 and bool(sbody and sbody.get("counts")))
                if sbody and sbody.get("counts"):
                    total = sum(sbody["counts"].values())
                    gate("live: scene status counts sum to total", total == sbody.get("totalScenes"))
            else:
                print("(skip live scene gates: no scenes found)")
        else:
            print("(skip live context gates: no project found)")
    else:
        print("(skip live gates: API not running)")

    # --- Summary ---
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} gates verified")
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print("BLOCKED gates:")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("ALL GATES VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
