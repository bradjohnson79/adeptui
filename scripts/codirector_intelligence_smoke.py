"""Live Co-Director intelligence remediation smoke against Schnick Coffee / Korri.

Verdicts:
  PASS — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE
  FAIL — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8758")
PROJECT_ID = os.environ.get("ADEPT_PROJECT_ID", "2347bf46-3762-4763-86c5-4a6032522278")
KORRI_ID = os.environ.get("ADEPT_KORRI_ID", "c49371ed-ba6b-4c16-ba98-a8b28b72118b")
EVIDENCE = ROOT / "docs" / "release-gate" / "codirector-reasoning" / "evidence"
CRITICAL = "Create Korri's CRS."


def _fail(reason: str) -> int:
    print("FAIL — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE")
    print(f"BLOCKER: {reason}")
    return 1


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    request_id = f"intel-smoke-{uuid.uuid4().hex[:10]}"
    payload = {
        "messages": [{"role": "user", "content": CRITICAL}],
        "project_id": PROJECT_ID,
        "character_id": KORRI_ID,
        "characterId": KORRI_ID,
        "mode": "chat",
        "request_id": request_id,
    }
    started = time.time()
    events: list[dict] = []
    try:
        with httpx.Client(timeout=180.0) as client:
            health = client.get(f"{API}/api/health")
            if health.status_code != 200:
                return _fail(f"API health {health.status_code}")
            with client.stream(
                "POST",
                f"{API}/api/codirector/chat/stream",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                if resp.status_code != 200:
                    return _fail(f"stream HTTP {resp.status_code}")
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
                    if not line.startswith("data:"):
                        continue
                    body = json.loads(line[5:].strip() or "{}")
                    events.append(body)
                    if body.get("type") in {"completed", "cancelled", "error"}:
                        break
    except Exception as exc:
        return _fail(f"request failed: {exc}")

    speech = ""
    sufficient = None
    clarification = None
    resolved = ""
    capability = ""
    job_started = False
    for event in events:
        et = str(event.get("type") or "")
        if et == "speech_act":
            speech = str(event.get("speech_act") or "")
        elif et == "context_sufficient":
            sufficient = event.get("context_sufficient")
            clarification = event.get("clarification_required")
            resolved = str(event.get("resolved_action") or "")
        elif et == "route_decision" or et == "unified_intent":
            capability = str(event.get("capability") or event.get("unified_intent", {}).get("capability") or capability)
        elif et in {"execution_status", "tool_started", "job_started"}:
            job_started = True
            capability = capability or str(event.get("execution", {}).get("capability") or "")
        exec_payload = event.get("execution") if isinstance(event.get("execution"), dict) else {}
        if exec_payload.get("capability"):
            capability = str(exec_payload.get("capability") or capability)
            job_started = True

    evidence = {
        "requestId": request_id,
        "elapsedSec": round(time.time() - started, 2),
        "speech_act": speech,
        "context_sufficient": sufficient,
        "clarification_required": clarification,
        "resolved_action": resolved,
        "capability": capability,
        "job_started": job_started,
        "event_types": [str(e.get("type") or "") for e in events][:40],
    }
    (EVIDENCE / "codirector-intelligence-smoke.json").write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2))

    if speech != "COMMAND":
        return _fail(f"intent={speech!r} expected COMMAND")
    if sufficient is not True:
        return _fail(f"context_sufficient={sufficient!r} expected true")
    if clarification is True:
        return _fail("clarification_required=true")
    action_ok = resolved in {
        "create_character_reference_sheet",
        "character.generate_visual_sheet",
        "character_creator.propose_visual_sheet",
    } or capability in {
        "create_character_reference_sheet",
        "character.generate_visual_sheet",
    }
    if not action_ok:
        return _fail(f"action={resolved!r} capability={capability!r}")
    if not job_started:
        return _fail("job did not start")

    print("PASS — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
