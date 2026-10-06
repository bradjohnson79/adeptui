# -*- coding: utf-8 -*-
"""Batch-1-only regeneration + metadata verification + retake of batch 2."""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8758/api"
PROJECT = "42dcee6d-eb0d-430e-a16a-e62ee05b4ac1"
SCENE = "638a86a1-64fa-474a-be36-c47dcf3333dc"
B1 = "bb_41bfcf57540f"
B2 = "bb_77a6dc9c2134"
ART = Path("docs/release-gate/timeline-final/artifacts/two-batch-production/live-run")


def req(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def master():
    return req("GET", f"{API}/director-timeline/projects/{PROJECT}/scenes/{SCENE}/master")["master"]


def wait_terminal(bid, timeout_min=30):
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        st = next(b for b in master()["batchBlocks"] if b["id"] == bid)
        if st["status"] in ("Approved", "Failed", "Cancelled"):
            return st
        time.sleep(10)
    raise TimeoutError("not terminal")


def run_batch1():
    print("=== Batch 1 regeneration (metadata fix exercise) ===")
    gen = req("POST", f"{API}/director-timeline/projects/{PROJECT}/scenes/{SCENE}/batches/{B1}/generate", {"draftMode": False})
    print("submitted", gen.get("job", {}).get("id"), "snap", gen.get("executionSnapshotId"))
    st = wait_terminal(B1)
    print("terminal:", st["status"], "approved:", (st.get("approvedClip") or {}).get("assetId"))
    d = st["duration"]
    print("durations:", json.dumps(d))
    lin = [r for r in st.get("references", []) if r.get("kind") == "timelineGenerationLineage"]
    if lin:
        l = lin[-1]
        print("lineage startImage:", l.get("startImageAssetId"), "generator:", l.get("generatorId"), "res:", l.get("resolution"))
    (ART / "B1-METADATA-VERIFY.json").write_text(json.dumps({"terminal": st}, indent=2, default=str), encoding="utf-8")
    return st["status"] == "Approved"


def run_retake():
    print("=== Batch 2 retake ===")
    body = {"userCorrection": {"delta": "Slower walk, more confident smile, shoes clearly visible."}}
    r = req("POST", f"{API}/director-timeline/projects/{PROJECT}/scenes/{SCENE}/batches/{B2}/retake", body)
    print("retake submitted:", r.get("ok"), r.get("batchBlockId"))
    st = wait_terminal(B2, timeout_min=30)
    print("terminal:", st["status"], "approved:", (st.get("approvedClip") or {}).get("assetId"))
    cands = st.get("candidateVersions") or []
    print("candidates:", len(cands))
    if len(cands) >= 2:
        print("take lineage: parent=", cands[-1].get("parentTakeId"), "activeTake=", st.get("activeTakeId"))
    (ART / "B2-RETAKE-VERIFY.json").write_text(json.dumps({"terminal": st}, indent=2, default=str), encoding="utf-8")
    return st["status"] == "Approved" and len(cands) >= 2


if __name__ == "__main__":
    print("started:", datetime.now(timezone.utc).isoformat())
    ok1 = run_batch1()
    ok2 = run_retake()
    print("BATCH1_OK:", ok1, "RETAKE_OK:", ok2)
    sys.exit(0 if (ok1 and ok2) else 1)
