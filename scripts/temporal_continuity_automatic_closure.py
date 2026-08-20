"""Automatic Timeline two-batch closure. Review must run inside the live API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8758"
PROJECT_ID = "42ff15c3-5c39-4a7c-a430-e58e3719b6da"
SCENE_ID = "2e3a2cfc-0094-4f7c-887a-5befa08db347"
OUT = ROOT / "docs" / "release-gate" / "codirector-temporal-continuity" / "artifacts"
PROMPT_B1 = (
    "Cinematic two-shot. Anadriya and Korri walk a long dim corridor. "
    "Camera dollies with them. Korri begins turning toward Anadriya. "
    "The turn is unfinished at the end of the shot. Preserve identity and screen geography."
)
PROMPT_B2 = (
    "Continue the same corridor walk without resetting. "
    "Finish Korri's turn toward Anadriya. Keep walking, camera dolly, lighting, and sides of frame."
)


def _req(method: str, path: str, data: dict | None = None, timeout: int = 180) -> dict:
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _master() -> dict:
    return _req("GET", f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/master")


def _ffmpeg(*args: str) -> None:
    proc = subprocess.run(["ffmpeg", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[:400])


def _asset_path(asset_id: str) -> Path | None:
    dest = ROOT / "data" / "assets" / PROJECT_ID
    if dest.is_dir():
        for path in dest.iterdir():
            if path.stem == asset_id:
                return path
    renders = ROOT / "data" / "projects" / PROJECT_ID / "renders"
    if renders.is_dir():
        matches = sorted(renders.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.codirector.video_intelligence.cadence import resolve_cadence
    from app.codirector.video_intelligence.contracts import CoDirectorContinuityPolicy
    from app.codirector.video_intelligence.gpu_lease import probe_comfy_generation_ready
    from app.codirector.video_intelligence.service import packet_blocks_submit, review_completed_batch
    from app.director_timeline_w46.contracts import SceneTimelineMaster

    comfy = probe_comfy_generation_ready()
    print("COMFY", comfy.get("tier"), flush=True)
    if not comfy.get("workflowReady"):
        (OUT / "automatic-closure-evidence.json").write_text(json.dumps({"comfy": comfy}, indent=2), encoding="utf-8")
        print("COMFY_NOT_WORKFLOW_READY", flush=True)
        return 2

    health = _req("GET", "/api/health")
    vi = _req("GET", "/api/setup/lifecycle/video-intelligence")
    worker = str(vi.get("workerPython") or "")
    print("API_REV", health.get("apiRevision"), "WORKER", worker, "CERT", vi.get("videochat3Certified"), flush=True)
    if "videochat3-worker" not in worker.replace("\\", "/"):
        print("WORKER_PYTHON_NOT_GPU_VENV", worker, flush=True)
        return 2
    if not vi.get("capabilities", {}).get("timelineVisualReview"):
        print("TIMELINE_VISUAL_REVIEW_FALSE", flush=True)
        return 2

    cadence = resolve_cadence(
        CoDirectorContinuityPolicy(reviewCadence="automatic"),
        prompt=PROMPT_B1,
        camera_motion="dolly",
        character_count=2,
    )
    dialogue = resolve_cadence(
        CoDirectorContinuityPolicy(reviewCadence="automatic"),
        prompt="quiet dialogue sitting and talking",
    )
    print("CADENCE", cadence, "DIALOGUE", dialogue, flush=True)

    policy = _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/codirector-continuity-policy",
        {"enabled": True, "reviewCadence": "automatic", "protection": "strong"},
    )
    print("POLICY", policy.get("coDirectorContinuityPolicy"), flush=True)

    workspace = _master()
    master = workspace.get("master") or {}
    master["coDirectorContinuityPolicy"] = policy.get("coDirectorContinuityPolicy") or master.get(
        "coDirectorContinuityPolicy"
    )
    batches = sorted(master.get("batchBlocks") or [], key=lambda b: b.get("order", 0))
    if len(batches) < 2:
        print("NEED_TWO_BATCHES", flush=True)
        return 2
    b1 = batches[0]
    b2 = batches[1]
    if not ((b1.get("approvedClip") or {}).get("assetId")):
        print("B1_NOT_APPROVED", flush=True)
        return 2

    # Pin both batches to the Timeline-visible LTX 2.5 id. No silent 2.3 alias.
    for batch in (b1, b2):
        batch["generatorId"] = "ltx-2.5-distilled"
    for ref in (b2.get("generationJobs") or []):
        if ref.get("status") in ("queued", "running"):
            qid = ref.get("queueJobId")
            if qid:
                try:
                    _req("POST", f"/api/jobs/{qid}/cancel")
                    print("CANCELLED_STUCK", qid, flush=True)
                except Exception as exc:
                    print("CANCEL_STUCK_ERR", qid, exc, flush=True)

    master["temporalPackets"] = [
        p
        for p in (master.get("temporalPackets") or [])
        if not (
            (p.get("source") or {}).get("batchId") == b1["id"]
            and (p.get("source") or {}).get("targetBatchId") == b2["id"]
        )
    ]
    # Direct /generate is blocked for Queued batches (sequential chain only).
    # A retake uses Ready so submit_batch_generation can run the in-API review.
    if b2.get("status") in ("Queued", "Generating", "Approved", "CandidateReady", "Failed"):
        b2["status"] = "Ready"
    _req(
        "PUT",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/master",
        {"master": master},
    )

    from app.codirector.video_intelligence.gpu_lease import query_free_vram_gb

    deadline = time.time() + 8 * 60
    while time.time() < deadline:
        free = query_free_vram_gb()
        print("WAIT_VRAM", free, flush=True)
        if free is not None and free >= 8.0:
            break
        time.sleep(10)

    t_before = time.time()
    try:
        gen2 = _req(
            "POST",
            f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches/{b2['id']}/generate",
            {"draftMode": True},
            timeout=300,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        print("GEN2_HTTP", exc.code, detail, flush=True)
        (OUT / "automatic-closure-evidence.json").write_text(
            json.dumps({"error": detail, "comfy": comfy}, indent=2),
            encoding="utf-8",
        )
        return 2
    t_after = time.time()
    print("GEN2", {k: gen2.get(k) for k in ("ok", "error", "jobId", "queueJobId", "reason")}, flush=True)

    after = _master().get("master") or {}
    packets = list(after.get("temporalPackets") or [])
    packet = None
    for item in reversed(packets):
        src = item.get("source") or {}
        if src.get("batchId") == b1["id"] and src.get("targetBatchId") == b2["id"]:
            packet = item
            break
    request = gen2.get("normalizedRequest") or gen2.get("request") or {}
    provider = ((request.get("providerOptions") or {}).get("temporalContinuation")) or request.get("temporalContinuation")
    job_id = gen2.get("queueJobId") or gen2.get("jobId")
    job = {}
    if job_id:
        try:
            job = _req("GET", f"/api/jobs/{job_id}")
        except Exception as exc:
            job = {"error": str(exc)[:200]}

    evidence = {
        "comfy": comfy,
        "health": {"ok": health.get("ok"), "apiRevision": health.get("apiRevision"), "apiStartedAt": health.get("apiStartedAt")},
        "workerPython": worker,
        "videochat3Certified": vi.get("videochat3Certified"),
        "timelineVisualReview": vi.get("capabilities", {}).get("timelineVisualReview"),
        "cadenceAutomaticCorridor": cadence,
        "cadenceAutomaticDialogue": dialogue,
        "policy": policy.get("coDirectorContinuityPolicy"),
        "batch1Id": b1["id"],
        "batch2Id": b2["id"],
        "generateMs": round((t_after - t_before) * 1000),
        "packet": packet,
        "gen2": {k: gen2.get(k) for k in ("ok", "error", "jobId", "queueJobId", "reason")},
        "temporalContinuation": provider,
        "jobId": job_id,
        "jobCreatedAt": job.get("created_at"),
        "packetCreatedAt": (packet or {}).get("createdAt"),
        "gpuLease": (packet or {}).get("extras", {}).get("gpuLease") if packet else None,
        "gpuPreflight": (packet or {}).get("extras", {}).get("gpuPreflight") if packet else None,
    }
    if packet and job.get("created_at"):
        evidence["packetBeforeJob"] = str(packet.get("createdAt") or "") <= str(job.get("created_at") or "")

    reload_row = _req("GET", f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/temporal-continuity")
    reload_packets = list(reload_row.get("temporalPackets") or reload_row.get("master", {}).get("temporalPackets") or [])
    if not reload_packets and isinstance(reload_row.get("master"), dict):
        reload_packets = list(reload_row["master"].get("temporalPackets") or [])
    # temporal-continuity route may return the policy wrapper
    if not reload_packets:
        reload_packets = list((_master().get("master") or {}).get("temporalPackets") or [])
    evidence["reloadPacketIds"] = [p.get("packetId") for p in reload_packets]
    evidence["reloadKeepsPacket"] = bool(packet) and (packet.get("packetId") in evidence["reloadPacketIds"])

    os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "fail"
    os.environ.pop("ADEPT_ALLOW_PERCEPTION_STUB", None)
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        fail_master = SceneTimelineMaster.model_validate(_master().get("master") or {})
        source = next(b for b in fail_master.batchBlocks if b.id == b1["id"])
        fail_master.temporalPackets = [
            p for p in fail_master.temporalPackets if not (p.source.batchId == b1["id"] and p.source.targetBatchId == "bb_degrade")
        ]
        degraded = review_completed_batch(db, PROJECT_ID, SCENE_ID, fail_master, source, target_batch_id="bb_degrade")
        evidence["controlledDegrade"] = {
            "availability": degraded.availability,
            "reason": degraded.reason,
            "preserve": list(degraded.continuation.preserve or []),
            "directives": list(degraded.continuation.nextBatchDirectives or []),
            "blocksSubmit": packet_blocks_submit(fail_master, "bb_degrade"),
        }
    finally:
        db.close()
        os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "live"

    (OUT / "automatic-closure-evidence.json").write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print("EVIDENCE", OUT / "automatic-closure-evidence.json", flush=True)

    if not gen2.get("ok"):
        print("GEN2_FAILED", gen2.get("error"), flush=True)
        return 2
    if not packet:
        print("NO_IN_API_PACKET", flush=True)
        return 2
    if packet.get("availability") != "ready":
        print("PACKET_NOT_READY", packet.get("availability"), packet.get("reason"), flush=True)
        return 2
    if not (provider or {}).get("applied"):
        print("CONTINUATION_NOT_APPLIED", provider, flush=True)
        return 2

    if job_id:
        deadline = time.time() + 20 * 60
        while time.time() < deadline:
            job = _req("GET", f"/api/jobs/{job_id}")
            print("JOB", job.get("status"), job.get("stage"), flush=True)
            if job.get("status") in ("done", "error", "failed", "cancelled"):
                break
            time.sleep(8)
        params = {}
        try:
            params = json.loads(job.get("params_json") or "{}")
        except Exception:
            params = {}
        hops = {}
        try:
            hist = json.loads(job.get("history_json") or "{}")
            if isinstance(hist, dict):
                hops = ((hist.get("videoRuntime") or {}).get("queueHops") or {})
        except Exception:
            hops = {}
        evidence["jobStatus"] = job.get("status")
        evidence["jobParamsContinuation"] = params.get("temporalContinuation")
        evidence["jobOutput"] = job.get("output_path")
        evidence["comfyPromptId"] = job.get("comfy_prompt_id")
        evidence["requestedModel"] = params.get("requestedModel") or params.get("generatorId")
        evidence["resolvedRuntimeModel"] = params.get("resolvedRuntimeModel")
        evidence["localFirstProvenance"] = params.get("localFirstProvenance")
        evidence["queueHops"] = hops
        evidence["providerAccepted"] = bool(job.get("comfy_prompt_id"))
        (OUT / "automatic-closure-evidence.json").write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
        output = Path(str(job.get("output_path") or ""))
        if output.is_file():
            last = OUT / "auto-b1-last-frame.png"
            first = OUT / "auto-b2-first-frame.png"
            b1_path = None
            clip_id = (b1.get("approvedClip") or {}).get("assetId")
            if clip_id:
                b1_path = _asset_path(str(clip_id))
            renders = ROOT / "data" / "projects" / PROJECT_ID / "renders"
            if b1_path is None and renders.is_dir():
                known = OUT / "batch1.mp4"
                b1_path = known if known.is_file() else None
            if b1_path and b1_path.is_file():
                _ffmpeg("-y", "-sseof", "-0.04", "-i", str(b1_path), "-vframes", "1", str(last))
            _ffmpeg("-y", "-i", str(output), "-vframes", "1", str(first))
            _ffmpeg("-y", "-i", str(output), "-t", "1.5", str(OUT / "auto-b2-first-1p5s.mp4"))
            evidence["autoBatch2Path"] = str(output)
            (OUT / "automatic-closure-evidence.json").write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")

    degrade = evidence.get("controlledDegrade") or {}
    if degrade.get("availability") != "unavailable" or degrade.get("directives"):
        print("DEGRADE_UNEXPECTED", degrade, flush=True)
        return 2
    print("AUTOMATIC_CLOSURE_OK", packet.get("packetId"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
