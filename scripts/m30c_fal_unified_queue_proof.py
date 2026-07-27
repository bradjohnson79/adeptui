"""M3.0c Phase 4: one guarded fal.ai job through the Studio queue.

This script intentionally submits at most one paid job. It uses the public API
endpoint consumed by Studio's Txt2Vid UI, which creates and commits the Studio
Job before the queue worker can call fal.ai. It never prints or persists a key.

Usage:
    python scripts/m30c_fal_unified_queue_proof.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30c-fal"
EVIDENCE = OUT / "unified_queue_proof.json"
DEFAULT_BASE = "http://127.0.0.1:8760"
PROMPT = (
    "A cinematic four second dolly through an empty film studio at dawn, "
    "dust motes in warm window light, shallow depth of field."
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request(base: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, {"text": raw[:1000]}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"text": raw[:1000]}
        return exc.code, payload


def env_key_presence() -> dict[str, Any]:
    """Report only presence and source, never the credential value."""
    sources: list[str] = []
    for name in ("FAL_API_KEY", "FAL_KEY"):
        if os.environ.get(name):
            sources.append(f"environment:{name}")
    for path in (ROOT / ".env", ROOT / "studio-api" / ".env"):
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            name = line.split("=", 1)[0].strip().removeprefix("export ").strip()
            if name in {"FAL_API_KEY", "FAL_KEY"} and "=" in line and line.split("=", 1)[1].strip():
                sources.append(f"{path.relative_to(ROOT)}:{name}")
    return {"present": bool(sources), "sources": sources}


def save(payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    base = os.environ.get("STUDIO_PROOF_BASE_URL", DEFAULT_BASE)
    started = now()
    evidence: dict[str, Any] = {
        "phase": "M3.0c Phase 4",
        "startedAt": started,
        "baseUrl": base,
        "outcome": "NOT_RUN",
        "submitted": False,
        "singleSubmitGuard": True,
        "cost": {
            "budgetCapUsd": 15.0,
            "estimateUsd": "unknown; provider pricing/account billing not exposed by queue",
            "guard": "one 4s 480p Seedance request maximum; no automatic retry",
        },
        "inputs": {
            "endpoint": "POST /api/projects/{projectId}/txt2vid",
            "engine": "fal_seedance",
            "durationSec": 4,
            "width": 854,
            "height": 480,
            "generateAudio": False,
            "prompt": PROMPT,
        },
        "envKeyPresence": env_key_presence(),
    }
    if EVIDENCE.exists():
        try:
            prior = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = {}
        if prior.get("submitted"):
            evidence["blocker"] = "Existing evidence says a paid submission already occurred; refusing a second request."
            save(evidence)
            return 3

    try:
        status, health = request(base, "GET", "/api/health")
        evidence["apiHealth"] = {"status": status, "ok": status == 200}
        if status != 200:
            raise RuntimeError(f"API health returned HTTP {status}")
    except Exception as exc:  # noqa: BLE001
        evidence["blocker"] = f"API unavailable: {type(exc).__name__}: {exc}"
        save(evidence)
        return 2

    status, fal_status = request(base, "GET", "/api/fal/key")
    evidence["falBridgeStatus"] = {
        "httpStatus": status,
        "state": fal_status.get("state") if isinstance(fal_status, dict) else None,
        "configured": fal_status.get("configured") if isinstance(fal_status, dict) else None,
        "verified": fal_status.get("verified") if isinstance(fal_status, dict) else None,
    }
    if status != 200 or not isinstance(fal_status, dict) or not fal_status.get("configured"):
        evidence["blocker"] = "API has no bridged/configured fal credential; no paid request submitted."
        save(evidence)
        return 2

    project_name = f"M3.0c fal queue proof {uuid.uuid4().hex[:8]}"
    status, project = request(
        base,
        "POST",
        "/api/projects",
        {"name": project_name, "engine_default": "fal_seedance"},
    )
    evidence["projectCreate"] = {"httpStatus": status, "projectId": project.get("id") if isinstance(project, dict) else None}
    if status < 200 or status >= 300 or not isinstance(project, dict) or not project.get("id"):
        evidence["blocker"] = f"Could not create temporary project (HTTP {status})."
        save(evidence)
        return 2
    project_id = project["id"]

    body = {
        "prompt": PROMPT,
        "engine": "fal_seedance",
        "duration_sec": 4,
        "width": 854,
        "height": 480,
        "fps": 24,
        "generate_audio": False,
        "tag": "m30c-fal-unified-proof",
    }
    # This is the only call that can cause a paid provider submission.
    status, created = request(base, "POST", f"/api/projects/{project_id}/txt2vid", body)
    evidence["queueSubmit"] = {
        "httpStatus": status,
        "jobCreatedResponse": True,
        "jobId": created.get("id") if isinstance(created, dict) else None,
        "statusAtResponse": created.get("status") if isinstance(created, dict) else None,
    }
    evidence["submitted"] = status in range(200, 300) and bool(isinstance(created, dict) and created.get("id"))
    save(evidence)
    if not evidence["submitted"]:
        evidence["blocker"] = f"Queue endpoint rejected request (HTTP {status}); no retry will be attempted."
        save(evidence)
        return 1

    job_id = created["id"]
    deadline = time.monotonic() + float(os.environ.get("STUDIO_PROOF_TIMEOUT_SEC", "900"))
    final: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, current = request(base, "GET", f"/api/jobs/{job_id}")
        final = current if isinstance(current, dict) else {}
        state = final.get("status")
        if state in {"done", "failed", "error", "cancelled"}:
            break
        time.sleep(5)
    evidence["jobFinal"] = {
        "httpStatus": status,
        "id": final.get("id"),
        "status": final.get("status"),
        "message": final.get("message"),
        "outputPath": final.get("output_path"),
        "history": final.get("history_json"),
    }
    history = {}
    try:
        history = json.loads(final.get("history_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        pass
    evidence["falRequestIdPresent"] = bool(history.get("falRequestId"))
    evidence["assetLinked"] = bool(final.get("output_path"))

    status, unified = request(base, "GET", f"/api/codirector/jobs/{job_id}")
    evidence["codirectorInspect"] = {
        "httpStatus": status,
        "source": unified.get("source") if isinstance(unified, dict) else None,
        "ok": status == 200 and isinstance(unified, dict) and unified.get("source") == "studio",
    }
    evidence["outcome"] = (
        "SUCCESS"
        if final.get("status") == "done"
        and evidence["falRequestIdPresent"]
        and evidence["assetLinked"]
        and evidence["codirectorInspect"]["ok"]
        else "FAILED_PROOF"
    )
    evidence["finishedAt"] = now()
    save(evidence)
    return 0 if evidence["outcome"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
