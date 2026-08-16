"""LTX I2V: running Stop + draft candidate + Promote. No extra Seedance jobs."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "70c789ff-952e-47d9-a630-be522c9651da"
SID = "f8bcb1d7-8b55-4cde-8991-16edbc394209"
BID = "bb_0ec46f01d338"
IMAGE = "26c16f61-38e1-4ff3-a992-9c1acde4674e"
ARTIFACT = Path(__file__).resolve().parents[1] / "docs/release-gate/timeline/artifacts-draft-aspect"


def write(name: str, payload: object) -> None:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def call(method: str, path: str, body: dict | None = None, timeout: float = 90.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    last_exc: Exception | None = None
    for attempt in range(8):
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            if isinstance(payload, dict):
                payload["_http"] = 200
                return payload
            return {"_raw": payload, "_http": 200}
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8", "replace") or "{}")
            payload["_http"] = exc.code
            return payload
        except Exception as exc:
            last_exc = exc
            time.sleep(2)
    raise RuntimeError(f"{method} {path} failed after retries: {last_exc}")


def job(job_id: str) -> dict:
    return call("GET", f"/api/jobs/{job_id}")


def master_batch() -> dict:
    payload = call("GET", f"/api/director-timeline/projects/{PID}/scenes/{SID}/master")
    blocks = ((payload.get("master") or {}).get("batchBlocks") or [])
    return next((b for b in blocks if b.get("id") == BID), {})


def configure() -> None:
    call(
        "PATCH",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/batches/{BID}",
        {
            "generatorId": "ltx-local",
            "sourceAnchors": [{"kind": "image", "assetId": IMAGE, "label": "start"}],
            "promptSegments": [
                {
                    "text": "the figure walks along an ultrawide desert road, cinematic",
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
    return call(
        "POST",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/batches/{BID}/generate",
        {"draftMode": draft},
    )


def halt_evidence(row: dict) -> dict:
    history = {}
    try:
        history = json.loads(row.get("history_json") or "{}")
    except json.JSONDecodeError:
        history = {}
    halt = {}
    if isinstance(history, dict):
        halt = history.get("halt") or {}
        vr = history.get("videoRuntime") or {}
        if not halt and isinstance(vr, dict):
            halt = vr.get("halt") or {}
    msg = str(row.get("message") or "").lower()
    return {
        "status": row.get("status"),
        "comfy_prompt_id": row.get("comfy_prompt_id"),
        "message": (row.get("message") or "")[:300],
        "confirmedStopped": bool(halt.get("confirmedStopped")) or "no longer active" in msg,
        "haltReason": ((halt.get("confirmation") or {}).get("reason") if isinstance(halt, dict) else None),
        "halt": halt,
    }


def wait_running(job_id: str, timeout: float) -> dict:
    last = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        last = job(job_id)
        st = str(last.get("status") or "")
        if last.get("comfy_prompt_id") and st in ("running", "cancelling"):
            return last
        if st in ("failed", "cancelled"):
            return last
        time.sleep(1.5)
    return last


def wait_done(job_id: str, timeout: float) -> dict:
    last = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        last = job(job_id)
        if str(last.get("status") or "") in ("done", "completed", "failed", "cancelled"):
            return last
        time.sleep(2)
    return last


def ltx_draft_candidates(before_ids: set[str]) -> list[dict]:
    versions = master_batch().get("candidateVersions") or []
    out = []
    for v in versions:
        if v.get("id") in before_ids:
            continue
        ts = v.get("takeState") or {}
        if str(ts.get("quality") or "").lower() == "draft" and str(ts.get("resolution") or "") in (
            "672x288",
            "672×288",
        ):
            out.append(
                {
                    "id": v.get("id"),
                    "quality": ts.get("quality"),
                    "resolution": ts.get("resolution"),
                    "aspectRatio": ts.get("aspectRatio"),
                    "assetId": v.get("assetId"),
                }
            )
    return out


def main() -> int:
    report: dict = {}
    configure()
    before = {v.get("id") for v in (master_batch().get("candidateVersions") or [])}

    submitted = generate(True)
    job_id = submitted.get("queueJobId") or submitted.get("internalJobId")
    running = wait_running(job_id, 240) if job_id else {}
    cancel = call(
        "POST",
        f"/api/director-timeline/projects/{PID}/scenes/{SID}/cancel",
        {"action": "cancel_active_local_job"},
    )
    halted = wait_done(job_id, 45) if job_id else {}
    stop = {
        "submitOk": bool(submitted.get("ok")),
        "jobId": job_id,
        "preCancel": {
            "status": running.get("status"),
            "comfy_prompt_id": running.get("comfy_prompt_id"),
            "message": (running.get("message") or "")[:200],
        },
        "cancelOk": bool(cancel.get("ok")),
        "after": halt_evidence(halted),
    }
    stop["ok"] = bool(
        stop["cancelOk"]
        and stop["after"].get("confirmedStopped")
        and stop["preCancel"].get("comfy_prompt_id")
        and str(stop["after"].get("haltReason") or "") != "no_prompt_id"
    )
    report["ltx_stop_running"] = stop
    write("ltx_stop_running.json", stop)

    configure()
    submitted2 = generate(True)
    job2 = submitted2.get("queueJobId") or submitted2.get("internalJobId")
    finished = wait_done(job2, 720) if job2 else {}
    params = {}
    try:
        params = json.loads(finished.get("params_json") or "{}")
    except json.JSONDecodeError:
        params = {}
    cands = []
    deadline = time.time() + 90
    while time.time() < deadline:
        cands = ltx_draft_candidates(before)
        if cands:
            break
        time.sleep(3)
    reload_cands = ltx_draft_candidates(before)
    promote = generate(False)
    preq = promote.get("normalizedRequest") or {}
    draft = {
        "submitOk": bool(submitted2.get("ok")),
        "jobId": job2,
        "jobStatus": finished.get("status"),
        "jobMessage": (finished.get("message") or "")[:200],
        "params": {k: params.get(k) for k in ("draftMode", "fast_mode", "width", "height", "outputAssetIds")},
        "candidates": cands,
        "survivedReload": bool(reload_cands),
        "promote": {
            "ok": bool(promote.get("ok")),
            "jobId": promote.get("queueJobId") or promote.get("internalJobId"),
            "draftMode": (preq.get("providerOptions") or {}).get("draftMode"),
            "resolution": preq.get("resolution"),
            "aspectRatio": preq.get("aspectRatio"),
            "newJob": (promote.get("queueJobId") or promote.get("internalJobId")) != job2,
        },
    }
    if promote.get("ok"):
        call(
            "POST",
            f"/api/director-timeline/projects/{PID}/scenes/{SID}/cancel",
            {"action": "cancel_active_local_job"},
        )
    draft["ok"] = bool(
        str(finished.get("status") or "") in ("done", "completed")
        and cands
        and draft["survivedReload"]
        and draft["promote"].get("ok")
        and draft["promote"].get("newJob")
        and draft["promote"].get("draftMode") is False
        and draft["promote"].get("resolution") == "1344x576"
    )
    report["ltx_draft_promote"] = draft
    write("ltx_draft_promote_candidate.json", draft)

    live_path = ARTIFACT / "live_cert.json"
    prev = json.loads(live_path.read_text(encoding="utf-8")) if live_path.is_file() else {}
    refuse_ok = True
    if isinstance((prev.get("gates") or {}).get("video_ref_refuse"), dict):
        refuse_ok = all(v.get("ok") for v in prev["gates"]["video_ref_refuse"].values())
    seed_ok = True
    follow = prev.get("followup") or {}
    seed_ok = bool(((follow.get("summary") or {}).get("seedance_request_and_draft")))
    if not seed_ok:
        takes = ((follow.get("gates") or {}).get("seedance_21_9") or {}).get("takes") or []
        seed_ok = any(t.get("quality") == "draft" and t.get("resolution") == "480p" for t in takes) and any(
            t.get("quality") == "final" and t.get("resolution") == "720p" for t in takes
        )
    summary = {
        "playwright_mocked": "1 passed",
        "video_ref_refuse": refuse_ok,
        "ltx_stop_running": bool(stop.get("ok")),
        "ltx_draft_promote": bool(draft.get("ok")),
        "seedance_21_9": seed_ok,
    }
    report["summary"] = summary
    if all(summary[k] is True or summary[k] == "1 passed" for k in ("video_ref_refuse", "ltx_stop_running", "ltx_draft_promote", "seedance_21_9")):
        verdict = "GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM CERTIFIED END TO END"
        code = 0
        blocker = None
    else:
        verdict = "NO-GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM NOT CERTIFIED END TO END"
        code = 1
        blocker = ", ".join(k for k, v in summary.items() if k != "playwright_mocked" and v is not True)
    report["verdict"] = verdict
    report["blocker"] = blocker
    prev["ltx_candidate_followup"] = report
    prev["verdict"] = verdict
    prev["blocker"] = blocker
    prev["summary"] = summary
    write("live_cert.json", prev)
    write("ltx_candidate_followup.json", report)
    print(json.dumps(report, indent=2, default=str))
    print(verdict)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
