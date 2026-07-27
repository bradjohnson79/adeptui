"""Phase 10 finishing pass over the situations that already have real artifacts.

The production pass proved the artifacts exist. This pass proves a human can act on them:
approve the generated image version, publish it back as a Production Bible reference, and
put the reused fal motion clip on the Director timeline through the approval gate.

Nothing here generates media. No fal job is submitted.
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("M30_API", "http://127.0.0.1:8760")
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "m30-situations"
DATA_DIR = Path(
    os.environ.get("STUDIO_DATA_DIR")
    or (Path.home() / "AppData" / "Local" / "Temp" / "adept-m30-sit-data")
)


def call(method, path, body=None, timeout=300):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return {"status": resp.status, "payload": json.loads(raw) if raw else None}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:400]}
        return {"status": exc.code, "payload": payload}
    except Exception as exc:
        return {"status": 0, "payload": {"error": str(exc)[:300]}}


def version_id_for(asset_id):
    con = sqlite3.connect("file:%s?mode=ro" % (DATA_DIR / "studio.db").as_posix(), uri=True)
    try:
        row = con.execute(
            "SELECT id, status FROM m29_asset_versions WHERE asset_id = ? ORDER BY created_at DESC",
            (asset_id,),
        ).fetchone()
        return row if row else (None, None)
    finally:
        con.close()


def video_asset_for(project_id):
    con = sqlite3.connect("file:%s?mode=ro" % (DATA_DIR / "studio.db").as_posix(), uri=True)
    try:
        row = con.execute(
            "SELECT id FROM assets WHERE project_id = ? AND kind = 'video'", (project_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def poll_studio_job(job_id, timeout=600, interval=5):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = call("GET", "/api/jobs/" + job_id)["payload"]
        if str((last or {}).get("status") or "").lower() in ("done", "failed", "cancelled"):
            return last
        time.sleep(interval)
    return last


results = []
for path in sorted(glob.glob(str(OUT / "situation-*-production.json"))):
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    n = rec["n"]
    pid = rec["projectId"]
    sid = rec["sceneId"]
    image_asset = rec.get("imageAssetId")
    out = {"n": n, "situation": rec["situation"], "projectId": pid, "sceneId": sid}

    # 1. Human approval of the artifact that actually exists, then publish it as a reference.
    ver_id, ver_status = version_id_for(image_asset) if image_asset else (None, None)
    out["imageVersion"] = {"id": ver_id, "statusBefore": ver_status}
    if ver_id:
        res = call("POST", "/api/codirector/m29/image/%s/approve" % ver_id, {"actor": "m30-operator"})
        out["imageApprove"] = {
            "status": res["status"],
            "versionStatus": (res["payload"] or {}).get("status"),
            "approvedBy": (res["payload"] or {}).get("approvedBy"),
        }
        res = call(
            "POST",
            "/api/codirector/m29/image/%s/publish-reference" % ver_id,
            {"actor": "m30-operator"},
        )
        meta = (res["payload"] or {}).get("metadata") or {}
        out["imagePublishReference"] = {
            "status": res["status"],
            "publishedReference": meta.get("publishedReference"),
            "publishedBy": meta.get("publishedBy"),
        }

    # 2. The reused fal clip onto the Director timeline, through the gate.
    vid_asset = video_asset_for(pid)
    out["videoAssetId"] = vid_asset
    if vid_asset:
        res = call(
            "POST",
            "/api/codirector/m29/timeline/propose",
            {
                "projectId": pid,
                "sceneId": sid,
                "clips": [
                    {
                        "assetId": vid_asset,
                        "start": 0.0,
                        "length": 4.0,
                        "track": "video",
                        "label": "fal seedance motion (reused artifact)",
                    }
                ],
                "notes": "Place reused fal Seedance clip on the video track",
            },
        )
        prop = res["payload"] or {}
        out["videoProposal"] = {"status": res["status"], "id": prop.get("id"),
                                "proposalStatus": prop.get("status")}
        if prop.get("id"):
            res = call("POST", "/api/codirector/m29/timeline/%s/apply" % prop["id"], {})
            out["videoApplyBeforeApproval"] = {
                "status": res["status"],
                "detail": str((res["payload"] or {}).get("detail"))[:120],
            }
            res = call("POST", "/api/codirector/m29/timeline/%s/approve" % prop["id"], {})
            out["videoApprove"] = {"status": res["status"],
                                   "proposalStatus": (res["payload"] or {}).get("status")}
            res = call("POST", "/api/codirector/m29/timeline/%s/apply" % prop["id"], {})
            out["videoApply"] = {"status": res["status"],
                                 "proposalStatus": (res["payload"] or {}).get("status")}

    res = call("GET", "/api/projects/%s/scenes/%s/director" % (pid, sid))
    d = res["payload"] or {}
    out["directorAfter"] = {
        "audio_clips": len(d.get("audio_clips") or []),
        "sfx_clips": len(d.get("sfx_clips") or []),
        "image_clips": len(d.get("image_clips") or []),
        "video_clips": len(d.get("video_clips") or []),
        "video_asset_ids": [c.get("asset_id") for c in (d.get("video_clips") or [])],
    }

    # 3. Re-export the capstone now that every track carries a real asset.
    if n == 12:
        res = call("POST", "/api/projects/%s/export" % pid, {})
        job = (res["payload"] or {}).get("job") or res["payload"] or {}
        jid = job.get("id") or job.get("jobId")
        out["reexport"] = {"status": res["status"], "jobId": jid}
        if jid:
            done = poll_studio_job(jid) or {}
            out["reexport"]["jobStatus"] = done.get("status")
            out["reexport"]["outputPath"] = done.get("output_path")
            pack = Path(done.get("output_path") or "")
            if pack.exists():
                files = sorted(p for p in pack.rglob("*") if p.is_file())
                out["reexport"]["files"] = [
                    {"name": str(p.relative_to(pack)), "bytes": p.stat().st_size} for p in files
                ]
                proj = pack / "project.json"
                if proj.exists():
                    payload = json.loads(proj.read_text(encoding="utf-8"))
                    scene = next(
                        (s for s in payload.get("scenes", []) if s.get("id") == sid), {}
                    )
                    out["reexport"]["packCarriesTimeline"] = any(
                        k in scene for k in ("director", "director_json", "timeline", "clips")
                    )
                    out["reexport"]["packSceneKeys"] = sorted(scene.keys())
                    out["reexport"]["packRenderedOutput"] = scene.get("output_path")

    results.append(out)
    print(
        "S%02d approve=%s publish=%s gate=%s videoClips=%s"
        % (
            n,
            (out.get("imageApprove") or {}).get("versionStatus"),
            (out.get("imagePublishReference") or {}).get("publishedReference"),
            (out.get("videoApplyBeforeApproval") or {}).get("status", "-"),
            out["directorAfter"]["video_clips"],
        )
    )

(OUT / "situation-finish.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print("wrote", OUT / "situation-finish.json")
