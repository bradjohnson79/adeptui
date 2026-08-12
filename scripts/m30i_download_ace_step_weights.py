#!/usr/bin/env python3
"""Download ACE-Step-v1-3.5B weights into sandbox models/ with retries (M3.0i)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "data" / "m210b-sandbox" / "providers" / "m2101-music-045" / "models"
OUT = ROOT / "artifacts" / "m30i" / "native-production" / "preflight" / "ace-step-weights.json"
REPO = "ACE-Step/ACE-Step-v1-3.5B"


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download

    log: dict = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "localDir": str(MODELS),
        "attempts": [],
    }
    last_err = None
    for attempt in range(1, 6):
        t0 = time.time()
        try:
            path = snapshot_download(
                repo_id=REPO,
                local_dir=str(MODELS),
                max_workers=2,
                resume_download=True,
            )
            elapsed = time.time() - t0
            tops = [p.name for p in Path(path).iterdir()]
            required = {"music_dcae_f8c8", "music_vocoder", "ace_step_transformer", "umt5-base"}
            present = required.intersection(set(tops))
            log.update(
                {
                    "ok": True,
                    "path": path,
                    "top": tops[:40],
                    "requiredPresent": sorted(present),
                    "status": "MODEL_READY" if present == required else "MODEL_PARTIAL",
                    "finishedAt": datetime.now(timezone.utc).isoformat(),
                    "elapsedSec": round(elapsed, 1),
                }
            )
            log["attempts"].append({"attempt": attempt, "ok": True, "elapsedSec": round(elapsed, 1)})
            OUT.write_text(json.dumps(log, indent=2), encoding="utf-8")
            print("STATUS", log["status"])
            return 0 if log["status"] == "MODEL_READY" else 3
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            log["attempts"].append({"attempt": attempt, "ok": False, "error": last_err[-800:]})
            print(f"attempt {attempt} failed: {last_err[:200]}", file=sys.stderr)
            time.sleep(min(60, 5 * attempt))
    log.update(
        {
            "ok": False,
            "status": "DOWNLOAD_FAILED",
            "error": (last_err or "")[-1500:],
            "finishedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    OUT.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("STATUS DOWNLOAD_FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
