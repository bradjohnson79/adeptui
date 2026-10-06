# -*- coding: utf-8 -*-
"""Official two-batch certification runner (API level, full trace capture).

Phase 23-26 evidence: Batch 1 + Batch 2 live LTX FINAL generation with
complete provenance capture. Run: python scripts/cert_timeline_two_batch.py
"""
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8758/api"
PROJECT = "42dcee6d-eb0d-430e-a16a-e62ee05b4ac1"
SCENE = "638a86a1-64fa-474a-be36-c47dcf3333dc"
B1 = "bb_41bfcf57540f"
B2 = "bb_77a6dc9c2134"
ART = Path("docs/release-gate/timeline-final/artifacts/two-batch-production/live-run")

ART.mkdir(parents=True, exist_ok=True)


def req(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def get(path):
    return req("GET", f"{API}{path}")


def post(path, body=None):
    return req("POST", f"{API}{path}", body)


def master():
    return get(f"/director-timeline/projects/{PROJECT}/scenes/{SCENE}/master")["master"]


def batch_state(bid):
    m = master()
    return next(b for b in m["batchBlocks"] if b["id"] == bid)


def wait_terminal(bid, timeout_min=40):
    deadline = time.time() + timeout_min * 60
    last = None
    while time.time() < deadline:
        st = batch_state(bid)
        last = st
        if st["status"] in ("Approved", "Failed", "Cancelled"):
            return st
        time.sleep(15)
    raise TimeoutError(f"batch {bid} not terminal: {last and last['status']}")


def capture(name, payload):
    p = ART / name
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  captured {name}")


def main():
    print(f"=== Timeline two-batch LIVE certification ({datetime.now(timezone.utc).isoformat()}) ===")
    report = {"startedAt": datetime.now(timezone.utc).isoformat(), "project": PROJECT, "scene": SCENE,
              "batches": {B1: {}, B2: {}}, "generator": "ltx-local", "aspect": "16:9", "resolution": "1280x720"}

    for bid, label in ((B1, "Batch 1"), (B2, "Batch 2")):
        print(f"--- {label} ({bid}) ---")
        st = batch_state(bid)
        report["batches"][bid]["pre"] = {
            "status": st["status"],
            "prompts": [{"text": s["text"], "start": s["start"], "length": s["length"],
                         "userDirection": s.get("userDirection"), "dialogue": s.get("dialogue")} for s in st["promptSegments"]],
            "anchors": [{"assetId": a.get("assetId"), "label": a.get("label")} for a in st["sourceAnchors"]],
            "generator": st["generatorId"],
            "duration": st["duration"],
        }
        capture(f"01-{bid}-pre-state.json", report["batches"][bid]["pre"])
        gen = post(f"/director-timeline/projects/{PROJECT}/scenes/{SCENE}/batches/{bid}/generate",
                   {"draftMode": False})
        capture(f"02-{bid}-generate-response.json", gen)
        report["batches"][bid]["generate"] = {
            "ok": gen.get("ok"), "job": gen.get("job"), "snapshot": gen.get("executionSnapshotId"),
            "normalizedRequest": gen.get("normalizedRequest"),
        }
        if not gen.get("ok"):
            print(f"  GENERATE FAILED: {gen}")
            report["verdict"] = "NO-GO"
            capture("VERDICT.json", report)
            return 1
        print(f"  submitted job={gen['job']['id']} snapshot={gen['executionSnapshotId']}")
        st = wait_terminal(bid)
        capture(f"03-{bid}-terminal.json", st)
        report["batches"][bid]["terminal"] = {
            "status": st["status"], "approvedClip": st.get("approvedClip"),
            "candidateVersions": st.get("candidateVersions"), "jobs": st.get("generationJobs"),
            "lineage": [r for r in st.get("references", []) if r.get("kind") == "timelineGenerationLineage"],
            "activeTakeId": st.get("activeTakeId"),
        }
        if st["status"] != "Approved":
            print(f"  BATCH NOT APPROVED: {st['status']}")
            report["verdict"] = "NO-GO"
            capture("VERDICT.json", report)
            return 1
        print(f"  APPROVED asset={st['approvedClip']['assetId']}")

    # Post-run cross-batch checks
    m = master()
    ordered = sorted(m["batchBlocks"], key=lambda b: b["order"])
    a1 = ordered[0]["approvedClip"]["assetId"]
    a2 = ordered[1]["approvedClip"]["assetId"]
    assert a1 != a2, "batches must produce distinct assets"
    assert ordered[0]["sourceAnchors"][0]["assetId"] != ordered[1]["sourceAnchors"][0]["assetId"],         "no cross-batch source-image leakage"
    report["crossBatch"] = {
        "distinctOutputs": True, "distinctSources": True,
        "batch1Source": ordered[0]["sourceAnchors"][0]["assetId"],
        "batch2Source": ordered[1]["sourceAnchors"][0]["assetId"],
        "batch1Output": a1, "batch2Output": a2,
        "windowOrder": [(b["id"], b["duration"]["plannedDuration"]) for b in ordered],
    }
    capture("04-cross-batch.json", report["crossBatch"])

    # Video clips placed on the NLE track
    tl = get(f"/projects/{PROJECT}/scenes/{SCENE}/director")
    placed = [c for c in tl.get("video_clips", []) if str(c.get("id", "")).startswith("bbclip_")]
    placed.sort(key=lambda c: c["start"])
    report["placedClips"] = placed
    capture("05-placed-clips.json", placed)
    report["finishedAt"] = datetime.now(timezone.utc).isoformat()
    report["verdict"] = "GO"
    capture("VERDICT.json", report)
    print("=== DONE: GO ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
