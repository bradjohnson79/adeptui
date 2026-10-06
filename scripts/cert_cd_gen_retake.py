# -*- coding: utf-8 -*-
"""GPU-window sequence: CD generation approve + batch retake + vision review."""
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758/api"
PROJECT = "42dcee6d-eb0d-430e-a16a-e62ee05b4ac1"
SCENE = "638a86a1-64fa-474a-be36-c47dcf3333dc"
B1 = "bb_41bfcf57540f"
B2 = "bb_77a6dc9c2134"
GEN_PROPOSAL = "8203ed1f-85b6-4c0b-b0b7-22b560b095a9"
ART = Path("docs/release-gate/timeline-final/artifacts/two-batch-production/live-run")


def req(method, url, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def master():
    return req("GET", f"{API}/director-timeline/projects/{PROJECT}/scenes/{SCENE}/master")["master"]


def wait_terminal(bid, timeout_min=32):
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        st = next(b for b in master()["batchBlocks"] if b["id"] == bid)
        if st["status"] in ("Approved", "Failed", "Cancelled"):
            return st
        time.sleep(10)
    raise TimeoutError("not terminal")


def cd_generate():
    print("=== CD generation (approve proposal) ===")
    r = req("POST", f"{API}/codirector/projects/{PROJECT}/proposals/{GEN_PROPOSAL}/approve", {})
    print("approve status:", r.get("status"))
    st = wait_terminal(B2)
    print("B2 terminal:", st["status"], "approved:", (st.get("approvedClip") or {}).get("assetId"))
    (ART / "CD-GEN-VERIFY.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    return st["status"] == "Approved"


def retake():
    print("=== Batch 1 retake (w46 inspector path) ===")
    r = req("POST", f"{API}/director-timeline/projects/{PROJECT}/scenes/{SCENE}/batches/{B1}/retake",
            {"userCorrection": {"delta": "Slower confident walk, shoes clearly in frame, brighter commercial light."}})
    print("retake ok:", r.get("ok"), "job:", (r.get("job") or {}).get("id"))
    st = wait_terminal(B1)
    cands = st.get("candidateVersions") or []
    print("B1 terminal:", st["status"], "candidates:", len(cands), "activeTake:", st.get("activeTakeId"))
    if len(cands) >= 2:
        print("lineage: take2 parent =", cands[-1].get("parentTakeId"), "| take1 =", cands[0].get("takeId"))
    (ART / "B1-RETAKE-VERIFY.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    return st["status"] == "Approved" and len(cands) >= 2


if __name__ == "__main__":
    ok_gen = cd_generate()
    ok_retake = retake()
    print("CD_GEN_OK:", ok_gen, "RETAKE_OK:", ok_retake)
    sys.exit(0 if (ok_gen and ok_retake) else 1)
