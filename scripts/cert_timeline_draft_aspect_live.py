"""Live Timeline Draft-First + Aspect + Video Reference certification.

Talks to the live Studio API used by Beta UI. One LTX Stop, one LTX draft+Promote,
one Seedance 21:9 480p→720p, plus video-ref refuse. No credit-burn loops.

Usage:
  python scripts/cert_timeline_draft_aspect_live.py
  python scripts/cert_timeline_draft_aspect_live.py --api http://127.0.0.1:8761
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "docs" / "release-gate" / "timeline" / "artifacts-draft-aspect"
PROJECT_NAME = "Timeline Draft Aspect Cert"


def _req(method: str, url: str, body: dict | None = None, timeout: float = 60.0) -> tuple[int, dict | list | str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def _write(name: str, payload: object) -> None:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _halt_evidence(job: dict) -> dict:
    history_raw = job.get("history_json") or ""
    history: dict = {}
    if isinstance(history_raw, str) and history_raw.strip():
        try:
            history = json.loads(history_raw)
        except json.JSONDecodeError:
            history = {"raw": history_raw[:500]}
    halt = {}
    if isinstance(history, dict):
        halt = history.get("halt") or {}
        recovery = history.get("recovery") or history.get("videoRuntime") or {}
        if not halt and isinstance(recovery, dict):
            halt = recovery.get("halt") or {}
        vr = history.get("video_runtime") or history.get("videoRuntime") or {}
        if not halt and isinstance(vr, dict):
            halt = vr.get("halt") or {}
    return {
        "status": job.get("status"),
        "stage": job.get("stage"),
        "message": job.get("message"),
        "comfy_prompt_id": job.get("comfy_prompt_id"),
        "confirmedStopped": bool(halt.get("confirmedStopped"))
        or "confirmed prompt" in str(job.get("message") or "").lower()
        or "no longer active" in str(job.get("message") or "").lower(),
        "halt": halt,
        "historyKeys": list(history.keys()) if isinstance(history, dict) else [],
    }


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 60.0):
        return _req(method, f"{self.base}{path}", body, timeout=timeout)

    def json(self, method: str, path: str, body: dict | None = None, timeout: float = 60.0) -> dict:
        status, payload = self.call(method, path, body, timeout=timeout)
        if not isinstance(payload, dict):
            raise RuntimeError(f"{method} {path} -> {status} {payload!r}")
        payload.setdefault("_http", status)
        return payload


def ensure_project(api: Api) -> dict:
    status, payload = api.call("GET", "/api/projects")
    projects = payload if isinstance(payload, list) else (payload or {}).get("projects") or []
    for p in projects:
        if isinstance(p, dict) and p.get("name") == PROJECT_NAME:
            return p
    created = api.json("POST", "/api/projects", {"name": PROJECT_NAME})
    if not created.get("id"):
        raise RuntimeError(f"create project failed: {created}")
    return created


def ensure_scene(api: Api, project_id: str) -> dict:
    status, payload = api.call("GET", f"/api/projects/{project_id}/scenes")
    scenes = payload if isinstance(payload, list) else (payload or {}).get("scenes") or []
    if isinstance(scenes, list) and scenes:
        return scenes[0]
    created = api.json(
        "POST",
        f"/api/projects/{project_id}/scenes",
        {"title": "Draft Aspect Scene", "prompt": "wide draft preview walk", "duration_sec": 5},
    )
    sid = created.get("id") or (created.get("scene") or {}).get("id")
    if not sid:
        raise RuntimeError(f"create scene failed: {created}")
    created["id"] = sid
    return created


def wait_job(api: Api, job_id: str, timeout_sec: float, want: set[str]) -> dict:
    deadline = time.time() + timeout_sec
    last = {}
    while time.time() < deadline:
        last = api.json("GET", f"/api/jobs/{job_id}")
        st = str(last.get("status") or "")
        if st in want:
            return last
        time.sleep(1.5)
    return last


def wait_master_take(api: Api, project_id: str, scene_id: str, batch_id: str, timeout_sec: float) -> dict:
    deadline = time.time() + timeout_sec
    last = {}
    while time.time() < deadline:
        last = api.json("GET", f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/master")
        master = last.get("master") or {}
        batch = next((b for b in (master.get("batchBlocks") or []) if b.get("id") == batch_id), {})
        versions = batch.get("candidateVersions") or []
        if versions:
            last["_batch"] = batch
            return last
        if str(batch.get("status") or "") in ("Failed", "Cancelled"):
            last["_batch"] = batch
            return last
        time.sleep(3)
    last["_batch"] = {}
    return last


def configure_batch(api: Api, project_id: str, scene_id: str, batch_id: str, generator_id: str) -> dict:
    return api.json(
        "PATCH",
        f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}",
        {
            "generatorId": generator_id,
            "promptSegments": [
                {
                    "text": "a person walks across an ultrawide desert road, cinematic",
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


def generate(api: Api, project_id: str, scene_id: str, batch_id: str, draft: bool) -> dict:
    return api.json(
        "POST",
        f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/generate",
        {"draftMode": draft},
        timeout=90.0,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8758")
    parser.add_argument("--skip-seedance", action="store_true")
    parser.add_argument("--skip-ltx-complete", action="store_true")
    args = parser.parse_args()
    api = Api(args.api)
    report: dict = {"api": args.api, "gates": {}, "verdict": None}

    health = api.json("GET", "/api/health")
    comfy = api.json("GET", "/api/comfy/health")
    report["health"] = {"ok": health.get("ok"), "comfy": {k: comfy.get(k) for k in ("reachable", "status", "baseUrl")}}
    devices = comfy.get("devices") or []
    report["gpu"] = devices[0] if devices else None
    if not comfy.get("reachable"):
        report["verdict"] = "NO-GO"
        report["blocker"] = "ComfyUI not reachable"
        _write("live_cert.json", report)
        print(json.dumps(report, indent=2, default=str))
        return 2

    project = ensure_project(api)
    scene = ensure_scene(api, project["id"])
    api.json("PATCH", f"/api/projects/{project['id']}/scenes/{scene['id']}", {"aspect_ratio": "21:9"})
    master = api.json("GET", f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/master")
    batch_id = ((master.get("master") or {}).get("batchBlocks") or [{}])[0].get("id")
    if not batch_id:
        report["verdict"] = "NO-GO"
        report["blocker"] = "No Timeline batch on scene"
        _write("live_cert.json", report)
        print(json.dumps(report, indent=2, default=str))
        return 2
    report["project"] = {"id": project["id"], "name": project.get("name"), "sceneId": scene["id"], "batchId": batch_id}
    api.json(
        "POST",
        f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/cancel",
        {"action": "stop_remaining_scene_jobs"},
    )

    # --- Gate: video-ref refuse (LTX + Kling) ---
    refuse_results = {}
    for gen_id in ("ltx-local", "kling-api"):
        configure_batch(api, project["id"], scene["id"], batch_id, gen_id)
        api.json(
            "PATCH",
            f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/batches/{batch_id}",
            {"sourceAnchors": [{"kind": "video", "assetId": "video-ref-cert-dummy", "label": "motion"}]},
        )
        refused = generate(api, project["id"], scene["id"], batch_id, True)
        errors = refused.get("errors") or []
        ok_refuse = refused.get("error") == "CAPABILITY_VALIDATION_FAILED" and any(
            "video reference" in str(e).lower() for e in errors
        )
        refuse_results[gen_id] = {
            "ok": ok_refuse,
            "error": refused.get("error"),
            "errors": errors,
            "http": refused.get("_http"),
            "detail": refused.get("detail"),
            "message": refused.get("message"),
        }
        api.json(
            "PATCH",
            f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/batches/{batch_id}",
            {"sourceAnchors": []},
        )
    report["gates"]["video_ref_refuse"] = refuse_results

    # --- Gate: LTX Stop ---
    configure_batch(api, project["id"], scene["id"], batch_id, "ltx-local")
    submitted = generate(api, project["id"], scene["id"], batch_id, True)
    _write("ltx_draft_submit.json", submitted)
    job_id = submitted.get("queueJobId") or submitted.get("internalJobId")
    req = submitted.get("normalizedRequest") or {}
    stop_gate = {
        "submitOk": bool(submitted.get("ok")),
        "jobId": job_id,
        "aspectRatio": req.get("aspectRatio"),
        "resolution": req.get("resolution"),
        "draftMode": (req.get("providerOptions") or {}).get("draftMode"),
        "error": submitted.get("error") or submitted.get("message"),
    }
    if not job_id or not submitted.get("ok"):
        stop_gate["ok"] = False
        report["gates"]["ltx_stop"] = stop_gate
    else:
        running = wait_job(api, job_id, 90, {"running", "cancelling", "cancelled", "completed", "failed"})
        stop_gate["preCancel"] = {
            "status": running.get("status"),
            "stage": running.get("stage"),
            "comfy_prompt_id": running.get("comfy_prompt_id"),
        }
        cancel = api.json(
            "POST",
            f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/cancel",
            {"action": "cancel_active_local_job"},
        )
        stop_gate["cancel"] = {k: cancel.get(k) for k in ("ok", "action", "message", "hostedCancelSupport", "affectedBatchIds")}
        halted = wait_job(api, job_id, 45, {"cancelled", "cancel_failed_runtime_active", "failed"})
        evidence = _halt_evidence(halted)
        stop_gate["jobAfter"] = evidence
        stop_gate["ok"] = bool(
            cancel.get("ok")
            and evidence.get("status") in ("cancelled", "cancelling")
            and (evidence.get("confirmedStopped") or evidence.get("status") == "cancelled")
        )
        # Strict: confirmedStopped or message proving Comfy halt, not DB-only fallback.
        msg = str(evidence.get("message") or "").lower()
        fallback = "halt fallback" in msg or "timeline batch (halt fallback)" in msg
        stop_gate["dbOnlyFallback"] = fallback
        if fallback:
            stop_gate["ok"] = False
            stop_gate["blocker"] = "Stop marked the Job cancelled without cancel_and_halt / Comfy confirmedStopped"
        elif evidence.get("confirmedStopped"):
            stop_gate["ok"] = True
        elif evidence.get("status") == "cancelled" and evidence.get("comfy_prompt_id"):
            # Halt ran; prompt id was present. Treat as pass if not fallback.
            stop_gate["ok"] = True
        report["gates"]["ltx_stop"] = stop_gate
        _write("ltx_stop.json", stop_gate)

    # --- Gate: LTX completed draft + Promote starts a new final job ---
    draft_gate: dict = {"skipped": bool(args.skip_ltx_complete)}
    if not args.skip_ltx_complete:
        configure_batch(api, project["id"], scene["id"], batch_id, "ltx-local")
        submitted2 = generate(api, project["id"], scene["id"], batch_id, True)
        job2 = submitted2.get("queueJobId") or submitted2.get("internalJobId")
        draft_gate["submitOk"] = bool(submitted2.get("ok"))
        draft_gate["jobId"] = job2
        draft_gate["normalized"] = {
            "aspectRatio": (submitted2.get("normalizedRequest") or {}).get("aspectRatio"),
            "resolution": (submitted2.get("normalizedRequest") or {}).get("resolution"),
            "draftMode": ((submitted2.get("normalizedRequest") or {}).get("providerOptions") or {}).get("draftMode"),
        }
        if submitted2.get("ok") and job2:
            finished = wait_job(api, job2, 420, {"completed", "failed", "cancelled"})
            draft_gate["jobStatus"] = finished.get("status")
            draft_gate["jobMessage"] = finished.get("message")
            params = {}
            try:
                params = json.loads(finished.get("params_json") or "{}")
            except json.JSONDecodeError:
                params = {}
            draft_gate["params"] = {k: params.get(k) for k in ("draftMode", "fast_mode", "width", "height", "aspectRatio")}
            master2 = wait_master_take(api, project["id"], scene["id"], batch_id, 90)
            batch = master2.get("_batch") or {}
            versions = batch.get("candidateVersions") or []
            latest = versions[-1] if versions else {}
            take = (latest.get("takeState") or {}) if isinstance(latest, dict) else {}
            draft_gate["candidate"] = {
                "count": len(versions),
                "quality": take.get("quality") or latest.get("quality"),
                "id": latest.get("id"),
                "batchStatus": batch.get("status"),
            }
            reload_master = api.json(
                "GET", f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/master"
            )
            reload_batch = next(
                (b for b in ((reload_master.get("master") or {}).get("batchBlocks") or []) if b.get("id") == batch_id),
                {},
            )
            reload_versions = reload_batch.get("candidateVersions") or []
            draft_gate["survivedReload"] = bool(reload_versions)
            promote = generate(api, project["id"], scene["id"], batch_id, False)
            promo_req = promote.get("normalizedRequest") or {}
            draft_gate["promote"] = {
                "ok": bool(promote.get("ok")),
                "jobId": promote.get("queueJobId") or promote.get("internalJobId"),
                "draftMode": (promo_req.get("providerOptions") or {}).get("draftMode"),
                "resolution": promo_req.get("resolution"),
                "aspectRatio": promo_req.get("aspectRatio"),
                "newJob": (promote.get("queueJobId") or promote.get("internalJobId")) != job2,
            }
            # Stop the final to avoid extra GPU once we proved a new final job started.
            if promote.get("ok"):
                api.json(
                    "POST",
                    f"/api/director-timeline/projects/{project['id']}/scenes/{scene['id']}/cancel",
                    {"action": "cancel_active_local_job"},
                )
            draft_ok = bool(
                finished.get("status") == "completed"
                and str(draft_gate["candidate"].get("quality") or "").lower() == "draft"
                and draft_gate["survivedReload"]
                and draft_gate["promote"].get("ok")
                and draft_gate["promote"].get("newJob")
                and draft_gate["promote"].get("draftMode") is False
            )
            draft_gate["ok"] = draft_ok
        else:
            draft_gate["ok"] = False
            draft_gate["error"] = submitted2.get("error") or submitted2.get("message")
    report["gates"]["ltx_draft_promote"] = draft_gate
    _write("ltx_draft_promote.json", draft_gate)

    # --- Gate: Seedance 21:9 480p draft → 720p promote ---
    seed_gate: dict = {"skipped": bool(args.skip_seedance)}
    if not args.skip_seedance:
        configure_batch(api, project["id"], scene["id"], batch_id, "seedance-api")
        seed_submit = generate(api, project["id"], scene["id"], batch_id, True)
        sreq = seed_submit.get("normalizedRequest") or {}
        seed_gate["submitOk"] = bool(seed_submit.get("ok"))
        seed_gate["normalized"] = {
            "aspectRatio": sreq.get("aspectRatio"),
            "resolution": sreq.get("resolution"),
            "draftMode": (sreq.get("providerOptions") or {}).get("draftMode"),
            "videoReferenceAssetId": sreq.get("videoReferenceAssetId"),
        }
        seed_gate["error"] = seed_submit.get("error") or seed_submit.get("message") or seed_submit.get("errors")
        _write("seedance_draft_submit.json", seed_submit)
        if seed_submit.get("ok"):
            master_s = wait_master_take(api, project["id"], scene["id"], batch_id, 600)
            batch_s = master_s.get("_batch") or {}
            versions_s = batch_s.get("candidateVersions") or []
            latest_s = versions_s[-1] if versions_s else {}
            take_s = latest_s.get("takeState") or {}
            seed_gate["draftResult"] = {
                "batchStatus": batch_s.get("status"),
                "quality": take_s.get("quality"),
                "resolution": take_s.get("resolution"),
                "aspectRatio": take_s.get("aspectRatio"),
                "candidateCount": len(versions_s),
            }
            promo_s = generate(api, project["id"], scene["id"], batch_id, False)
            preq = promo_s.get("normalizedRequest") or {}
            seed_gate["promote"] = {
                "ok": bool(promo_s.get("ok")),
                "draftMode": (preq.get("providerOptions") or {}).get("draftMode"),
                "resolution": preq.get("resolution"),
                "aspectRatio": preq.get("aspectRatio"),
                "error": promo_s.get("error") or promo_s.get("message"),
            }
            seed_gate["ok"] = bool(
                seed_gate["normalized"].get("aspectRatio") == "21:9"
                and seed_gate["normalized"].get("resolution") == "480p"
                and seed_gate["draftResult"].get("quality") == "draft"
                and seed_gate["promote"].get("ok")
                and seed_gate["promote"].get("resolution") == "720p"
                and seed_gate["promote"].get("draftMode") is False
            )
        else:
            err_txt = json.dumps(seed_gate.get("error") or "")
            seed_gate["ok"] = False
            if "credential" in err_txt.lower() or "fal" in err_txt.lower() or "not configured" in err_txt.lower():
                seed_gate["blocker"] = "Seedance live fal credential missing or rejected"
            else:
                seed_gate["blocker"] = f"Seedance draft submit failed: {err_txt[:400]}"
    report["gates"]["seedance_21_9"] = seed_gate
    _write("seedance_21_9.json", seed_gate)

    refuse_ok = all(v.get("ok") for v in refuse_results.values())
    ltx_stop_ok = bool((report["gates"].get("ltx_stop") or {}).get("ok"))
    ltx_draft_ok = bool(draft_gate.get("ok")) if not args.skip_ltx_complete else False
    seed_ok = bool(seed_gate.get("ok")) if not args.skip_seedance else False
    report["summary"] = {
        "video_ref_refuse": refuse_ok,
        "ltx_stop": ltx_stop_ok,
        "ltx_draft_promote": ltx_draft_ok,
        "seedance_21_9": seed_ok,
        "playwright_mocked": "see timeline-draft-aspect-videoref.spec.ts",
    }
    if refuse_ok and ltx_stop_ok and ltx_draft_ok and seed_ok:
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
        if not seed_ok:
            blockers.append(seed_gate.get("blocker") or "Seedance 21:9 Draft→Final")
        report["blocker"] = "; ".join(blockers)
        report["verdict"] = "NO-GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM NOT CERTIFIED END TO END"
        code = 1
    _write("live_cert.json", report)
    print(json.dumps(report, indent=2, default=str))
    print(report["verdict"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
