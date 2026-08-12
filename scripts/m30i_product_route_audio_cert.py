#!/usr/bin/env python3
"""M3.0i product-route audio certification (music/SFX/dialogue) via Studio API.

Requires STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1=1 on the API process.
No fal. No fixtures.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30i" / "native-production" / "product-route"
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8743").rstrip("/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=900) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:2000]}") from exc


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"startedAt": _now(), "api": API, "cases": []}

    # Create project
    proj = _req("POST", "/api/projects", {"name": "M3.0i Native Audio Product Route"})
    project_id = proj.get("id") or proj.get("projectId")
    if not project_id:
        # some APIs return nested
        project_id = (proj.get("project") or {}).get("id")
    if not project_id:
        report["error"] = f"create_project_failed: {proj}"
        (OUT / "audio-product-route.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("FAIL create project", proj)
        return 2
    report["projectId"] = project_id

    cases = [
        {
            "id": "AUDIO-MUSIC-01",
            "kind": "music",
            "registryId": "m2101-music-045",
            "prompt": "cinematic ambient underscore, soft pads, no vocals",
            "durationSec": 8,
        },
        {
            "id": "AUDIO-SFX-01",
            "kind": "sfx",
            "registryId": "m2101-sfx-031",
            "prompt": "footsteps on gravel, sparse, outdoor",
            "durationSec": 3,
        },
        {
            "id": "AUDIO-DIALOGUE-01",
            "kind": "dialogue",
            "registryId": "m2101-dialogue-001",
            "prompt": "Are you heading into town?",
            "durationSec": 3,
        },
    ]

    for case in cases:
        entry = {"id": case["id"], "kind": case["kind"], "startedAt": _now()}
        payload = {
            "kind": case["kind"],
            "prompt": case["prompt"],
            "durationSec": case["durationSec"],
            "registryId": case["registryId"],
            "seed": 42,
        }
        body = {
            "projectId": project_id,
            "kind": case["kind"],
            "prompt": case["prompt"],
            "durationSec": case["durationSec"],
            "registryId": case["registryId"],
            "seed": 42,
        }
        try:
            result = _req("POST", "/api/codirector/m29/audio/generate", body)
            entry["result"] = {
                k: result.get(k)
                for k in (
                    "assetId",
                    "assetPath",
                    "sha256",
                    "durationSec",
                    "sampleRate",
                    "registryId",
                    "status",
                    "sandboxOnly",
                    "provenance",
                )
            }
            path = result.get("assetPath")
            if path and Path(str(path)).is_file() and Path(str(path)).stat().st_size > 1000:
                entry["bytes"] = Path(str(path)).stat().st_size
                entry["fileExists"] = True
                entry["ok"] = True
            else:
                entry["fileExists"] = False
                entry["ok"] = False
                entry["error"] = "assetPath missing or file too small"
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = str(exc)[:2000]
        entry["finishedAt"] = _now()
        report["cases"].append(entry)
        print(case["id"], "OK" if entry.get("ok") else "FAIL", entry.get("error") or entry.get("result", {}).get("assetPath"))

    report["finishedAt"] = _now()
    report["allOk"] = all(c.get("ok") for c in report["cases"])
    (OUT / "audio-product-route.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("STATUS", "GREEN" if report["allOk"] else "NOT_GREEN")
    return 0 if report["allOk"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
