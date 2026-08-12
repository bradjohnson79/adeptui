#!/usr/bin/env python3
"""Phase 0 isolation bench: A (direct Ollama) vs E-style Co-Director stream timings."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

MESSAGE = (
    "Yes — Agent Gold is a great name. For this project I want a hands-on Balanced Co-Director: "
    "listen first while I tell the story, capture confirmed facts as we go, and help me stay creatively engaged."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bench_a_direct_ollama(endpoint: str, model: str, timeout: float = 180.0) -> dict:
    """Test A — direct provider inference with stream=true."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": MESSAGE}],
        "stream": True,
        "keep_alive": "30m",
        "options": {"temperature": 0.7},
    }
    t0 = time.perf_counter()
    first_token_at = None
    chunks = 0
    text = []
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = data.get("message") if isinstance(data, dict) else None
            piece = ""
            if isinstance(msg, dict):
                piece = str(msg.get("content") or "")
            if piece:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                chunks += 1
                text.append(piece)
            if isinstance(data, dict) and data.get("done"):
                break
    t1 = time.perf_counter()
    return {
        "path": "A_direct_ollama_stream",
        "ok": bool(text),
        "ttftMs": round(((first_token_at or t1) - t0) * 1000, 1),
        "totalMs": round((t1 - t0) * 1000, 1),
        "chunks": chunks,
        "chars": sum(len(x) for x in text),
        "model": model,
    }


def bench_e_codirector_stream(api: str, project_id: str, timeout: float = 300.0) -> dict:
    """Test E — full current Co-Director orchestration via /chat/stream."""
    body = {
        "messages": [{"role": "user", "content": MESSAGE}],
        "project_id": project_id,
        "mode": "chat",
    }
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/codirector/chat/stream",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    t0 = time.perf_counter()
    first_token_at = None
    first_stage_at = None
    stages: list[str] = []
    tokens = 0
    completed = False
    timings = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                et = event.get("type")
                if et == "processing_stage":
                    if first_stage_at is None:
                        first_stage_at = time.perf_counter()
                    stages.append(str(event.get("stage") or ""))
                elif et == "token":
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    tokens += 1
                elif et == "conversation_timings":
                    timings = event.get("timings")
                elif et == "completed":
                    completed = True
                    break
    except Exception as exc:  # noqa: BLE001
        t1 = time.perf_counter()
        return {
            "path": "E_full_orchestration",
            "ok": False,
            "error": str(exc)[:400],
            "ttftMs": None,
            "totalMs": round((t1 - t0) * 1000, 1),
            "stages": stages,
            "tokens": tokens,
        }
    t1 = time.perf_counter()
    return {
        "path": "E_full_orchestration",
        "ok": completed or tokens > 0,
        "ttftMs": round(((first_token_at or t1) - t0) * 1000, 1) if first_token_at else None,
        "firstStageMs": round(((first_stage_at or t1) - t0) * 1000, 1) if first_stage_at else None,
        "totalMs": round((t1 - t0) * 1000, 1),
        "stages": stages[:40],
        "tokens": tokens,
        "coreTimings": timings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8758")
    parser.add_argument("--ollama", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    run_id = (ROOT / "docs/release-gate/co-director-performance/artifacts/CURRENT_RUN_ID.txt").read_text(
        encoding="utf-8"
    ).strip()
    out_dir = Path(args.out) if args.out else ROOT / "docs/release-gate/co-director-performance/artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    model = args.model
    if not model:
        tags = json.loads(urllib.request.urlopen(f"{args.ollama}/api/tags", timeout=10).read().decode())
        models = tags.get("models") or []
        model = str((models[0] or {}).get("name") or "") if models else ""

    project_id = args.project_id
    if not project_id:
        # Prefer existing cert project if present
        project_id = "ae57714e-d43e-4cec-9bd9-0af2780fa185"

    rows = []
    print(f"[isolation] A direct ollama model={model}", flush=True)
    rows.append(bench_a_direct_ollama(args.ollama, model))
    print(f"  -> ttft={rows[-1].get('ttftMs')} total={rows[-1].get('totalMs')}", flush=True)

    print(f"[isolation] E codirector stream project={project_id}", flush=True)
    rows.append(bench_e_codirector_stream(args.api, project_id))
    print(
        f"  -> ttft={rows[-1].get('ttftMs')} total={rows[-1].get('totalMs')} tokens={rows[-1].get('tokens')}",
        flush=True,
    )

    a = rows[0]
    e = rows[1]
    dominant = "unknown"
    if a.get("ttftMs") and a["ttftMs"] > 20000:
        dominant = "provider_model_runtime"
    elif e.get("ttftMs") and a.get("ttftMs") and e["ttftMs"] > a["ttftMs"] + 5000:
        dominant = "orchestration_or_fake_stream_or_pre_llm_sync"
    elif e.get("ttftMs") is None and e.get("totalMs", 0) > 60000:
        dominant = "orchestration_pre_token_stall"

    matrix = {
        "runId": run_id,
        "generatedAt": _now(),
        "messageClass": "onboarding_working_agreement",
        "rows": rows,
        "dominantCauseHypothesis": dominant,
        "interpretation": {
            "A_slow": "provider/model runtime defect",
            "A_fast_E_slow": "Conversation Core / fake stream / sync wiki side effects",
        },
    }
    path = out_dir / "isolation_matrix.json"
    path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}", flush=True)
    print(f"dominant={dominant}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
