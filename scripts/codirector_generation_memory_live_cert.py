"""Live cert: Venture retry from pack memory. Reuses Korri. Does not create a project."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
BRIEF = (
    "Create a Silver metallic Venture corridor scene where we see an elevator door "
    "at the end of the corridor, and then about 10 meters ahead, there is a door "
    "that leads to a Combat Chamber room. The corridor should like something you "
    "would see through an underground research facility. Somewhat sci-fi futuristic, "
    "full wide master shot. Please create this image for me now."
)
FORGOT = ("didn't carry over", "need the original prompt", "paste the original prompt", "paste the prompt")


def _post_stream(message: str) -> dict:
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": message}],
            "project_id": PROJECT_ID,
            "mode": "chat",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/codirector/chat/stream",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    events = []
    assistant = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            evt = json.loads(payload)
        except json.JSONDecodeError:
            continue
        events.append(evt)
        if evt.get("type") in {"assistant", "completed", "completion"} and evt.get("content"):
            assistant.append(str(evt.get("content")))
        if evt.get("type") == "delta" and evt.get("text"):
            assistant.append(str(evt.get("text")))
    text = "".join(assistant)
    execs = [e for e in events if e.get("type") == "execution_status" or e.get("execution")]
    first = execs[0]["execution"] if execs and isinstance(execs[0].get("execution"), dict) else {}
    jobs = list(first.get("jobIds") or first.get("job_ids") or [])
    if not jobs:
        jobs = [c.get("job_id") for c in (first.get("child_jobs") or []) if c.get("job_id")]
    return {
        "assistant": text,
        "execution_id": first.get("execution_id") or first.get("executionId") or "",
        "job_ids": jobs,
        "status": first.get("status") or "",
        "events": events,
        "exec_count": len(execs),
    }


def _forgot(text: str) -> bool:
    blob = (text or "").lower()
    return any(token in blob for token in FORGOT)


def main() -> int:
    only_retry = "--retry-only" in sys.argv
    health = urllib.request.urlopen(f"{API}/api/healthz", timeout=10).read().decode("utf-8")
    print("health", health)
    if only_retry:
        turn2 = _post_stream("Retry with same prompt again and use GPT Image 2.")
        print(
            "TURN2",
            json.dumps(
                {
                    "execution_id": turn2["execution_id"],
                    "job_ids": turn2["job_ids"],
                    "status": turn2["status"],
                    "forgot": _forgot(turn2["assistant"]),
                    "assistant_head": turn2["assistant"][:360],
                },
                indent=2,
            ),
        )
        if _forgot(turn2["assistant"]) or not turn2["job_ids"]:
            print("NO-GO retry-only")
            return 4
        print("LIVE_OK retry-only")
        return 0
    turn1 = _post_stream(BRIEF)
    print(
        "TURN1",
        json.dumps(
            {
                "execution_id": turn1["execution_id"],
                "job_ids": turn1["job_ids"],
                "status": turn1["status"],
                "forgot": _forgot(turn1["assistant"]),
                "assistant_head": turn1["assistant"][:240],
            },
            indent=2,
        ),
    )
    if not turn1["job_ids"]:
        print("NO-GO turn1 did not enqueue")
        return 2
    turn2 = _post_stream("Retry with same prompt again and use GPT Image 2.")
    print(
        "TURN2",
        json.dumps(
            {
                "execution_id": turn2["execution_id"],
                "job_ids": turn2["job_ids"],
                "status": turn2["status"],
                "forgot": _forgot(turn2["assistant"]),
                "assistant_head": turn2["assistant"][:360],
            },
            indent=2,
        ),
    )
    if _forgot(turn2["assistant"]):
        print("NO-GO turn2 asked for the original prompt")
        return 3
    if not turn2["job_ids"]:
        print("NO-GO turn2 did not enqueue a second job")
        return 4
    if turn2["execution_id"] == turn1["execution_id"]:
        print("NO-GO turn2 reused the old execution")
        return 5
    print("LIVE_OK turn1+turn2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
