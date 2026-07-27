"""M2.5 vision validation over the real artifacts produced by the situation run.

This is the inspect link in the chain: the local provider decodes the actual PNG and
reports measured metrics, so the approval that follows is a decision about a real image
rather than about a record that claims one exists.
"""

from __future__ import annotations

import glob
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("M30_API", "http://127.0.0.1:8760")
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "m30-situations"


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


results = []
for path in sorted(glob.glob(str(OUT / "situation-*-production.json"))):
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    n, pid, sid = rec["n"], rec["projectId"], rec["sceneId"]
    asset = rec.get("imageAssetId")
    out = {"n": n, "situation": rec["situation"], "projectId": pid, "assetId": asset}
    if not asset:
        results.append(out)
        continue

    res = call(
        "POST",
        "/api/codirector/vision/validate",
        {"projectId": pid, "assetId": asset, "sceneId": sid, "provider": "local"},
    )
    payload = res["payload"] or {}
    session = payload.get("session") or {}
    report = payload.get("report") or {}
    findings = report.get("findings") or []
    metrics = {}
    for f in findings:
        if f.get("metrics"):
            metrics.update(f["metrics"])
    out["validate"] = {
        "status": res["status"],
        "sessionId": session.get("sessionId"),
        "sessionStatus": session.get("status"),
        "provider": report.get("provider") or session.get("provider"),
        "overallScore": report.get("overallScore"),
        "band": report.get("band"),
        "passed": report.get("passed"),
        "findingCount": len(findings),
        "findingStatuses": sorted({f.get("status") for f in findings}),
        "validators": [f.get("validatorId") for f in findings],
        "measured": {
            k: metrics[k]
            for k in ("width", "height", "aspectRatio", "meanLuma", "laplacianVariance", "source")
            if k in metrics
        },
        "warnings": (report.get("warnings") or [])[:4],
        "recommendations": (report.get("recommendations") or [])[:4],
    }

    if session.get("sessionId"):
        res = call(
            "POST",
            "/api/codirector/vision/approve",
            {
                "projectId": pid,
                "sessionId": session["sessionId"],
                "reviewer": "m30-operator",
                "notes": "Reviewed measured metrics on the real artifact.",
            },
        )
        body = res["payload"] or {}
        approval = body.get("approval") or body
        out["visionApprove"] = {
            "status": res["status"],
            "decision": approval.get("decision"),
            "reviewer": approval.get("reviewer"),
            "sessionStatus": (body.get("session") or {}).get("status"),
        }

    results.append(out)
    v = out.get("validate") or {}
    print(
        "S%02d validate=%s band=%s score=%s findings=%s measured=%s approve=%s"
        % (
            n,
            v.get("status"),
            v.get("band"),
            v.get("overallScore"),
            v.get("findingCount"),
            v.get("measured", {}).get("source"),
            (out.get("visionApprove") or {}).get("decision"),
        )
    )

(OUT / "situation-vision.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print("wrote", OUT / "situation-vision.json")
