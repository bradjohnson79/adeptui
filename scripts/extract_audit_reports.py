"""Extract the final assistant report from each Phase-0 audit subagent transcript.

Reads the JSONL transcripts and writes the last substantial assistant message
from each to a clean markdown file for the doc-writing subagents.
"""

import json
import os
import sys

SRC_DIR = r"C:\Users\bradj\.cursor\projects\c-AdeptFilmWorks-AIVideoStudio\agent-transcripts\131a5b69-674e-4846-81f1-b1ff989c2feb\subagents"
OUT_DIR = r"C:\AdeptFilmWorks\AIVideoStudio\data\tmp\codirector-audit-sources"

AGENTS = {
    "tool-registry": "78024fdd-2dec-44a9-a246-0c5b2bb6845c",
    "routing": "41da07fc-75f8-4d8e-9e1b-a0a7ffeae688",
    "state-isolation": "29e17dd0-2c9a-458f-84be-6f5ee2f7b3be",
    "native-systems": "3b6f0311-d0e7-4cf7-91b7-4d64316f07d1",
}


def iter_events(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def event_text(ev):
    """Best-effort extraction of text content from a transcript event."""
    if not isinstance(ev, dict):
        return ""
    # Common shapes: {"role": "assistant", "content": ...}, {"type": "assistant", "message": {"content": ...}}
    role = ev.get("role") or ev.get("type") or ""
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
            elif isinstance(c, str):
                parts.append(c)
        return mrole, "\n".join(parts)
    return mrole, ""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, agent_id in AGENTS.items():
        path = os.path.join(SRC_DIR, agent_id + ".jsonl")
        if not os.path.exists(path):
            print(f"MISSING {name}: {path}")
            continue
        best_role, best_text = "", ""
        for ev in iter_events(path):
            role, text = event_text(ev)
            if "assistant" in str(role) and len(text) > len(best_text):
                best_role, best_text = role, text
        out = os.path.join(OUT_DIR, f"{name}-report.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(best_text)
        print(f"OK {name}: {len(best_text)} chars -> {out}")


if __name__ == "__main__":
    main()
