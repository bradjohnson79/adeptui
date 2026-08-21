"""Revision C Phase 2 live A–F on Schnick Coffee. Never POST /api/projects."""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import urllib.error
import urllib.request

API = "http://127.0.0.1:8758"
PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278"
OUT = Path(__file__).resolve().parent / "evidence" / "phase2-live-gates.json"


def _req(method: str, path: str, body: dict | None = None, timeout: int = 90) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(
            f"{API}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return exc.code, parsed
        except (TimeoutError, urllib.error.URLError) as exc:
            last_err = exc
            import time
            time.sleep(2 + attempt * 2)
    raise last_err or TimeoutError(f"{method} {path} failed")


def _neutral_pose() -> dict:
    names = (
        "pelvis", "spine", "chest", "neck", "head",
        "leftShoulder", "leftElbow", "leftWrist",
        "rightShoulder", "rightElbow", "rightWrist",
        "leftHip", "leftKnee", "leftAnkle",
        "rightHip", "rightKnee", "rightAnkle",
    )
    return {name: {"x": 0.0, "y": 0.0, "z": 0.0} for name in names}


def _figure(pose: dict | None = None, **overrides) -> dict:
    data = {
        "id": "fig-phase2-korri",
        "name": "Korri",
        "archetypeId": "adult-female",
        "colorId": "seaglass",
        "position": {"x": 0.0, "z": 0.0},
        "rotationY": 18.0,
        "scale": 1.0,
        "pose": pose or _neutral_pose(),
        "characterId": "char-korri",
    }
    data.update(overrides)
    return data


def _counter() -> dict:
    return {
        "id": "prim-phase2-counter",
        "name": "service counter",
        "kind": "table-medium",
        "position": {"x": 0.38, "z": 0.16},
        "size": {"x": 1.2, "y": 0.95, "z": 0.5},
    }


SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2"
FORBIDDEN_GENERATORS = {"wan-local", "hunyuan-video-1.5-local", "hunyuan-video-13b-local", "cert-stub-local"}
PREFERRED_GENERATORS = ("ltx-local", "ltx-2.5-distilled", "ltx-2.5-comfy", "ltx-2.5-full", "minimax-h3-local")


def _pick_healthy_generator() -> dict:
    code, body = _req("GET", "/api/director-timeline/generators")
    adapters = (body or {}).get("timelineAdapters") or (body or {}).get("generators") or []
    by_id = {str(item.get("id") or item.get("generatorId") or ""): item for item in adapters if isinstance(item, dict)}
    chosen = None
    for gid in PREFERRED_GENERATORS:
        item = by_id.get(gid)
        if not item:
            continue
        if item.get("supportsTimelineGeneration") is False:
            continue
        if gid in FORBIDDEN_GENERATORS:
            continue
        chosen = {"id": gid, "label": item.get("label") or gid, "capability": item.get("capabilityLabel") or item.get("status")}
        break
    return {"code": code, "chosen": chosen, "available": sorted(by_id)}


def _library_videos() -> list[dict]:
    code, body = _req("GET", f"/api/projects/{PROJECT_ID}/library?limit=500")
    rows = []
    if isinstance(body, dict):
        rows = body.get("items") or body.get("assets") or []
    if not isinstance(rows, list):
        _pc, proj = _req("GET", f"/api/projects/{PROJECT_ID}")
        rows = (proj or {}).get("assets") or [] if isinstance(proj, dict) else []
    videos = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or row.get("type") or "").lower()
        mime = str(row.get("mime") or row.get("contentType") or "").lower()
        name = str(row.get("filename") or row.get("path") or "").lower()
        if "video" in kind or mime.startswith("video/") or name.endswith((".mp4", ".webm", ".mov")):
            videos.append(row)
    return videos


def _run_gate_f(*, packet_id: str, compiled: dict) -> dict:
    """Real posed Timeline clip + Revision A / JEPA / PoseContinuityReview."""
    evidence: dict = {"pass": False}
    pick = _pick_healthy_generator()
    evidence["generatorProbe"] = pick
    chosen = pick.get("chosen")
    if not chosen:
        evidence["reason"] = "No healthy Timeline generator (WAN/Hunyuan/stub forbidden; no silent fallback)."
        return evidence
    generator_id = str(chosen["id"])
    evidence["provider"] = chosen.get("label")
    evidence["model"] = generator_id

    sc_code, scenes = _req("GET", f"/api/projects/{PROJECT_ID}/scenes")
    scene_id = SCENE_ID
    if isinstance(scenes, list) and scenes:
        scene_id = str(scenes[0].get("id") or scene_id)
    evidence["sceneId"] = scene_id
    evidence["scenesCode"] = sc_code

    before_videos = {str(row.get("id")) for row in _library_videos() if row.get("id")}

    add_code, add_body = _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/batches",
        {"label": "Phase2 Gate F posed clip", "plannedDuration": 5, "generatorId": generator_id},
    )
    batch = (add_body or {}).get("batch") if isinstance(add_body, dict) else {}
    batch_id = str((batch or {}).get("id") or "")
    evidence["batchCreate"] = {"code": add_code, "batchId": batch_id}
    if add_code != 200 or not batch_id:
        evidence["reason"] = f"Could not add Timeline batch: {add_body}"
        return evidence

    _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/batches",
        {"label": "Phase2 Gate F successor", "plannedDuration": 5, "generatorId": generator_id},
    )

    _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/codirector-continuity-policy",
        {"enabled": True, "reviewCadence": "every_batch"},
    )
    _req(
        "PATCH",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/batches/{batch_id}",
        {
            "promptSegments": [
                {
                    "start": 0.0,
                    "length": 5.0,
                    "text": "Korri at the coffee service counter, short posed hold, then a small natural shift.",
                }
            ],
            "references": [{"poseWorldStatePacketId": packet_id}] if packet_id else [],
        },
    )

    gen_code, gen_body = _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/batches/{batch_id}/generate",
        {"draftMode": True},
        timeout=120,
    )
    request = (gen_body or {}).get("normalizedRequest") if isinstance(gen_body, dict) else {}
    pose_opt = ((request or {}).get("providerOptions") or {}).get("poseMotionConditioning") or {}
    evidence["generateCode"] = gen_code
    evidence["timelineRequestId"] = (gen_body or {}).get("queueJobId") or (gen_body or {}).get("internalJobId")
    evidence["jobId"] = (gen_body or {}).get("queueJobId") or ((gen_body or {}).get("job") or {}).get("id")
    evidence["executionSnapshotId"] = (gen_body or {}).get("executionSnapshotId")
    evidence["poseMotionConditioning"] = pose_opt
    evidence["prompt"] = (request or {}).get("prompt")
    evidence["requestGeneratorId"] = (request or {}).get("generatorId") or (gen_body or {}).get("generatorId")
    if gen_code != 200 or not (gen_body or {}).get("ok"):
        evidence["reason"] = f"Generate failed: {gen_body}"
        return evidence
    if evidence["requestGeneratorId"] and evidence["requestGeneratorId"] != generator_id:
        evidence["reason"] = f"Silent generator substitution {generator_id} → {evidence['requestGeneratorId']}"
        return evidence
    if pose_opt.get("applied") is not True:
        evidence["reason"] = f"poseMotionConditioning.applied is not true: {pose_opt}"
        return evidence
    if "pose continuity" not in str((request or {}).get("prompt") or compiled.get("promptPrefix") or "").lower():
        evidence["reason"] = "Generate prompt missing compiled pose continuity prefix."
        return evidence

    video_asset_id = ""
    candidate_id = ""
    deadline = time.time() + 1200
    last_status = ""
    while time.time() < deadline:
        _mc, master_body = _req("GET", f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/master", timeout=60)
        master = (master_body or {}).get("master") if isinstance(master_body, dict) else master_body
        batches = (master or {}).get("batchBlocks") or []
        target = next((b for b in batches if str(b.get("id")) == batch_id), {})
        last_status = str(target.get("status") or "")
        approved = (target.get("approvedClip") or {}) if isinstance(target, dict) else {}
        if approved.get("assetId"):
            video_asset_id = str(approved["assetId"])
            candidate_id = str(approved.get("candidateId") or "")
            break
        cands = target.get("candidateVersions") or []
        ready = next((c for c in cands if c.get("assetId") and str(c.get("status") or last_status) != "failed"), None)
        if last_status in {"CandidateReady", "Ready"} and ready:
            video_asset_id = str(ready.get("assetId") or "")
            candidate_id = str(ready.get("id") or "")
            break
        if last_status in {"Failed", "Cancelled", "Error"}:
            evidence["reason"] = f"Batch ended {last_status}: {target.get('lastError') or target}"
            evidence["batchStatus"] = last_status
            return evidence
        if evidence["jobId"]:
            _jc, job = _req("GET", f"/api/jobs/{evidence['jobId']}", timeout=30)
            evidence["jobPoll"] = {"status": (job or {}).get("status") if isinstance(job, dict) else job}
            if isinstance(job, dict) and str(job.get("status") or "").lower() in {"failed", "error", "cancelled"}:
                evidence["reason"] = f"Job failed: {job.get('error') or job.get('status')}"
                return evidence
        time.sleep(5)

    evidence["batchStatus"] = last_status
    evidence["candidateId"] = candidate_id
    if not video_asset_id:
        evidence["reason"] = f"Timed out waiting for posed video. lastStatus={last_status}"
        return evidence

    if last_status != "Approved" and candidate_id:
        ap_code, ap_body = _req(
            "POST",
            f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/batches/{batch_id}/approve",
            {"candidateId": candidate_id},
            timeout=180,
        )
        evidence["approve"] = {"code": ap_code, "ok": isinstance(ap_body, dict) and ap_body.get("ok") is True}
        if isinstance(ap_body, dict) and (ap_body.get("approvedClip") or {}).get("assetId"):
            video_asset_id = str(ap_body["approvedClip"]["assetId"])

    after_videos = [row for row in _library_videos() if str(row.get("id")) == video_asset_id]
    new_videos = [row for row in _library_videos() if str(row.get("id")) not in before_videos]
    video_row = after_videos[0] if after_videos else (new_videos[0] if new_videos else {"id": video_asset_id})
    evidence["generatedVideoAssetId"] = video_asset_id
    evidence["generatedVideoPath"] = video_row.get("path") or video_row.get("filename")
    evidence["newVideo"] = str(video_asset_id) not in before_videos or bool(new_videos)

    tc_code, tc_body = _req(
        "GET",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{scene_id}/temporal-continuity",
        timeout=60,
    )
    packets = (tc_body or {}).get("temporalPackets") or [] if isinstance(tc_body, dict) else []
    latest = packets[-1] if packets else {}
    extras = latest.get("extras") or {}
    pose_review = extras.get("poseContinuityReview") or latest.get("poseContinuityReview")
    world_review = extras.get("worldReview") or latest.get("worldReview")
    observed = (latest.get("assessment") or {}).get("observedState") or latest.get("observedState")
    evidence["temporalCode"] = tc_code
    evidence["temporalAnalysisId"] = latest.get("packetId") or latest.get("id")
    evidence["worldIntelligence"] = {
        "availability": (world_review or {}).get("availability") if isinstance(world_review, dict) else None,
        "summary": (world_review or {}).get("summary") or (world_review or {}).get("creatorFacingSummary"),
    }
    evidence["poseContinuityReview"] = {
        "id": (pose_review or {}).get("reviewId") or (pose_review or {}).get("packetId") or (pose_review or {}).get("id"),
        "authorityNote": (pose_review or {}).get("authorityNote"),
        "continuityRisk": (pose_review or {}).get("continuityRisk"),
        "changes": (pose_review or {}).get("changes") or (pose_review or {}).get("structuredDifferences"),
        "nextBatchGuidance": (pose_review or {}).get("nextBatchGuidance"),
    } if isinstance(pose_review, dict) else pose_review
    evidence["observedState"] = observed
    evidence["observedProvenance"] = "temporal-continuity packet from generated media" if observed or pose_review else "missing"

    evidence["pass"] = bool(
        evidence.get("newVideo")
        and video_asset_id
        and pose_opt.get("applied") is True
        and (pose_review or observed)
        and "error" not in str(pose_review or {})
    )
    if not evidence["pass"] and not evidence.get("reason"):
        evidence["reason"] = "Generate succeeded but intended-vs-observed review was not produced from the new clip."
    evidence["note"] = (
        "Observed media is authoritative for what happened. PoseCraft remains intended starting performance. "
        "No hardcoded observed packet."
    )
    return evidence


def _snapshot(doc: dict, *, name: str, figures: list, primitives: list) -> dict:
    scene = doc["currentScene"]
    return {
        "snapshotId": str(uuid.uuid4()),
        "projectId": PROJECT_ID,
        "sceneId": scene.get("name") or "Pose study",
        "sceneRevision": int(scene.get("revision") or 1),
        "name": name,
        "imageAssetId": "",
        "camera": scene.get("camera") or {},
        "figures": figures,
        "primitives": primitives,
        "customFigures": [],
        "semanticSummary": name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    report: dict = {
        "projectId": PROJECT_ID,
        "projectName": "Schnick Coffee",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "gates": {},
    }
    health_code, health = _req("GET", "/api/health")
    wi_code, wi = _req("GET", "/api/codirector/world-intelligence/status")
    report["health"] = {"code": health_code, "body": health}
    report["worldIntelligence"] = {"code": wi_code, "body": wi}

    orig_code, original = _req("GET", f"/api/posecraft/projects/{PROJECT_ID}/scene")
    if orig_code != 200 or not isinstance(original, dict):
        report["gates"]["restore"] = {"pass": False, "reason": "Could not load existing PoseCraft scene."}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    standing = _figure(
        pose={
            **_neutral_pose(),
            "rightShoulder": {"x": -18.0, "y": 0.0, "z": 22.0},
            "rightElbow": {"x": -12.0, "y": 0.0, "z": 0.0},
        }
    )
    seated = _figure(
        pose={
            **_neutral_pose(),
            "leftHip": {"x": 78.0, "y": 0.0, "z": 0.0},
            "rightHip": {"x": 78.0, "y": 0.0, "z": 0.0},
            "leftKnee": {"x": 82.0, "y": 0.0, "z": 0.0},
            "rightKnee": {"x": 82.0, "y": 0.0, "z": 0.0},
        },
        position={"x": 0.15, "z": 0.0},
    )
    counter = _counter()
    work = deepcopy(original)
    scene = work.setdefault("currentScene", {})
    scene["figures"] = [standing]
    scene["primitives"] = list(scene.get("primitives") or []) + [counter]
    scene["selectedFigureId"] = standing["id"]
    scene["revision"] = int(scene.get("revision") or 1) + 1
    scene["creatorModified"] = True
    snap_a = _snapshot(work, name="Phase2 standing", figures=[standing], primitives=[counter])
    snap_b = _snapshot(work, name="Phase2 seated", figures=[seated], primitives=[counter])
    work["snapshots"] = list(work.get("snapshots") or []) + [snap_a, snap_b]
    work["selectedSnapshotId"] = snap_a["snapshotId"]

    try:
        put_code, put_body = _req("PUT", f"/api/posecraft/projects/{PROJECT_ID}/scene", work)
        report["scenePut"] = {"code": put_code, "ok": put_code == 200}
        if put_code != 200:
            report["gates"]["A"] = {"pass": False, "reason": put_body}
            return _finish(report, 1)

        a_code, a_body = _req("POST", f"/api/posecraft/projects/{PROJECT_ID}/intelligence/analyze", {})
        packet = (a_body or {}).get("packet") if isinstance(a_body, dict) else {}
        report["gates"]["A"] = {
            "pass": a_code == 200
            and packet.get("projectId") == PROJECT_ID
            and packet.get("character", {}).get("figureName") == "Korri"
            and packet.get("availability") in {"available", "degraded", "low_confidence"}
            and packet.get("constraints", {}).get("creatorIntentHonored") is True,
            "code": a_code,
            "availability": packet.get("availability"),
            "stance": packet.get("character", {}).get("stance"),
            "support": packet.get("character", {}).get("primarySupport"),
            "summary": packet.get("creatorFacingSummary"),
            "worldAvailability": (packet.get("world") or {}).get("availability"),
        }

        proj_code, proj = _req("GET", f"/api/projects/{PROJECT_ID}")
        images = []
        if isinstance(proj, dict):
            for row in proj.get("assets") or []:
                kind = str((row or {}).get("kind") or "").lower()
                name = str((row or {}).get("filename") or (row or {}).get("path") or "").lower()
                if kind == "image" or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    images.append(row)
        jepa_eval = None
        pose_world = None
        if images:
            ev_code, ev_body = _req(
                "POST",
                "/api/codirector/world-intelligence/evaluate",
                {
                    "projectId": PROJECT_ID,
                    "assetId": images[0]["id"],
                    "referenceAssetIds": [images[1]["id"]] if len(images) > 1 else [],
                },
                timeout=180,
            )
            ev_packet = (ev_body or {}).get("packet") if isinstance(ev_body, dict) else {}
            jepa_eval = {"code": ev_code, "availability": (ev_packet or {}).get("availability")}
            work["snapshots"] = [
                {**snap_a, "imageAssetId": images[0]["id"]},
                snap_b,
            ]
            _req("PUT", f"/api/posecraft/projects/{PROJECT_ID}/scene", work)
            j_code, j_body = _req(
                "POST",
                f"/api/posecraft/projects/{PROJECT_ID}/intelligence/analyze",
                {"snapshotId": snap_a["snapshotId"]},
                timeout=180,
            )
            j_packet = (j_body or {}).get("packet") if isinstance(j_body, dict) else {}
            pose_world = {
                "code": j_code,
                "availability": (j_packet.get("world") or {}).get("availability"),
                "reason": (j_packet.get("world") or {}).get("reason"),
                "imageAssetId": images[0]["id"],
            }
        report["gates"]["JEPA"] = {
            "pass": bool(jepa_eval and jepa_eval.get("availability") in {"available", "degraded", "low_confidence"})
            or bool(pose_world and pose_world.get("availability") in {"available", "degraded", "low_confidence"}),
            "projectCode": proj_code,
            "imageCount": len(images),
            "evaluate": jepa_eval,
            "poseWorld": pose_world,
        }

        c_code, c_body = _req(
            "POST",
            f"/api/posecraft/projects/{PROJECT_ID}/intelligence/analyze",
            {"snapshotId": snap_a["snapshotId"]},
        )
        c_packet = (c_body or {}).get("packet") if isinstance(c_body, dict) else {}
        contacts = (c_packet.get("interaction") or {}).get("graph", {}).get("edges") or []
        contact_blob = json.dumps(c_packet.get("interaction") or {}).lower()
        report["gates"]["C"] = {
            "pass": c_code == 200 and ("counter" in contact_blob or bool(contacts) or (c_packet.get("interaction") or {}).get("groundContact") is True),
            "code": c_code,
            "edges": contacts[:8],
            "handContact": (c_packet.get("interaction") or {}).get("handContact"),
            "groundContact": (c_packet.get("interaction") or {}).get("groundContact"),
        }

        b_code, b_body = _req(
            "POST",
            f"/api/posecraft/projects/{PROJECT_ID}/intelligence/compare",
            {"fromSnapshotId": snap_a["snapshotId"], "toSnapshotId": snap_b["snapshotId"]},
        )
        transition = (b_body or {}).get("transition") if isinstance(b_body, dict) else {}
        report["gates"]["B"] = {
            "pass": b_code == 200 and bool((transition or {}).get("changes") or (transition or {}).get("plausibilityWarnings")),
            "code": b_code,
            "changes": (transition or {}).get("changes"),
            "warnings": (transition or {}).get("plausibilityWarnings"),
            "actionProgression": (transition or {}).get("actionProgression"),
        }

        d_code, d_body = _req("POST", f"/api/posecraft/projects/{PROJECT_ID}/intelligence/handoff/scene-creator", {})
        ws_code, ws_body = _req("GET", f"/api/scene-creator/projects/{PROJECT_ID}/workspace")
        ctx = (ws_body or {}).get("production_context") or (ws_body or {}).get("productionContext") or {}
        if not ctx and isinstance(ws_body, dict):
            ctx = ((ws_body.get("workspace") or {}).get("production_context") or ws_body)
        pose_id = (d_body or {}).get("poseWorldStatePacketId") if isinstance(d_body, dict) else ""
        report["gates"]["D"] = {
            "pass": d_code == 200
            and bool(pose_id)
            and ws_code == 200
            and (
                ctx.get("poseWorldStatePacketId") == pose_id
                or (ctx.get("poseIntelligence") or {}).get("packetId") == pose_id
                or "poseWorldStatePacketId" in json.dumps(ws_body)
            ),
            "code": d_code,
            "workspaceCode": ws_code,
            "poseWorldStatePacketId": pose_id,
            "workspaceHasPose": "poseWorldStatePacketId" in json.dumps(ws_body) or "poseIntelligence" in json.dumps(ws_body),
        }

        e_code, e_body = _req("POST", f"/api/posecraft/projects/{PROJECT_ID}/intelligence/handoff/timeline", {})
        compiled = (e_body or {}).get("compiled") if isinstance(e_body, dict) else {}
        report["gates"]["E"] = {
            "pass": e_code == 200 and compiled.get("applied") is True and "pose continuity" in str(compiled.get("promptPrefix") or "").lower(),
            "code": e_code,
            "applied": compiled.get("applied"),
            "promptPrefix": compiled.get("promptPrefix"),
            "packetId": (e_body or {}).get("poseWorldStatePacketId") if isinstance(e_body, dict) else None,
        }

        report["gates"]["F"] = _run_gate_f(
            packet_id=str((e_body or {}).get("poseWorldStatePacketId") or packet.get("packetId") or ""),
            compiled=compiled if isinstance(compiled, dict) else {},
        )
    finally:
        restore_code, _restore = _req("PUT", f"/api/posecraft/projects/{PROJECT_ID}/scene", original)
        report["gates"]["restore"] = {"pass": restore_code == 200, "code": restore_code}

    return _finish(report, 0 if all(g.get("pass") for g in report["gates"].values()) else 1)


def _finish(report: dict, code: int) -> int:
    report["finishedAt"] = datetime.now(timezone.utc).isoformat()
    report["verdict"] = "PASS" if code == 0 else "FAIL"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verdict", "gates", "projectId") if k in report}, indent=2))
    print(f"wrote {OUT}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
