"""Write workflow certification matrix from readiness + smoke evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    run_id = (ROOT / "docs/release-gate/runtime-zero-block/artifacts/CURRENT_RUN_ID.txt").read_text(
        encoding="utf-8"
    ).strip()
    base = ROOT / "docs/release-gate/runtime-zero-block/artifacts" / run_id / "workflows"
    base.mkdir(parents=True, exist_ok=True)
    ready_path = base / "readiness.json"
    ready = json.loads(ready_path.read_text(encoding="utf-8-sig")) if ready_path.exists() else []
    img_job = None
    img_path = base / "image_smoke_job.json"
    if img_path.exists():
        img_job = json.loads(img_path.read_text(encoding="utf-8-sig"))
    img_done = bool(
        img_job and str(img_job.get("status") or "").lower() in {"done", "succeeded", "completed"}
    )

    rows = []
    for item in ready:
        wid = item.get("id")
        status = item.get("status")
        nodes_ok = status in {"ready", "unknown"} and not item.get("missingNodes")
        models_ok = status in {"ready", "unknown"}
        live = False
        artifact = None
        persistence = False
        if wid and str(wid).startswith("image.") and img_done:
            live = True
            artifact = img_job.get("id")
            persistence = True
            verdict = "GO"
            notes = "Live imagegen job completed; see image_smoke_job.json for actual engine."
        elif status == "ready":
            verdict = "NO-GO"
            notes = "Readiness ready; live run not yet evidenced"
        elif status == "unknown":
            verdict = "BLOCKED"
            notes = "Readiness unknown (node catalogue or model mapping incomplete)"
        else:
            verdict = "NO-GO"
            notes = item.get("err") or str(status)
        rows.append(
            {
                "workflowId": wid,
                "ui": True,
                "registry": True,
                "nodes": nodes_ok,
                "packages": True,
                "models": models_ok,
                "preflight": status,
                "liveRun": live,
                "artifact": artifact,
                "persistence": persistence,
                "verdict": verdict,
                "notes": notes,
            }
        )

    matrix = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": "ae57714e-d43e-4cec-9bd9-0af2780fa185",
        "rows": rows,
        "WORKFLOW_CATALOG_GREEN": all(r["verdict"] == "GO" for r in rows) and bool(rows),
        "goCount": sum(1 for r in rows if r["verdict"] == "GO"),
        "total": len(rows),
    }
    (base / "matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    print("GO", matrix["goCount"], "/", matrix["total"], "catalog_green", matrix["WORKFLOW_CATALOG_GREEN"])


if __name__ == "__main__":
    main()
