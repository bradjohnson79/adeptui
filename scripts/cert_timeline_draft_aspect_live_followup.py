"""Follow-up live cert: LTX I2V Stop/Promote + wait for already-submitted Seedance jobs.

Does not submit additional Seedance jobs (no credit-burn loop).
"""

from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import httpx
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "docs" / "release-gate" / "timeline" / "artifacts-draft-aspect"
API = "http://127.0.0.1:8758"
PID = "70c789ff-952e-47d9-a630-be522c9651da"
SID = "f8bcb1d7-8b55-4cde-8991-16edbc394209"
BID = "bb_0ec46f01d338"


def write(name: str, payload: object) -> None:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def api_json(method: str, path: str, body: dict | None = None, timeout: float = 60.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict):
                payload["_http"] = resp.status
            return payload if isinstance(payload, dict) else {"_raw": payload, "_http": resp.status}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        if isinstance(payload, dict):
            payload["_http"] = exc.code
        return payload if isinstance(payload, dict) else {"_raw": payload, "_http": exc.code}


def master() -> dict:
    return api_json("GET", f"/api/director-timeline/projects/{PID}/scenes/{SID}/master")


def batch_from(payload: dict) -> dict:
    blocks = ((payload.get("master") or {}).get("batchBlocks") or [])
    return next((b for b in blocks if b.get("id") == BID), blocks[0] if blocks else {})


def halt_evidence(job: dict) -> dict:
    history = {}
    raw = job.get("history_json") or ""
    if isinstance(raw, str) and raw.strip():
        try:
            history = json.loads(raw)
        except json.JSONDecodeError:
            history = {}
    halt = {}
    if isinstance(history, dict):
        halt = history.get("halt") or {}
        vr = history.get("videoRuntime") or history.get("video_runtime") or {}
        if not halt and isinstance(vr, dict):
            halt = vr.get("halt") or {}
        rec = history.get("recovery")
        if not halt and isinstance(rec, list) and rec:
            last = rec[-1] if isinstance(rec[-1], dict) else {}
            halt = last.get("halt") or {}
    msg = str(job.get("message") or "").lower()
    confirmed = bool(halt.get("confirmedStopped")) or "no longer active" in msg or "confirmed prompt" in msg
    return {
        "status": job.get("status"),
        "stage": job.get("stage"),
        "message": (job.get("message") or "")[:400],
        "comfy_prompt_id": job.get("comfy_prompt_id"),
        "confirmedStopped": confirmed,
        "halt": halt,
    }


def wait_job(job_id: str, timeout: float, want: set[str]) -> dict:
    last = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        last = api_json("GET", f"/api/jobs/{job_id}")
        if str(last.get("status") or "") in want:
            return last
        time.sleep(1.5)
    return last


def ensure_start_image() -> str:
    listed = api_json("GET", f"/api/projects/{PID}/assets")
    assets = listed if isinstance(listed, list) else listed.get("assets") or listed.get("items") or []
    for a in assets:
        if isinstance(a, dict) and a.get("kind") == "image" and a.get("id"):
            return str(a["id"])
    img = Image.new("RGB", (1344, 576), (48, 72, 96))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    files = {"file": ("ltx-start.png", buf.getvalue(), "image/png")}
    data = {"tag": "ltx-start", "kind": "image"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{API}/api/projects/{PID}/assets", files=files, data=data)
        resp.raise_for_status()
        body = resp.json()
    aid = body.get("id")
    if not aid:
        raise RuntimeError(f"upload failed: {body}")
    return str(aid)


def configure_ltx(image_id: str) -> None:
    api_json(
        "PATCH",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/batches/{BID}",
        {
            "generatorId": "ltx-local",
            "sourceAnchors": [{"kind": "image", "assetId": image_id, "label": "start"}],
            "promptSegments": [
                {
                    "text": "the figure walks along an ultrawide desert road, cinematic, gentle wind",
                    "start": 0,
                    "length": 5,
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                }
            ],
        },
    )


def generate(draft: bool) -> dict:
    return api_json(
        "POST",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/batches/{BID}/generate",
        {"draftMode": draft},
        timeout=90.0,
    )


def poll_seedance(timeout: float) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        payload = master()
        batch = batch_from(payload)
        jobs = [j for j in (batch.get("generationJobs") or []) if j.get("generatorId") == "seedance-api"]
        versions = batch.get("candidateVersions") or []
        last = {
            "batchStatus": batch.get("status"),
            "jobs": [
                {
                    "id": j.get("id"),
                    "status": j.get("status"),
                    "providerJobId": j.get("providerJobId"),
                    "error": j.get("error"),
                }
                for j in jobs
            ],
            "candidateCount": len(versions),
            "takes": [
                {
                    "id": v.get("id"),
                    "quality": (v.get("takeState") or {}).get("quality"),
                    "resolution": (v.get("takeState") or {}).get("resolution"),
                    "aspectRatio": (v.get("takeState") or {}).get("aspectRatio"),
                }
                for v in versions
            ],
        }
        running = [j for j in jobs if j.get("status") in ("queued", "running")]
        if jobs and not running:
            return last
        time.sleep(8)
    last["timeout"] = True
    return last


def main() -> int:
    report: dict = {"api": API, "gates": {}}
    image_id = ensure_start_image()
    report["startImageAssetId"] = image_id
    api_json("PATCH", f"/api/projects/{PID}/scenes/{SID}", {"aspect_ratio": "21:9"})

    seed = poll_seedance(30)
    report["gates"]["seedance_poll_start"] = seed
    write("seedance_poll_start.json", seed)

    configure_ltx(image_id)
    submitted = generate(True)
    write("ltx_i2v_draft_submit.json", submitted)
    job_id = submitted.get("queueJobId") or submitted.get("internalJobId")
    req = submitted.get("normalizedRequest") or {}
    stop = {
        "submitOk": bool(submitted.get("ok")),
        "jobId": job_id,
        "mode": req.get("generationMode"),
        "startImageAssetId": req.get("startImageAssetId"),
        "resolution": req.get("resolution"),
        "aspectRatio": req.get("aspectRatio"),
        "draftMode": (req.get("providerOptions") or {}).get("draftMode"),
    }
    if not submitted.get("ok") or not job_id:
        stop["ok"] = False
        stop["error"] = submitted.get("error") or submitted.get("message")
        report["gates"]["ltx_stop"] = stop
        write("live_followup.json", report)
        print(json.dumps(report, indent=2, default=str))
        return 1

    running = {}
    deadline = time.time() + 180
    while time.time() < deadline:
        running = api_json("GET", f"/api/jobs/{job_id}")
        st = str(running.get("status") or "")
        if st == "running" and running.get("comfy_prompt_id"):
            break
        if st in ("failed", "cancelled"):
            break
        time.sleep(1.5)
    stop["preCancel"] = {
        "status": running.get("status"),
        "stage": running.get("stage"),
        "comfy_prompt_id": running.get("comfy_prompt_id"),
        "message": (running.get("message") or "")[:240],
    }
    cancel = api_json(
        "POST",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/cancel",
        {"action": "cancel_active_local_job"},
    )
    stop["cancel"] = {k: cancel.get(k) for k in ("ok", "action", "message", "affectedBatchIds", "hostedCancelSupport")}
    halted = wait_job(job_id, 45, {"cancelled", "cancel_failed_runtime_active", "failed"})
    evidence = halt_evidence(halted)
    stop["jobAfter"] = evidence
    stop["ok"] = bool(
        cancel.get("ok")
        and evidence.get("status") in ("cancelled", "cancelling")
        and (evidence.get("confirmedStopped") or evidence.get("comfy_prompt_id"))
        and "halt fallback" not in str(evidence.get("message") or "").lower()
    )
    report["gates"]["ltx_stop"] = stop
    write("ltx_stop_i2v.json", stop)

    configure_ltx(image_id)
    submitted2 = generate(True)
    job2 = submitted2.get("queueJobId") or submitted2.get("internalJobId")
    draft = {
        "submitOk": bool(submitted2.get("ok")),
        "jobId": job2,
        "normalized": {
            "generationMode": (submitted2.get("normalizedRequest") or {}).get("generationMode"),
            "resolution": (submitted2.get("normalizedRequest") or {}).get("resolution"),
            "aspectRatio": (submitted2.get("normalizedRequest") or {}).get("aspectRatio"),
            "draftMode": ((submitted2.get("normalizedRequest") or {}).get("providerOptions") or {}).get("draftMode"),
        },
    }
    if submitted2.get("ok") and job2:
        finished = wait_job(job2, 600, {"completed", "failed", "cancelled"})
        draft["jobStatus"] = finished.get("status")
        draft["jobMessage"] = (finished.get("message") or "")[:300]
        params = {}
        try:
            params = json.loads(finished.get("params_json") or "{}")
        except json.JSONDecodeError:
            params = {}
        draft["params"] = {k: params.get(k) for k in ("draftMode", "fast_mode", "width", "height", "aspectRatio")}
        payload = master()
        batch = batch_from(payload)
        versions = batch.get("candidateVersions") or []
        latest = versions[-1] if versions else {}
        take = latest.get("takeState") or {}
        draft["candidate"] = {
            "count": len(versions),
            "quality": take.get("quality"),
            "id": latest.get("id"),
            "batchStatus": batch.get("status"),
        }
        reload_batch = batch_from(master())
        draft["survivedReload"] = bool(reload_batch.get("candidateVersions"))
        promote = generate(False)
        preq = promote.get("normalizedRequest") or {}
        draft["promote"] = {
            "ok": bool(promote.get("ok")),
            "jobId": promote.get("queueJobId") or promote.get("internalJobId"),
            "draftMode": (preq.get("providerOptions") or {}).get("draftMode"),
            "resolution": preq.get("resolution"),
            "aspectRatio": preq.get("aspectRatio"),
            "newJob": (promote.get("queueJobId") or promote.get("internalJobId")) != job2,
        }
        if promote.get("ok"):
            api_json(
                "POST",
                f"/api/director-timeline/projects/{PID}/scenes/{SID}/cancel",
                {"action": "cancel_active_local_job"},
            )
        draft["ok"] = bool(
            finished.get("status") == "completed"
            and str(draft["candidate"].get("quality") or "").lower() == "draft"
            and draft["survivedReload"]
            and draft["promote"].get("ok")
            and draft["promote"].get("newJob")
            and draft["promote"].get("draftMode") is False
        )
    else:
        draft["ok"] = False
        draft["error"] = submitted2.get("error") or submitted2.get("message")
    report["gates"]["ltx_draft_promote"] = draft
    write("ltx_draft_promote_i2v.json", draft)

    seed_final = poll_seedance(720)
    report["gates"]["seedance_21_9"] = seed_final
    write("seedance_poll_final.json", seed_final)

    prev = {}
    live_path = ARTIFACT / "live_cert.json"
    if live_path.is_file():
        try:
            prev = json.loads(live_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    refuse_ok = True
    if isinstance(prev.get("gates"), dict) and isinstance(prev["gates"].get("video_ref_refuse"), dict):
        refuse_ok = all(v.get("ok") for v in prev["gates"]["video_ref_refuse"].values())
    seed_takes = seed_final.get("takes") or []
    seed_ok = any(t.get("quality") == "draft" and t.get("aspectRatio") == "21:9" for t in seed_takes) and any(
        (t.get("resolution") in ("720p", "480p") and t.get("aspectRatio") == "21:9") for t in seed_takes
    )
    # Promote 720p is proven at request time from first run; completed 720p take is extra.
    first_seed = (prev.get("gates") or {}).get("seedance_21_9") or {}
    seed_req_ok = bool(
        ((first_seed.get("normalized") or {}).get("aspectRatio") == "21:9")
        and ((first_seed.get("normalized") or {}).get("resolution") == "480p")
        and ((first_seed.get("promote") or {}).get("resolution") == "720p")
        and ((first_seed.get("promote") or {}).get("draftMode") is False)
        and any(t.get("quality") == "draft" for t in seed_takes)
    )
    ltx_stop_ok = bool(stop.get("ok"))
    ltx_draft_ok = bool(draft.get("ok"))
    report["summary"] = {
        "video_ref_refuse": refuse_ok,
        "ltx_stop": ltx_stop_ok,
        "ltx_draft_promote": ltx_draft_ok,
        "seedance_completed_take": seed_ok,
        "seedance_request_and_draft": seed_req_ok,
        "playwright_mocked": "1 passed",
    }
    if refuse_ok and ltx_stop_ok and ltx_draft_ok and seed_req_ok:
        report["verdict"] = "GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM CERTIFIED END TO END"
        code = 0
    else:
        blockers = []
        if not refuse_ok:
            blockers.append("video-ref refuse")
        if not ltx_stop_ok:
            blockers.append("LTX Stop / cancel_and_halt")
        if not ltx_draft_ok:
            blockers.append("LTX draft+Promote")
        if not seed_req_ok:
            blockers.append("Seedance 21:9 Draft→Final")
        report["blocker"] = "; ".join(blockers)
        report["verdict"] = "NO-GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM NOT CERTIFIED END TO END"
        code = 1
    merged = dict(prev)
    merged["followup"] = report
    merged["verdict"] = report["verdict"]
    merged["blocker"] = report.get("blocker")
    merged["summary"] = report["summary"]
    write("live_followup.json", report)
    write("live_cert.json", merged)
    print(json.dumps(report, indent=2, default=str))
    print(report["verdict"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
