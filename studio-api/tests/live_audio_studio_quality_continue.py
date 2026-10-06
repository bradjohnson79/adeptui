"""Continue the live quality suite after footsteps already completed."""

from __future__ import annotations

import json
import time
from pathlib import Path

from live_audio_studio_quality import (
    OUT,
    PROJECT_ID,
    SUITE,
    analyze_wav,
    copy_asset,
    req,
    wait_batch,
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ws = req("GET", f"/api/audio-studio/projects/{PROJECT_ID}/workspace")
    batches = ws.get("batches") or []
    report: dict = {"projectId": PROJECT_ID, "runs": []}
    foot = next((b for b in batches if (b.get("compiled_prompt") or "").lower().find("footstep") >= 0), batches[0] if batches else None)
    if foot:
        takes = []
        for cand in foot.get("candidates") or []:
            aid = cand.get("asset_id")
            wav = copy_asset(aid, OUT / f"footsteps_{cand.get('id')}.wav") if aid else None
            analysis = analyze_wav(wav) if wav else None
            takes.append(
                {
                    "id": cand.get("id"),
                    "status": cand.get("status"),
                    "assetId": aid,
                    "timings": cand.get("timings"),
                    "analysis": analysis,
                    "wav": str(wav) if wav else None,
                }
            )
            print("footsteps take", cand.get("status"), analysis, cand.get("timings"))
        report["runs"].append(
            {
                "id": "footsteps",
                "batchId": foot.get("id"),
                "status": foot.get("status"),
                "compiledPrompt": foot.get("compiled_prompt"),
                "negativePrompt": foot.get("negative_prompt"),
                "takes": takes,
                "reusedExisting": True,
            }
        )
    remaining = [spec for spec in SUITE if spec["id"] != "footsteps"]
    for spec in remaining:
        print("\n===", spec["id"], "===")
        t0 = time.time()
        started = req(
            "POST",
            f"/api/audio-studio/projects/{PROJECT_ID}/generate",
            {
                "kind": spec["kind"],
                "prompt": spec["prompt"],
                "durationSeconds": spec["duration"],
                "intensity": spec["intensity"],
                "eventType": spec["eventType"],
                "category": spec["kind"],
                "candidateCount": spec["takes"],
                "asyncMode": True,
                "allowProviderSwitch": False,
                "allowCpuFallback": False,
            },
        )
        print("compiled", (started.get("compiled_prompt") or "")[:320])
        print("neg", started.get("negative_prompt"))
        done = wait_batch(str(started["id"]))
        elapsed = time.time() - t0
        takes = []
        for cand in done.get("candidates") or []:
            aid = cand.get("asset_id")
            wav = copy_asset(aid, OUT / f"{spec['id']}_{cand.get('id')}.wav") if aid else None
            analysis = analyze_wav(wav) if wav else None
            takes.append(
                {
                    "id": cand.get("id"),
                    "status": cand.get("status"),
                    "error": cand.get("error"),
                    "assetId": aid,
                    "timings": cand.get("timings"),
                    "analysis": analysis,
                    "wav": str(wav) if wav else None,
                }
            )
            print(" take", cand.get("status"), cand.get("error"), analysis, cand.get("timings"))
        report["runs"].append(
            {
                "id": spec["id"],
                "batchId": started.get("id"),
                "elapsedSec": elapsed,
                "status": done.get("status"),
                "progress": done.get("progress"),
                "compiledPrompt": done.get("compiled_prompt") or started.get("compiled_prompt"),
                "negativePrompt": done.get("negative_prompt"),
                "takes": takes,
            }
        )
    (OUT / "live-quality-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT / "live-quality-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
