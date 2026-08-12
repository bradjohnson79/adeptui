#!/usr/bin/env python3
"""Complete product export for the M3.0h local-first certified project."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8742"
PROJECT_ID = "2f561428-7a17-4d0a-917f-6da6c0960837"
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "m30h-local-first" / "real-local-execution"


def main() -> int:
    req = urllib.request.Request(
        f"{API}/api/projects/{PROJECT_ID}/export",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    job = json.load(urllib.request.urlopen(req, timeout=60))
    (OUT / "export-job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    for _ in range(180):
        j = json.load(urllib.request.urlopen(f"{API}/api/jobs/{job['id']}", timeout=60))
        if j.get("status") in ("done", "failed", "cancelled"):
            (OUT / "export-job-final.json").write_text(json.dumps(j, indent=2) + "\n", encoding="utf-8")
            proof_path = OUT / "local-proof.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["exportStatus"] = j.get("status")
            proof["exportJobId"] = j.get("id")
            proof["exportOutputPath"] = j.get("output_path")
            proof["exportMessage"] = j.get("message")
            if j.get("status") == "done":
                proof["exportContract"] = "product_export_job_completed"
            proof_path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"status": j.get("status"), "output": j.get("output_path")}, indent=2))
            return 0 if j.get("status") == "done" else 2
        time.sleep(1)
    print("timeout", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
