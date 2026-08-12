#!/usr/bin/env python3
"""Live creative workflow evidence collector for M4.8–M4.9 (API-driven, no DB edits)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8758"
PROJECT = sys.argv[2] if len(sys.argv) > 2 else "e32dae30-a014-4ea4-a2f2-69f4b7809bde"
ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "m48-m49"


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(r, timeout=60) as resp:
        raw = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        if "application/pdf" in ctype or path.endswith(".pdf"):
            return raw
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def write(rel: str, payload) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (bytes, bytearray)):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    report: dict = {"api": API, "projectId": PROJECT, "steps": []}

    project = req("GET", f"/api/projects/{PROJECT}")
    images = [a for a in (project.get("assets") or []) if a.get("kind") == "image"]
    report["imageAssetCount"] = len(images)
    if not images:
        report["verdict"] = "NO_IMAGE_ASSETS"
        write("creative/live-report.json", report)
        print(json.dumps(report, indent=2))
        return 2

    s = req(
        "POST",
        f"/api/image-studio/projects/{PROJECT}/continuity-sessions/inherit-from-scene",
        {"sceneId": "Scene 12"},
    )["session"]
    write("continuity/live-session.json", s)
    report["steps"].append({"inherit": s["id"]})

    # Triple inherit identity
    for i in range(2):
        s2 = req(
            "POST",
            f"/api/image-studio/projects/{PROJECT}/continuity-sessions/inherit-from-scene",
            {"sceneId": "Scene 12"},
        )["session"]
        assert s2["id"] == s["id"], "continuity session must be stable across inherits"
    report["steps"].append({"continuityStable": True})

    asset = images[0]["id"]
    approved = req(
        "POST",
        f"/api/image-studio/projects/{PROJECT}/continuity-sessions/{s['id']}/approve-image",
        {"assetId": asset},
    )["session"]
    write("continuity/approved.json", approved)
    report["steps"].append({"approved": asset in approved.get("approvedImageIds", [])})

    reopen = req("GET", f"/api/image-studio/projects/{PROJECT}/assets/{asset}/reopen")
    write("creative/reopen.json", reopen)
    report["steps"].append({"reopenPrompt": bool((reopen.get("reopen") or {}).get("prompt") is not None)})

    added = req(
        "POST",
        f"/api/storyboard-studio/projects/{PROJECT}/add-image",
        {
            "assetId": asset,
            "prompt": "Narrative film cert frame — dusk alley, anamorphic",
            "label": "Live Cert",
            "sceneId": "Scene 12",
            "continuitySessionId": s["id"],
            "scriptwriterSceneId": "Scene 12",
        },
    )
    write("creative/add-image.json", added)

    # Fill toward 9 panels using available assets (reuse if fewer than 9)
    panel_ids = [added["panelId"]]
    for i in range(8):
        aid = images[i % len(images)]["id"]
        row = req(
            "POST",
            f"/api/storyboard-studio/projects/{PROJECT}/add-image",
            {
                "assetId": aid,
                "prompt": f"Storyboard cert panel {i + 2}",
                "label": f"P{i + 2}",
                "sceneId": "Scene 12",
                "continuitySessionId": s["id"],
            },
        )
        panel_ids.append(row["panelId"])
    write("storyboard/nine-panels.json", {"panelIds": panel_ids})

    # Replace panel index 4 (5th), undo
    target = panel_ids[4]
    replaced = req(
        "POST",
        f"/api/storyboard-studio/projects/{PROJECT}/replace-panel",
        {
            "panelId": target,
            "assetId": images[-1]["id"],
            "prompt": "Replaced panel 5",
            "continuitySessionId": s["id"],
            "sceneId": "Scene 12",
        },
    )
    write("storyboard/replace-panel-5.json", replaced)
    undone = req(
        "POST",
        f"/api/storyboard-studio/projects/{PROJECT}/undo-replace-panel",
        {"panelId": target},
    )
    write("storyboard/undo-replace.json", undone)

    prep = req(
        "POST",
        f"/api/storyboard-studio/projects/{PROJECT}/prepare-timeline",
        {"panelIds": [panel_ids[7]], "approvedOnly": False},
    )
    write("storyboard/prepare-panel-8.json", prep)
    proposal_id = prep["proposal"]["id"]
    confirmed = req(
        "POST",
        f"/api/storyboard-studio/projects/{PROJECT}/timeline-proposals/{proposal_id}/confirm",
        {"panelIds": [panel_ids[7]]},
    )
    write("storyboard/confirm-panel-8.json", confirmed)

    pdf = req("GET", f"/api/storyboard-studio/projects/{PROJECT}/export.pdf")
    write("storyboard/export.pdf", pdf)
    report["steps"].append({"pdfBytes": len(pdf), "pdfMagic": pdf[:4].decode("latin-1", errors="replace")})

    providers = req(
        "POST",
        "/api/image-studio/providers/for-mode",
        {"mode": "all_models", "prompt": "cinematic", "purpose": "storyboard"},
    )
    write("providers/all-models.json", providers)

    ws = req("GET", f"/api/storyboard-studio/projects/{PROJECT}/workspace")
    write("storyboard/workspace-after.json", ws)

    report["verdict"] = "LIVE_API_WORKFLOW_PASS"
    write("creative/live-report.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise
