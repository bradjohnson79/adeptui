"""Cancel stuck Hitchhiker jobs before certification re-runs."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"


def main() -> None:
    jobs = json.load(urllib.request.urlopen(f"{API}/api/projects/{PID}/jobs", timeout=60))
    cancelled = []
    for job in jobs:
        status = str(job.get("status") or "").lower()
        if status not in {"queued", "running", "claimed"}:
            continue
        req = urllib.request.Request(
            f"{API}/api/jobs/{job['id']}/cancel",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=30)
            cancelled.append(job["id"])
        except urllib.error.HTTPError as exc:
            cancelled.append(f"{job['id']}:HTTP{exc.code}")
    print(json.dumps({"cancelled": cancelled}, indent=2))


if __name__ == "__main__":
    main()
