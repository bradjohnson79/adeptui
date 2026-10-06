"""Live :8758 Co-Director chat recert. Does not POST /api/projects. Not TestClient."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278"
SESSION_ID = "avs-a10ef709c2"
BASE = "http://127.0.0.1:8758"
OUT = Path(__file__).resolve().parent


def post(path: str, body: dict, timeout: int = 180) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get(path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def slim_invocations(payload: dict) -> list[dict]:
    out = []
    for item in payload.get("toolInvocations") or []:
        result = item.get("result") or {}
        data = result.get("data") if isinstance(result, dict) else {}
        out.append(
            {
                "toolId": item.get("toolId") or result.get("toolId"),
                "status": item.get("status") or result.get("status"),
                "summary": result.get("summary") if isinstance(result, dict) else None,
                "executed": data.get("executed") if isinstance(data, dict) else None,
                "dialogueA": data.get("dialogueA") if isinstance(data, dict) else None,
                "certifiedReady": data.get("certifiedReady") if isinstance(data, dict) else None,
                "gateLine": data.get("gateLine") if isinstance(data, dict) else None,
                "dataKeys": sorted(data.keys()) if isinstance(data, dict) else [],
            }
        )
    return out


def chat(text: str) -> dict:
    return post(
        "/api/codirector/chat",
        {
            "messages": [{"role": "user", "content": text}],
            "project_id": PROJECT_ID,
            "mode": "chat",
            "workspace_tab": "avatar",
            "workspaceTab": "avatar",
        },
        timeout=180,
    )


def main() -> None:
    health = get("/api/health")
    inspect = post(
        f"/api/codirector/projects/{PROJECT_ID}/tools/read",
        {"toolId": "avatar.inspect", "arguments": {"sessionId": SESSION_ID}},
        timeout=60,
    )
    turns = [
        "What have I set up in Avatar Studio?",
        'Change Korri\'s line to "Absolutely not."',
        "Generate it with InfiniteTalk.",
        "Which Avatar Studio generators are ready?",
    ]
    chats = []
    for text in turns:
        payload = chat(text)
        chats.append(
            {
                "user": text,
                "reply": payload.get("reply"),
                "fallbackUsed": payload.get("fallbackUsed"),
                "fallbackReason": payload.get("fallbackReason"),
                "providerError": payload.get("providerError"),
                "model": payload.get("model"),
                "invocations": slim_invocations(payload),
            }
        )
    session = get(f"/api/projects/{PROJECT_ID}/avatar-sessions/{SESSION_ID}")
    inspect_after = post(
        f"/api/codirector/projects/{PROJECT_ID}/tools/read",
        {"toolId": "avatar.inspect", "arguments": {"sessionId": SESSION_ID}},
        timeout=60,
    )
    report = {
        "health": {
            "apiRevision": health.get("apiRevision"),
            "apiStartedAt": health.get("apiStartedAt"),
        },
        "inspectBeforeSummary": (inspect.get("result") or {}).get("summary"),
        "inspectBefore": (inspect.get("result") or {}).get("data"),
        "chats": chats,
        "sessionAfter": {
            "id": session.get("id"),
            "mode_kind": session.get("mode_kind"),
            "conversation": session.get("conversation"),
            "speakers": [
                {"id": s.get("id"), "label": s.get("label"), "character_id": s.get("character_id")}
                for s in (session.get("speakers") or [])
            ],
            "provider_choice": session.get("provider_choice"),
            "look_aspect": (session.get("look") or {}).get("aspect"),
        },
        "inspectAfter": (inspect_after.get("result") or {}).get("data"),
    }
    (OUT / "_closure-live-chat.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"health": report["health"], "chats": [
        {"user": c["user"], "fallbackUsed": c["fallbackUsed"], "invocations": [i["toolId"] for i in c["invocations"]], "replyHead": (c["reply"] or "")[:240]}
        for c in chats
    ]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
