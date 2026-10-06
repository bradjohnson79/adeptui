"""Poll a studio job until terminal state."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8758"
JOB = sys.argv[1] if len(sys.argv) > 1 else ""
TIMEOUT = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
OUT = Path(__file__).resolve().parent / "evidence" / "WAN_FLF_JOB.json"


def main() -> int:
    if not JOB:
        print("usage: poll_job.py JOB_ID [timeout]")
        return 2
    started = time.time()
    last = {}
    with httpx.Client(timeout=30.0) as client:
        while time.time() - started < TIMEOUT:
            job = client.get(f"{API}/api/jobs/{JOB}").json()
            last = {
                "id": job.get("id"),
                "status": job.get("status"),
                "stage": job.get("stage"),
                "progress": job.get("progress"),
                "message": job.get("message"),
                "output_path": job.get("output_path") or job.get("outputPath"),
                "elapsed_s": round(time.time() - started, 1),
            }
            print(json.dumps(last), flush=True)
            if str(job.get("status") or "").lower() in {"done", "complete", "failed", "error", "cancelled", "canceled"}:
                OUT.write_text(json.dumps(job, indent=2, default=str)[:200000], encoding="utf-8")
                return 0 if str(job.get("status") or "").lower() in {"done", "complete"} else 1
            time.sleep(15)
    OUT.write_text(json.dumps({"timeout": True, "last": last}, indent=2), encoding="utf-8")
    print("TIMEOUT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
