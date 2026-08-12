"""Export Hitchhiker project via Studio API for M3.2f evidence."""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
OUT = Path("artifacts/m32f/hitchhiker-production-lifecycle/09-final-render")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    req = urllib.request.Request(
        f"{API}/api/projects/{PID}/export",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    job = json.load(urllib.request.urlopen(req, timeout=60))
    print("export job", job.get("id"))
    for _ in range(120):
        j = json.load(urllib.request.urlopen(f"{API}/api/jobs/{job['id']}"))
        if j.get("status") in ("done", "failed", "cancelled"):
            print(j.get("status"), (j.get("message") or "")[:200], j.get("output_path"))
            (OUT / "export-job.json").write_text(json.dumps(j, indent=2), encoding="utf-8")
            return
        time.sleep(2)
    raise SystemExit("export timed out")


if __name__ == "__main__":
    main()
