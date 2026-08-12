#!/usr/bin/env python3
"""Independent verifier for Timeline Multi-Batch + Preview Monitor GO Closure.

Runs against the live Beta API (http://127.0.0.1:8758) and checks each gate.
Exit 0 = all gates pass; exit 1 = any gate fails.

Wiring gates (request-sink isolation, sequential queue contract, completion
binding, re-take, stop/resume) require the Beta API to run with
ADEPT_TIMELINE_CERT_STUB=1 so the env-gated StubCertAdapter replaces the
provider execution boundary. NO GPU generation is ever executed — live
multi-batch GPU generation remains the manual creator gate.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8758"
TL = "/api/director-timeline"
CERT = f"{TL}/cert"
STUB_GENERATOR = "cert-stub-local"
REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "docs" / "release-gate" / "timeline-multi-batch" / "artifacts"
FULL_AUDIT_DIR = REPO_ROOT / "docs" / "release-gate" / "timeline-full-audit"
FULL_AUDIT_ARTIFACTS = FULL_AUDIT_DIR / "artifacts"
REGISTRY_PATH = REPO_ROOT / "config" / "video-workflows" / "certified-registry.json"
results: list[tuple[str, bool, str]] = []


def req(method: str, path: str, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"_raw": e.read().decode()[:200]}


def gate(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail}")


# ---------------------------------------------------------------------------
# Cert-mode helpers (stub-gated)
# ---------------------------------------------------------------------------

def stub_enabled() -> bool:
    s, _ = req("GET", f"{CERT}/requests")
    return s == 200


def cert_reset() -> None:
    s, b = req("POST", f"{CERT}/reset")
    assert s == 200 and b.get("ok"), f"cert reset failed: {s} {b}"


def sink() -> list[dict]:
    s, b = req("GET", f"{CERT}/requests")
    assert s == 200, f"cert requests failed: {s}"
    return b.get("requests", [])


def set_stub_state(job_id: str, state: str, output_asset_ids=None, error_message=None) -> None:
    s, b = req("POST", f"{CERT}/stub-jobs/{job_id}/state", {
        "state": state, "outputAssetIds": output_asset_ids, "errorMessage": error_message,
    })
    assert s == 200, f"set stub state failed: {s} {b}"


def get_master(pid: str, sid: str) -> dict:
    s, b = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
    assert s == 200, f"master GET failed: {s}"
    return b["master"]


def add_batch(pid: str, sid: str, planned: float = 5.0, at_order=None) -> dict:
    body = {"plannedDuration": planned}
    if at_order is not None:
        body["atOrder"] = at_order
    s, b = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches", body)
    assert s == 200, f"add batch failed: {s} {b}"
    return b["batch"]


def config_batch(pid: str, sid: str, batch_id: str, prompt: str, planned: float = 5.0) -> None:
    s, b = req("PATCH", f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch_id}", {
        "generatorId": STUB_GENERATOR,
        "plannedDuration": planned,
        "promptSegments": [{
            "id": f"ps-{batch_id[-6:]}", "start": 0, "length": planned, "text": prompt,
            "role": "primary", "strength": 1, "anchorIds": [],
            "executionStrategy": "compiled", "versionId": f"psv-{batch_id[-6:]}",
        }],
    })
    assert s == 200, f"config batch failed: {s} {b}"


def complete_and_approve(pid: str, sid: str, batch_id: str, snapshot_id: str, asset_id: str, duration: float = 5.0) -> dict:
    s, c = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch_id}/complete", {
        "assetId": asset_id, "generatedDuration": duration, "executionSnapshotId": snapshot_id,
    })
    assert s == 200 and c.get("ok"), f"complete failed: {s} {c}"
    s, a = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch_id}/approve", {
        "candidateId": c["candidate"]["id"],
    })
    assert s == 200, f"approve failed: {s} {a}"
    return a


def new_verifier_project() -> tuple[str, str]:
    s, p = req("POST", "/api/projects", {"name": "Timeline Wiring Verifier"})
    assert s == 200, f"create project failed: {s} {p}"
    pid = p["id"]
    s, scenes = req("GET", f"/api/projects/{pid}/scenes")
    slist = scenes if isinstance(scenes, list) else scenes.get("scenes", [])
    assert slist, "verifier project has no scene"
    return pid, slist[0]["id"]


# 8x8 red PNG — same fixture bytes as the wiring cert's PNG_RED.
_PNG_RED_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGP4z8CAFWEXHbQSACj/P8Fu7N9hAAAAAElFTkSuQmCC"
)


def upload_image(pid: str, tag: str) -> str:
    """Multipart-upload the tiny PNG fixture; returns the asset id."""
    import base64
    import uuid

    png = base64.b64decode(_PNG_RED_B64)
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("tag", tag), ("kind", "image")):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{tag}.png\"\r\n"
        f"Content-Type: image/png\r\n\r\n".encode()
        + png
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    payload = b"".join(parts)
    request = urllib.request.Request(
        f"{BASE}/api/projects/{pid}/assets",
        data=payload,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.loads(resp.read().decode())["id"]


def wiring_gates() -> None:
    """Wiring gates — run only when the cert stub is enabled. No GPU work."""
    # REQUEST_SINK_ISOLATION_PER_BATCH (parallel orchestration)
    cert_reset()
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        b1 = m["batchBlocks"][0]
        b2 = add_batch(pid, sid, 8.0)
        b3 = add_batch(pid, sid, 2.0)
        config_batch(pid, sid, b1["id"], "V-ONE", 5.0)
        config_batch(pid, sid, b2["id"], "V-TWO", 8.0)
        config_batch(pid, sid, b3["id"], "V-THREE", 2.0)
        m = get_master(pid, sid)
        m["orchestratorMode"] = "parallel"
        s, put = req("PUT", f"{TL}/projects/{pid}/scenes/{sid}/master", {"master": m})
        assert s == 200, f"set parallel failed: {s} {put}"
        s, gen = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/generate", {"scope": "full"})
        assert s == 200 and gen.get("ok"), f"generate failed: {s} {gen}"
        records = sink()
        by_batch = {r["request"]["batchBlockId"]: r["request"] for r in records}
        ok = (
            len(records) == 3
            and set(by_batch) == {b1["id"], b2["id"], b3["id"]}
            and len({r["executionSnapshotId"] for r in by_batch.values()}) == 3
            and "V-ONE" in by_batch[b1["id"]]["prompt"]
            and "V-TWO" in by_batch[b2["id"]]["prompt"]
            and by_batch[b2["id"]]["duration"] == 8.0
            and "V-THREE" in by_batch[b3["id"]]["prompt"]
            and "V-ONE" not in by_batch[b2["id"]]["prompt"]
        )
        gate("REQUEST_SINK_ISOLATION_PER_BATCH", ok, f"records={len(records)} batches={len(by_batch)}")
    finally:
        req("DELETE", f"/api/projects/{pid}")

    # SEQUENTIAL_QUEUE_CONTRACT — snapshot created != provider submitted; concurrency = 1
    cert_reset()
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        b1 = m["batchBlocks"][0]
        b2 = add_batch(pid, sid, 5.0)
        b3 = add_batch(pid, sid, 5.0)
        for bid, p in ((b1["id"], "S-ONE"), (b2["id"], "S-TWO"), (b3["id"], "S-THREE")):
            config_batch(pid, sid, bid, p, 5.0)
        s, gen = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/generate", {"scope": "full"})
        assert s == 200 and gen.get("orchestratorMode") == "sequential_continuity", f"seq generate failed: {s} {gen}"
        records = sink()
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        staged2 = by_id[b2["id"]].get("pendingSnapshotId")
        staged3 = by_id[b3["id"]].get("pendingSnapshotId")
        ok = (
            len(records) == 1
            and records[0]["request"]["batchBlockId"] == b1["id"]
            and by_id[b1["id"]]["status"] == "Generating"
            and by_id[b2["id"]]["status"] == "Queued"
            and by_id[b3["id"]]["status"] == "Queued"
            and staged2 and staged3
            and m["executionSnapshots"][staged2].get("immutable") is True
            and m["executionSnapshots"][staged3].get("immutable") is True
        )
        gate("SEQUENTIAL_SNAPSHOT_STAGING", ok,
             f"submissions={len(records)} staged={bool(staged2)}/{bool(staged3)}")

        # Chain: B1 terminal → B2 submitted with its STAGED snapshot (concurrency stays 1)
        snap1 = by_id[b1["id"]]["generationJobs"][0]["executionSnapshotId"]
        approved = complete_and_approve(pid, sid, b1["id"], snap1, "verifier-out-1")
        records = sink()
        chain = approved.get("sequentialChain") or {}
        ok = (
            chain.get("submitted") is True
            and chain.get("batchBlockId") == b2["id"]
            and len(records) == 2
            and records[1]["request"]["batchBlockId"] == b2["id"]
            and records[1]["request"]["executionSnapshotId"] == staged2
        )
        gate("SEQUENTIAL_CHAIN_ADVANCE", ok, f"chain={chain.get('batchBlockId')} records={len(records)}")

        # Watcher-driven chain: B2 stub job → succeeded → B3 submitted
        set_stub_state(records[1]["jobId"], "succeeded", ["verifier-out-2"])
        deadline = time.time() + 30
        chained = False
        while time.time() < deadline:
            m = get_master(pid, sid)
            by_id = {b["id"]: b for b in m["batchBlocks"]}
            if by_id[b3["id"]]["status"] == "Generating":
                chained = True
                break
            time.sleep(1)
        records = sink()
        ok = (
            chained
            and by_id[b2["id"]]["status"] == "Approved"
            and len(records) == 3
            and records[2]["request"]["batchBlockId"] == b3["id"]
            and records[2]["request"]["executionSnapshotId"] == staged3
        )
        gate("SEQUENTIAL_WATCHER_CHAIN", ok, f"records={len(records)} b3={by_id[b3['id']]['status']}")
    finally:
        req("DELETE", f"/api/projects/{pid}")

    # COMPLETION_BINDING_BY_LINEAGE — out-of-order completion binds by batchBlockId
    cert_reset()
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        bA = m["batchBlocks"][0]
        bB = add_batch(pid, sid, 5.0)
        config_batch(pid, sid, bA["id"], "B-ALPHA", 5.0)
        config_batch(pid, sid, bB["id"], "B-BRAVO", 5.0)
        s, scene_before = req("GET", f"/api/projects/{pid}/scenes/{sid}")
        out_path_before = scene_before.get("output_path") or scene_before.get("outputPath")
        for bid in (bA["id"], bB["id"]):
            s, g = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{bid}/generate")
            assert s == 200 and g.get("ok"), f"generate {bid} failed: {s} {g}"
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        snapA = by_id[bA["id"]]["generationJobs"][0]["executionSnapshotId"]
        snapB = by_id[bB["id"]]["generationJobs"][0]["executionSnapshotId"]
        complete_and_approve(pid, sid, bB["id"], snapB, "verifier-out-B")  # B first
        complete_and_approve(pid, sid, bA["id"], snapA, "verifier-out-A")  # then A
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        s, scene_after = req("GET", f"/api/projects/{pid}/scenes/{sid}")
        out_path_after = scene_after.get("output_path") or scene_after.get("outputPath")
        ok = (
            (by_id[bA["id"]].get("approvedClip") or {}).get("assetId") == "verifier-out-A"
            and (by_id[bA["id"]]["approvedClip"]).get("executionSnapshotId") == snapA
            and (by_id[bB["id"]].get("approvedClip") or {}).get("assetId") == "verifier-out-B"
            and (by_id[bB["id"]]["approvedClip"]).get("executionSnapshotId") == snapB
            and out_path_after == out_path_before
        )
        gate("COMPLETION_BINDING_BY_LINEAGE", ok,
             f"A={(by_id[bA['id']].get('approvedClip') or {}).get('assetId')} "
             f"B={(by_id[bB['id']].get('approvedClip') or {}).get('assetId')} "
             f"scene_output_unchanged={out_path_after == out_path_before}")
    finally:
        req("DELETE", f"/api/projects/{pid}")

    # RETAKE_TARGETING — new snapshot for retaken batch; other batch untouched
    cert_reset()
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        bA = m["batchBlocks"][0]
        bB = add_batch(pid, sid, 5.0)
        config_batch(pid, sid, bA["id"], "R-ALPHA", 5.0)
        config_batch(pid, sid, bB["id"], "R-BRAVO", 5.0)
        s, g = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{bB['id']}/generate")
        assert s == 200 and g.get("ok")
        first_snap = sink()[0]["request"]["executionSnapshotId"]
        s, rt = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{bB['id']}/retake", {"mode": "directed"})
        assert s == 200 and rt.get("ok"), f"retake failed: {s} {rt}"
        records = sink()
        retake_req = records[1]["request"]
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        ok = (
            len(records) == 2
            and retake_req["batchBlockId"] == bB["id"]
            and retake_req["executionSnapshotId"] != first_snap
            and "R-BRAVO" in retake_req["prompt"]
            and len(by_id[bA["id"]]["generationJobs"]) == 0
            and all(r["request"]["batchBlockId"] != bA["id"] for r in records)
            and first_snap in m["executionSnapshots"]
            and rt.get("priorSnapshotsPreserved") is True
        )
        gate("RETAKE_TARGETING", ok, f"newSnap={retake_req['executionSnapshotId'] != first_snap}")
    finally:
        req("DELETE", f"/api/projects/{pid}")

    # STOP_RESUME_SAFETY — stop preserves authoring + outputs; resume skips approved
    cert_reset()
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        b1 = m["batchBlocks"][0]
        b2 = add_batch(pid, sid, 5.0)
        b3 = add_batch(pid, sid, 5.0)
        b4 = add_batch(pid, sid, 5.0)
        for bid, p in ((b1["id"], "T-ONE"), (b2["id"], "T-TWO"), (b3["id"], "T-THREE"), (b4["id"], "T-FOUR")):
            config_batch(pid, sid, bid, p, 5.0)
        s, g = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{b4['id']}/generate")
        assert s == 200 and g.get("ok")
        m = get_master(pid, sid)
        snap4 = next(b for b in m["batchBlocks"] if b["id"] == b4["id"])["generationJobs"][0]["executionSnapshotId"]
        complete_and_approve(pid, sid, b4["id"], snap4, "verifier-out-4")
        cert_reset()
        s, gen = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/generate", {"scope": "full"})
        assert s == 200 and gen.get("ok")
        assert len(sink()) == 1, "sequential: only B1 submitted"

        s, cancel = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/cancel", {"action": "stop_remaining_scene_jobs"})
        assert s == 200 and cancel.get("ok"), f"stop failed: {s} {cancel}"
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        ok = (
            len(m["batchBlocks"]) == 4
            and all(by_id[i]["status"] == "Cancelled" for i in (b1["id"], b2["id"], b3["id"]))
            and all("T-" in by_id[i]["promptSegments"][0]["text"] for i in (b1["id"], b2["id"], b3["id"]))
            and all(by_id[i]["duration"]["plannedDuration"] == 5.0 for i in (b1["id"], b2["id"], b3["id"]))
            and by_id[b4["id"]]["status"] == "Approved"
            and (by_id[b4["id"]].get("approvedClip") or {}).get("assetId") == "verifier-out-4"
            and b4["id"] in (cancel.get("preservedCompletedBatchIds") or [])
            and len(sink()) == 1
        )
        gate("STOP_PRESERVES_STATE", ok, f"batches={len(m['batchBlocks'])} preserved={cancel.get('preservedCompletedBatchIds')}")

        # Resume: approved never resubmitted; cancelled continue
        before_resume = len(sink())
        s, _ = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/cancel", {"action": "resume_incomplete_only"})
        s, gen = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/generate", {"scope": "full"})
        assert s == 200 and gen.get("ok")
        records = sink()
        new_records = records[before_resume:]
        ok = (
            all(r["request"]["batchBlockId"] != b4["id"] for r in records)
            and len(new_records) == 1
            and new_records[0]["request"]["batchBlockId"] == b1["id"]
        )
        m = get_master(pid, sid)
        by_id = {b["id"]: b for b in m["batchBlocks"]}
        ok = ok and by_id[b1["id"]]["status"] == "Generating" and by_id[b4["id"]]["status"] == "Approved"
        gate("RESUME_SKIPS_APPROVED", ok, f"new={len(new_records)} target={new_records[0]['request']['batchBlockId'] if new_records else None} b4_records={sum(1 for r in records if r['request']['batchBlockId'] == b4['id'])}")
    finally:
        req("DELETE", f"/api/projects/{pid}")

    # SCALE_TIERS — 10/25 persistence, no cap
    pid, sid = new_verifier_project()
    try:
        for tier in (10, 25):
            m = get_master(pid, sid)
            while len(m["batchBlocks"]) < tier:
                add_batch(pid, sid, 2.0)
                m = get_master(pid, sid)
            ids = [b["id"] for b in m["batchBlocks"]]
            m2 = get_master(pid, sid)  # reload
            ok = len(set(ids)) == len(ids) and [b["id"] for b in m2["batchBlocks"]] == ids
            gate(f"SCALE_TIER_{tier}", ok, f"batches={len(ids)} unique={len(set(ids))} persisted={ok}")
    finally:
        req("DELETE", f"/api/projects/{pid}")


def artifact_gates() -> None:
    """Artifact gates — preflight verdict + preview resolver evidence."""
    preflight = ARTIFACT_DIR / "comfyui-preflight.json"
    if not preflight.is_file():
        gate("COMFYUI_PREFLIGHT_VERDICT", False, "artifact missing — run scripts/certify_comfyui_preflight.py")
    else:
        data = json.loads(preflight.read_text(encoding="utf-8"))
        h3 = data.get("providers", {}).get("minimax_h3_route_a", {})
        ok = (
            data.get("ok") is True
            and h3.get("verdict") == "READY FOR MANUAL GENERATION"
            and data.get("gpuExecutionEnqueued") is False
        )
        gate("COMFYUI_PREFLIGHT_VERDICT", ok,
             f"overall={data.get('verdict')} h3={h3.get('verdict')} gpuEnqueued={data.get('gpuExecutionEnqueued')}")

    resolver = REPO_ROOT / "studio-web" / "src" / "components" / "timeline-master" / "resolveTimelineAtTime.ts"
    dist = REPO_ROOT / "studio-web" / "dist"
    dist_index = dist / "index.html"
    resolver_ok = resolver.is_file() and "resolveTimelineAtTime" in resolver.read_text(encoding="utf-8")
    build_fresh = dist_index.is_file() and dist_index.stat().st_mtime >= resolver.stat().st_mtime
    gate("PREVIEW_RESOLVER_ARTIFACT", resolver_ok and build_fresh,
         f"resolver={resolver_ok} dist_fresh={build_fresh}")


# ---------------------------------------------------------------------------
# Timeline Full Audit gates (t7): drift contract, export artifacts, UI timing
# format, console cleanliness
# ---------------------------------------------------------------------------

def drift_contract_gates() -> None:
    """DRIFT_CONTRACT — topology/bindings fingerprint split is live and the
    registry is in sync with the builders. Export gates require the Beta API
    started with ADEPT_TIMELINE_WORKFLOW_EXPORT=1."""
    # 1. Registry sync: dry-run the migration — changed must be 0 and every
    # offline-buildable entry must carry fingerprints.topologyHash.
    import subprocess as _sp

    mig = _sp.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "migrate_video_registry_topology.py")],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    try:
        report = json.loads(mig.stdout)
    except json.JSONDecodeError:
        report = None
    if mig.returncode != 0 or report is None:
        gate("DRIFT_CONTRACT_REGISTRY_SYNC", False,
             f"migration dry-run failed rc={mig.returncode}: {(mig.stderr or mig.stdout)[:200]}")
    else:
        built = [r for r in report["results"] if r["result"] == "OK"]
        built_missing = [r["workflowKey"] for r in built if not r.get("topologyHash")]
        bindings_bad = [r["workflowKey"] for r in built if r.get("bindingsOk") is False]
        ok = report["changed"] == 0 and not built_missing and not bindings_bad
        gate("DRIFT_CONTRACT_REGISTRY_SYNC", ok,
             f"changed={report['changed']} buildable={len(built)} missingTopo={built_missing} bindingsBad={bindings_bad}")

    # 2. Registry coverage: ltx.simple_i2v + ltx.scene (the Timeline drift
    # defendants) carry certified topologyHash values.
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_key = {e.get("workflowKey"): e for e in data.get("entries", [])}
    for key in ("ltx.simple_i2v", "ltx.scene"):
        topo = ((by_key.get(key) or {}).get("fingerprints") or {}).get("topologyHash")
        gate(f"DRIFT_CONTRACT_TOPOLOGY_CERTIFIED[{key}]", bool(topo), str(topo or "missing")[:60])

    # 3. Live export: build the real graph via the export endpoint and assert
    # topologyMatch + bindingsValid (requires ADEPT_TIMELINE_WORKFLOW_EXPORT=1).
    pid, sid = new_verifier_project()
    try:
        m = get_master(pid, sid)
        batch = m["batchBlocks"][0]
        # LTX is I2V-only: attach a start frame or the export fails fast with
        # START_FRAME_REQUIRED (same contract the wiring cert gates Q/S use).
        start_asset = upload_image(pid, "verifier-drift-start")
        req("PATCH", f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch['id']}",
            {"generatorId": "ltx-local", "plannedDuration": 5.0,
             "promptSegments": [{
                 "id": "ps-drift", "start": 0, "length": 5.0, "text": "drift contract probe",
                 "role": "primary", "strength": 1, "anchorIds": [],
                 "executionStrategy": "compiled", "versionId": "psv-drift",
             }],
             "sourceAnchors": [{"kind": "image", "assetId": start_asset,
                                "label": "start", "atTime": 0, "strength": 1}]})
        s, exp = req("POST",
                     f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch['id']}/workflow-export")
        if s == 404:
            gate("DRIFT_CONTRACT_LIVE_BUILD", False,
                 "export endpoint 404 — restart Beta API with ADEPT_TIMELINE_WORKFLOW_EXPORT=1")
            gate("EXPORT_ARTIFACTS", False, "export endpoint unavailable")
            return
        ok = s == 200 and exp.get("topologyMatch") is True and exp.get("bindingsValid") is True
        gate("DRIFT_CONTRACT_LIVE_BUILD", ok,
             f"topologyMatch={exp.get('topologyMatch')} bindingsValid={exp.get('bindingsValid')} "
             f"workflow={exp.get('workflowKey')}")

        artifacts = exp.get("artifacts") or {}
        files_ok = True
        details = []
        for kind in ("workflow", "api", "bindings", "fingerprints"):
            p = Path(artifacts.get(kind) or "")
            exists = p.is_file()
            files_ok = files_ok and exists
            details.append(f"{kind}={'ok' if exists else 'MISSING'}")
        fp_path = Path(artifacts.get("fingerprints") or "")
        fp = json.loads(fp_path.read_text(encoding="utf-8")) if fp_path.is_file() else {}
        content_ok = fp.get("topologyMatch") is True and fp.get("bindingsValid") is True
        gate("EXPORT_ARTIFACTS", files_ok and content_ok,
             f"{' '.join(details)} fingerprintsContent={'ok' if content_ok else 'BAD'}")
    finally:
        req("DELETE", f"/api/projects/{pid}")


def drift_live_evidence_gate() -> None:
    """DRIFT_LIVE_EVIDENCE — the CURRENT API process instance proves the
    topology+bindings path and shows zero legacy graphHash failures.

    Evidence is bound to the process instance, not a generic restart marker:
    the API listener PID (data/runtime/api.pid, reconciled by the supervisor)
    must be running; its start timestamp scopes the api.log scan; only log
    records at/after that start (supervisor pump prefixes every line with an
    ISO timestamp) are considered. Requires drift_contract_gates() to have run
    first in this verifier session so a fresh workflowFingerprint line exists.
    """
    import re
    import subprocess as _sp
    from datetime import datetime, timedelta

    pid_file = REPO_ROOT / "data" / "runtime" / "beta" / "pids" / "api.pid"
    log_file = REPO_ROOT / "data" / "runtime" / "logs" / "beta" / "api.log"
    if not pid_file.exists() or not log_file.exists():
        gate("DRIFT_LIVE_EVIDENCE", False, f"missing pid/log file (pid={pid_file.exists()} log={log_file.exists()})")
        return
    api_pid = pid_file.read_text(encoding="utf-8").strip()

    probe = _sp.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-Process -Id {api_pid} -ErrorAction SilentlyContinue).StartTime.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')"],
        capture_output=True, text=True, timeout=30,
    )
    start_raw = (probe.stdout or "").strip()
    if probe.returncode != 0 or not start_raw:
        gate("DRIFT_LIVE_EVIDENCE", False, f"api pid {api_pid} not running or start time unreadable")
        return
    # Truncate to whole seconds (pump prefix granularity) with small tolerance.
    start = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M:%SZ") - timedelta(seconds=3)

    prefix = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\]")
    in_interval: list[str] = []
    for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = prefix.match(line)
        if not m:
            continue  # unprefixed lines predate the timestamped-pump hardening
        if datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ") >= start:
            in_interval.append(line)

    topo_lines = [
        ln for ln in in_interval
        if "workflowFingerprint" in ln and "selectedPath=topology" in ln
        and "topologyMatch=true" in ln and "legacyGraphHashCheck=false" in ln
    ]
    legacy_failures = [ln for ln in in_interval if "graphHash mismatch" in ln]
    ok = bool(topo_lines) and not legacy_failures
    gate("DRIFT_LIVE_EVIDENCE", ok,
         f"apiPid={api_pid} apiStart={start_raw} intervalLines={len(in_interval)} "
         f"topologyEvidence={len(topo_lines)} legacyGraphHashFailures={len(legacy_failures)}")


def ui_format_console_gates() -> None:
    """UI_TIMING_FORMAT + CONSOLE_CLEANLINESS evidence gates."""
    fmt = REPO_ROOT / "studio-web" / "src" / "lib" / "formatDuration.ts"
    dist_index = REPO_ROOT / "studio-web" / "dist" / "index.html"
    fmt_ok = fmt.is_file() and "formatDurationSeconds" in fmt.read_text(encoding="utf-8")
    fresh = dist_index.is_file() and fmt.is_file() and dist_index.stat().st_mtime >= fmt.stat().st_mtime
    gate("UI_TIMING_FORMAT", fmt_ok and fresh, f"formatDurationSeconds={fmt_ok} dist_fresh={fresh}")

    t_art = ARTIFACT_DIR / "T-console-cleanliness.json"
    if not t_art.is_file():
        gate("CONSOLE_CLEANLINESS", False,
             "artifact missing — run wiring cert gate T (timeline-multi-batch-wiring-cert.spec.ts)")
    else:
        data = json.loads(t_art.read_text(encoding="utf-8"))
        ok = not data.get("consoleErrors") and not data.get("failedRequests")
        gate("CONSOLE_CLEANLINESS", ok,
             f"consoleErrors={len(data.get('consoleErrors') or [])} failedRequests={len(data.get('failedRequests') or [])}")


# ---------------------------------------------------------------------------
# Navigation gates (Addendum 1): 9 gates — 7 Playwright NAV results + 2
# source-contract checks.
# ---------------------------------------------------------------------------

def navigation_gates() -> None:
    art = FULL_AUDIT_ARTIFACTS / "nav-routing-cert.json"
    nav: dict = {}
    if not art.is_file():
        for nav_id in ("NAV-1", "NAV-2", "NAV-3", "NAV-4", "NAV-5", "NAV-6", "NAV-7"):
            gate(nav_id, False, "nav-routing-cert.json missing — run project-workspace-routing.spec.ts")
    else:
        nav = json.loads(art.read_text(encoding="utf-8")).get("gates") or {}
        for nav_id in ("NAV-1", "NAV-2", "NAV-3", "NAV-4", "NAV-5", "NAV-6", "NAV-7"):
            entry = nav.get(nav_id)
            gate(nav_id, bool(entry and entry.get("ok")),
                 (entry or {}).get("detail") or "not recorded")

    # Source contract: routing effect never falls back to workspace memory.
    editor = (REPO_ROOT / "studio-web" / "src" / "pages" / "ProjectEditor.tsx").read_text(encoding="utf-8")
    prefs = (REPO_ROOT / "studio-web" / "src" / "workspacePrefs.ts").read_text(encoding="utf-8")
    import re as _re

    routing_fx = _re.search(
        r"const requested = resolveWorkspace\(raw\);(?P<body>.*?)setWorkspaceProjectId\(id\);",
        editor, _re.S)
    body = routing_fx.group("body") if routing_fx else ""
    no_silent_resume = 'requested || "home"' in body and "loadLastWorkspace" not in body
    gate("NAV_NO_SILENT_RESUME_SOURCE", no_silent_resume,
         'routing effect uses requested || "home" with no loadLastWorkspace fallback'
         if no_silent_resume else "routing effect still references workspace memory")

    per_project = "readMap" in prefs and "map[projectId] = canonical" in prefs and "loadLastWorkspace(projectId" in prefs
    gate("NAV_WORKSPACE_MEMORY_PER_PROJECT", per_project,
         "lastWorkspaceByProject map keyed by projectId" if per_project else "global single-record store detected")


# ---------------------------------------------------------------------------
# Stability gates (Addendum 2): 11 gates — dual-metric soak + lifecycle +
# logging + ownership evidence.
# ---------------------------------------------------------------------------

def _netstat_listeners(port: int) -> list[int]:
    import subprocess as _sp
    try:
        out = _sp.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="ignore")
    except Exception:
        return []
    pids: list[int] = []
    for line in out.splitlines():
        if "LISTENING" not in line.upper() or f":{port} " not in line:
            continue
        parts = line.split()
        try:
            pids.append(int(parts[-1]))
        except (ValueError, IndexError):
            continue
    return sorted(set(pids))


def stability_gates() -> None:
    soak_path = FULL_AUDIT_ARTIFACTS / "beta-health-soak.json"
    surfaces_path = FULL_AUDIT_ARTIFACTS / "beta-soak-creator-surfaces.json"
    audit_doc = FULL_AUDIT_DIR / "BETA_SERVER_STABILITY_AUDIT.md"

    soak = json.loads(soak_path.read_text(encoding="utf-8")) if soak_path.is_file() else None
    surfaces = json.loads(surfaces_path.read_text(encoding="utf-8")) if surfaces_path.is_file() else None

    gate("STAB_AUDIT_REPORT", audit_doc.is_file(),
         "BETA_SERVER_STABILITY_AUDIT.md present" if audit_doc.is_file() else "missing")

    if soak is None:
        for name in ("STAB_NO_UNINTENDED_RESTARTS", "STAB_NO_FAILED_HEALTH_SAMPLES",
                     "STAB_SOAK_DURATION", "STAB_PORTS_SINGLE_LISTENER"):
            gate(name, False, "beta-health-soak.json missing — run scripts/beta_health_monitor.py")
    else:
        counters = soak.get("counters") or {}
        gate("STAB_NO_UNINTENDED_RESTARTS", counters.get("processRestartCount") == 0,
             f"processRestartCount={counters.get('processRestartCount')}")
        gate("STAB_NO_FAILED_HEALTH_SAMPLES", counters.get("failedHealthSampleCount") == 0,
             f"failedHealthSampleCount={counters.get('failedHealthSampleCount')}")
        # Soak duration: use the monitor's recorded wall-clock window, not
        # sample count × interval (each sample does HTTP probes + netstat, so
        # the real interval exceeds the nominal one).
        duration_min = 0.0
        try:
            started = datetime.fromisoformat(str(soak.get("startedAt")).replace("Z", "+00:00"))
            ended = datetime.fromisoformat(str(soak.get("endedAt")).replace("Z", "+00:00"))
            duration_min = (ended - started).total_seconds() / 60.0
        except Exception:
            duration_min = 0.0
        gate(
            "STAB_SOAK_DURATION",
            duration_min >= 29.0,
            f"duration={duration_min:.1f} min samples={counters.get('sampleCount')}",
        )
        last = (soak.get("samples") or [{}])[-1]
        ports = last.get("ports") or {}
        api_count = (ports.get("api") or {}).get("listenerCount")
        web_count = (ports.get("web") or {}).get("listenerCount")
        gate("STAB_PORTS_SINGLE_LISTENER", api_count == 1 and web_count == 1,
             f"apiListeners={api_count} webListeners={web_count}")

    if surfaces is None:
        gate("STAB_SOAK_CREATOR_SURFACES", False,
             "beta-soak-creator-surfaces.json missing — run scripts/soak_beta_creator_surfaces.mjs")
    else:
        ok = (
            surfaces.get("verdict") == "SOAK CLEAN"
            and surfaces.get("stepFailureCount") == 0
            and len(surfaces.get("iterations") or []) >= 20
        )
        gate("STAB_SOAK_CREATOR_SURFACES", ok,
             f"verdict={surfaces.get('verdict')} iterations={len(surfaces.get('iterations') or [])} "
             f"stepFailures={surfaces.get('stepFailureCount')}")

    # pid files match the real port listeners (post-reconciliation contract).
    pid_dir = REPO_ROOT / "data" / "runtime" / "beta" / "pids"
    try:
        api_pid = int((pid_dir / "api.pid").read_text().strip())
        web_pid = int((pid_dir / "web.pid").read_text().strip())
    except Exception:
        api_pid = web_pid = -1
    api_listeners = _netstat_listeners(8758)
    web_listeners = _netstat_listeners(8760)
    gate("STAB_PID_FILES_MATCH_LISTENERS",
         api_pid in api_listeners and web_pid in web_listeners,
         f"api.pid={api_pid} listeners={api_listeners} web.pid={web_pid} listeners={web_listeners}")

    # Logging hardening: supervisor log lines are timestamped and service
    # exits carry pid + exit code.
    sup_log = REPO_ROOT / "data" / "runtime" / "logs" / "beta" / "supervisor.log"
    log_ok = False
    if sup_log.is_file():
        lines = [l for l in sup_log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        tail = lines[-40:]
        log_ok = bool(tail) and all(l.startswith("[") for l in tail)
    gate("STAB_LOGGING_HARDENED", log_ok, "supervisor.log tail fully timestamped" if log_ok else "untimestamped lines in supervisor.log tail")

    # Deterministic Stop/Start: today's launcher log shows clean cycles.
    launcher = REPO_ROOT / "data" / "runtime" / "logs" / "beta" / "launcher.log"
    cycles = 0
    if launcher.is_file():
        today = time.strftime("%Y-%m-%d", time.gmtime())
        cycles = sum(
            1
            for line in launcher.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith(f"[{today}") and "Runtime READY" in line
        )
    gate("STAB_START_STOP_DETERMINISTIC", cycles >= 3, f"ready_cycles_today={cycles}")

    # Playwright ownership: exactly one supervisor + one listener per port
    # right now (no cert-stub strays, no duplicate supervisors).
    sup_pid_file = pid_dir / "supervisor.pid"
    sup_alive = False
    if sup_pid_file.is_file():
        try:
            sup_pid = int(sup_pid_file.read_text().strip())
            import subprocess as _sp
            out = _sp.check_output(["tasklist", "/FI", f"PID eq {sup_pid}", "/NH"], text=True, errors="ignore")
            sup_alive = str(sup_pid) in out and "No tasks" not in out
        except Exception:
            sup_alive = False
    single = len(api_listeners) == 1 and len(web_listeners) == 1
    gate("STAB_PLAYWRIGHT_OWNERSHIP", sup_alive and single,
         f"supervisorAlive={sup_alive} apiListeners={len(api_listeners)} webListeners={len(web_listeners)}")

    # ERR_NETWORK_CHANGED classification documented in the stability audit.
    classified = audit_doc.is_file() and "ERR_NETWORK_CHANGED" in audit_doc.read_text(encoding="utf-8")
    gate("STAB_ERR_NETWORK_CHANGED_CLASSIFIED", classified,
         "client-side classification documented" if classified else "not documented")


def main() -> int:
    # health
    s, _ = req("GET", "/api/health")
    gate("health", s == 200, f"status={s}")

    # project/scene
    _, projects = req("GET", "/api/projects")
    plist = projects if isinstance(projects, list) else projects.get("projects", [])
    pid = plist[0]["id"]
    _, scenes = req("GET", f"/api/projects/{pid}/scenes")
    slist = scenes if isinstance(scenes, list) else scenes.get("scenes", [])
    sid = slist[0]["id"]

    # 1. PUT /director preserves master
    _, m1 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
    before = len(m1["master"]["batchBlocks"])
    while before < 2:
        req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches", {"plannedDuration": 5.0})
        _, m1 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
        before = len(m1["master"]["batchBlocks"])
    cur = req("GET", f"/api/projects/{pid}/scenes/{sid}/director")[1]
    body = {k: v for k, v in cur.items() if k in {
        "media_mode", "duration_sec", "image_clips", "video_clips", "prompt_segments",
        "camera_clips", "audio_clips", "sfx_clips", "lipsync", "playhead", "guidance_priority",
    }}
    body["duration_sec"] = float(body.get("duration_sec") or 5) + 0.001
    req("PUT", f"/api/projects/{pid}/scenes/{sid}/director", body)
    _, m2 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
    after = len(m2["master"]["batchBlocks"])
    gate("PUT_DIRECTOR_PRESERVES_MASTER", after == before, f"before={before} after={after}")

    # 2. per-batch clip isolation
    batches = sorted(m2["master"]["batchBlocks"], key=lambda b: b["order"])
    a, b = batches[0], batches[1]
    a0, b0 = len(a.get("visualClips", [])), len(b.get("visualClips", []))
    req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{b['id']}/clips",
         {"kind": "image", "assetId": "verifier-iso", "start": 0, "length": 2, "label": "V"})
    _, m3 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
    a1 = next(x for x in m3["master"]["batchBlocks"] if x["id"] == a["id"])
    b1 = next(x for x in m3["master"]["batchBlocks"] if x["id"] == b["id"])
    gate("BATCH_OWNED_CLIPS_ISOLATION",
         len(a1.get("visualClips", [])) == a0 and len(b1.get("visualClips", [])) == b0 + 1,
         f"A={a0}->{len(a1.get('visualClips', []))} B={b0}->{len(b1.get('visualClips', []))}")

    # 3. capability gating
    _, gens = req("GET", f"{TL}/generators")
    gmap = {g["id"]: g for g in gens.get("generators", [])}
    gate("LTX_SUPPORTS_TIMELINE", gmap.get("ltx-local", {}).get("supportsTimelineGeneration") is True, str(gmap.get("ltx-local", {}).get("supportsTimelineGeneration")))
    gate("WAN_UNSUPPORTED_TIMELINE", gmap.get("wan-local", {}).get("supportsTimelineGeneration") is False, str(gmap.get("wan-local", {}).get("supportsTimelineGeneration")))
    req("PATCH", f"{TL}/projects/{pid}/scenes/{sid}/batches/{a['id']}", {"generatorId": "wan-local"})
    _, gr = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches/{a['id']}/generate")
    gate("WAN_GENERATION_GATED", gr.get("ok") is False and gr.get("error") == "GENERATOR_UNSUPPORTED_FOR_TIMELINE", str(gr.get("error")))
    req("PATCH", f"{TL}/projects/{pid}/scenes/{sid}/batches/{a['id']}", {"generatorId": "ltx-local"})

    # 4. no artificial cap
    _, m4 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
    n = len(m4["master"]["batchBlocks"])
    if n < 10:
        for _ in range(10 - n):
            req("POST", f"{TL}/projects/{pid}/scenes/{sid}/batches", {"plannedDuration": 2.0})
        _, m4 = req("GET", f"{TL}/projects/{pid}/scenes/{sid}/master")
        n = len(m4["master"]["batchBlocks"])
    gate("NO_ARTIFICIAL_BATCH_CAP", n >= 10, f"batches={n}")

    # 5. orchestratorMode surfaced
    _, gs = req("POST", f"{TL}/projects/{pid}/scenes/{sid}/generate", {"scope": "full"})
    gate("ORCHESTRATOR_MODE_SURFACED", bool(gs.get("orchestratorMode")), str(gs.get("orchestratorMode")))

    # 6. web up
    s2, _ = req("GET", "/")
    gate("BETA_WEB_UP", s2 == 200, f"status={s2}")

    # 7. wiring gates (cert stub required — no GPU execution)
    if stub_enabled():
        gate("CERT_STUB_ENABLED", True, "ADEPT_TIMELINE_CERT_STUB=1")
        wiring_gates()
    else:
        gate("CERT_STUB_ENABLED", False,
             "stub endpoints 404 — restart Beta API with ADEPT_TIMELINE_CERT_STUB=1 to run wiring gates")

    # 8. artifact gates
    artifact_gates()

    # 9. Timeline Full Audit gates (drift contract + export + UI format + console)
    drift_contract_gates()
    drift_live_evidence_gate()
    ui_format_console_gates()

    # 10. Navigation gates (Addendum 1)
    navigation_gates()

    # 11. Stability gates (Addendum 2)
    stability_gates()

    failed = [name for name, ok, _ in results if not ok]
    print("\n=== VERIFIER SUMMARY ===")
    for name, ok, detail in results:
        print(f"  {'✓' if ok else '✗'} {name}")
    if failed:
        print(f"\nNO-GO — {len(failed)} gate(s) failed: {', '.join(failed)}")
        return 1
    print("\nGO — all gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
