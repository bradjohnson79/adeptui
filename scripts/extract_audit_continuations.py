"""Append continuation report messages to already-extracted audit source files.

Some subagents split their final report across multiple assistant messages.
This appends any substantial assistant message containing 'Report (continued)'
to the matching source file, in transcript order.
"""

import json
import os

SRC_DIR = r"C:\Users\bradj\.cursor\projects\c-AdeptFilmWorks-AIVideoStudio\agent-transcripts\131a5b69-674e-4846-81f1-b1ff989c2feb\subagents"
OUT_DIR = r"C:\AdeptFilmWorks\AIVideoStudio\data\tmp\codirector-audit-sources"

AGENTS = {
    "tool-registry": "78024fdd-2dec-44a9-a246-0c5b2bb6845c",
    "routing": "41da07fc-75f8-4d8e-9e1b-a0a7ffeae688",
    "state-isolation": "29e17dd0-2c9a-458f-84be-6f5ee2f7b3be",
    "native-systems": "3b6f0311-d0e7-4cf7-91b7-4d64316f07d1",
}


def event_text(ev):
    if not isinstance(ev, dict):
        return "", ""
    role = ev.get("role") or ""
    msg = ev.get("message") if isinstance(ev.get("message"), dict) else ev
    mrole = msg.get("role") or role
    content = msg.get("content")
    if isinstance(content, str):
        return mrole, content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return mrole, "\n".join(parts)
    return mrole, ""


def main():
    for name, agent_id in AGENTS.items():
        path = os.path.join(SRC_DIR, agent_id + ".jsonl")
        if not os.path.exists(path):
            continue
        continuations = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role, text = event_text(ev)
                if "assistant" in str(role) and "continued" in text[:400] and len(text) > 3000:
                    continuations.append(text)
        if continuations:
            out = os.path.join(OUT_DIR, f"{name}-report.md")
            with open(out, "a", encoding="utf-8") as f:
                for c in continuations:
                    f.write("\n\n")
                    f.write(c)
            print(f"APPENDED {name}: {len(continuations)} continuation(s), {sum(len(c) for c in continuations)} chars")
        else:
            print(f"NO CONTINUATION {name}")


if __name__ == "__main__":
    main()
