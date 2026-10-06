"""POST one live Co-Director chat payload to :8758 and save the result."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8758"


def slim(payload: dict) -> dict:
    invocations = []
    for item in payload.get("toolInvocations") or []:
        result = item.get("result") or {}
        data = result.get("data") if isinstance(result, dict) else {}
        invocations.append(
            {
                "toolId": item.get("toolId") or result.get("toolId"),
                "status": item.get("status") or result.get("status"),
                "summary": result.get("summary") if isinstance(result, dict) else None,
                "executed": data.get("executed") if isinstance(data, dict) else None,
                "dialogueA": data.get("dialogueA") if isinstance(data, dict) else None,
                "dialogueB": data.get("dialogueB") if isinstance(data, dict) else None,
                "certifiedReady": data.get("certifiedReady") if isinstance(data, dict) else None,
                "gateLine": data.get("gateLine") if isinstance(data, dict) else None,
                "runtimeGate": data.get("runtimeGate") if isinstance(data, dict) else None,
                "ok": data.get("ok") if isinstance(data, dict) else None,
            }
        )
    return {
        "reply": payload.get("reply"),
        "fallbackUsed": payload.get("fallbackUsed"),
        "fallbackReason": payload.get("fallbackReason"),
        "providerError": payload.get("providerError"),
        "model": payload.get("model"),
        "invocations": invocations,
    }


def main() -> None:
    name = sys.argv[1]
    payload_path = ROOT / f"_closure_{name}_payload.json"
    out_path = ROOT / f"_closure-chat-{name}.json"
    body = payload_path.read_bytes()
    req = urllib.request.Request(
        f"{BASE}/api/codirector/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    slimmed = slim(payload)
    out_path.write_text(json.dumps(slimmed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(
        {
            "name": name,
            "fallbackUsed": slimmed["fallbackUsed"],
            "tools": [item["toolId"] for item in slimmed["invocations"]],
            "replyHead": (slimmed["reply"] or "")[:400],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
