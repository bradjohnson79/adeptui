"""Cancel + next-gen + approve + place on Korri. No new project."""

from __future__ import annotations

import json
import time
from pathlib import Path

from live_audio_studio_quality import PROJECT_ID, req, wait_batch

OUT = Path(r"C:\AdeptFilmWorks\AIVideoStudio\artifacts\audio-studio-quality")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = req(
        "POST",
        f"/api/audio-studio/projects/{PROJECT_ID}/generate",
        {
            "kind": "sfx",
            "prompt": "Heavy steel door slam, close.",
            "durationSeconds": 2,
            "intensity": "Bold",
            "eventType": "door_slam",
            "category": "sfx",
            "candidateCount": 2,
            "asyncMode": True,
            "allowProviderSwitch": False,
            "allowCpuFallback": False,
        },
    )
    batch_id = str(started["id"])
    print("cancel-batch", batch_id, started.get("progress", {}).get("label"))
    first_ready = None
    deadline = time.time() + 180
    while time.time() < deadline:
        batch = req("GET", f"/api/audio-studio/projects/{PROJECT_ID}/batches/{batch_id}")
        ready = [c for c in (batch.get("candidates") or []) if c.get("status") == "ready" and c.get("asset_id")]
        generating = any(c.get("status") == "generating" for c in (batch.get("candidates") or []))
        print("poll", batch.get("status"), batch.get("progress", {}).get("label"), "ready", len(ready))
        if ready and (generating or len(ready) == 1):
            first_ready = ready[0]
            break
        if batch.get("status") in ("complete", "failed", "cancelled"):
            first_ready = ready[0] if ready else None
            break
        time.sleep(1.5)
    cancelled = req("POST", f"/api/audio-studio/projects/{PROJECT_ID}/batches/{batch_id}/cancel")
    after = req("GET", f"/api/audio-studio/projects/{PROJECT_ID}/batches/{batch_id}")
    print("cancel", cancelled.get("ok"), after.get("status"), [(c.get("status"), c.get("asset_id")) for c in after.get("candidates") or []])

    nxt = req(
        "POST",
        f"/api/audio-studio/projects/{PROJECT_ID}/generate",
        {
            "kind": "sfx",
            "prompt": "Glass set on a counter, short and clean.",
            "durationSeconds": 2,
            "intensity": "Normal",
            "eventType": "glass_place",
            "category": "sfx",
            "candidateCount": 1,
            "asyncMode": True,
            "allowProviderSwitch": False,
            "allowCpuFallback": False,
        },
    )
    done = wait_batch(str(nxt["id"]))
    print("next-gen", done.get("status"), [(c.get("status"), c.get("asset_id"), (c.get("timings") or {}).get("inferenceMs")) for c in done.get("candidates") or []])

    foot = req("GET", f"/api/audio-studio/projects/{PROJECT_ID}/batches/2231763a-b38b-4931-9651-087e697efb55")
    cand = next(c for c in foot["candidates"] if c.get("id") == "544606fe-781e-4ef4-a857-9d2070918a41")
    approved = req(
        "POST",
        f"/api/audio-studio/projects/{PROJECT_ID}/batches/{foot['id']}/candidates/{cand['id']}/approve",
    )
    placed = req(
        "POST",
        f"/api/audio-studio/projects/{PROJECT_ID}/place",
        {"assetId": cand["asset_id"], "category": "sfx", "startMs": 0, "loop": False},
    )
    print("approve", approved.get("approved"), "place", placed.get("ok") or placed)

    report = {
        "cancelBatchId": batch_id,
        "cancel": {"ok": cancelled.get("ok"), "status": after.get("status"), "candidates": after.get("candidates"), "serveInterrupt": cancelled.get("serveInterrupt")},
        "firstReadyPreserved": bool(first_ready and any(c.get("id") == first_ready.get("id") and c.get("status") == "ready" for c in after.get("candidates") or [])),
        "nextGen": {"batchId": nxt.get("id"), "status": done.get("status"), "candidates": done.get("candidates")},
        "approve": approved,
        "place": placed,
    }
    (OUT / "cancel-timeline-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT / "cancel-timeline-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
