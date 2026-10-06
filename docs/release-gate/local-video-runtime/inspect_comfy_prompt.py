"""Read-only Comfy /history + MCP job inspect. Never launch/stop Comfy."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
MCP_EXE = ROOT / r"data\venvs\mcp\Scripts\comfy-mcp.exe"
COMFY_BIN = ROOT / r"data\venvs\mcp\Scripts\comfy.exe"
PROMPT = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = Path(__file__).resolve().parent / "evidence" / f"COMFY_PROMPT_{PROMPT[:8]}.json"


def summarize(workflow: dict) -> dict:
    classes = []
    keep = {}
    for nid, node in (workflow or {}).items():
        if not isinstance(node, dict):
            continue
        cls = str(node.get("class_type") or "")
        classes.append(cls)
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        for key in (
            "ckpt_name",
            "unet_name",
            "vae_name",
            "clip_name",
            "text_encoder",
            "width",
            "height",
            "length",
            "frame_rate",
            "start_image",
            "end_image",
            "image",
            "filename_prefix",
            "sampler_name",
            "scheduler",
            "weight_dtype",
        ):
            if key in inputs and not isinstance(inputs[key], list):
                keep[f"{nid}.{cls}.{key}"] = inputs[key]
    return {"classTypes": classes, "inputs": keep}


async def mcp_job(prompt_id: str) -> dict:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=str(MCP_EXE), env={"COMFY_BIN": str(COMFY_BIN)})
    out = {"ok": False, "tools": [], "calls": {}}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            out["tools"] = tools
            if "job" in tools:
                result = await session.call_tool("job", {"prompt_id": prompt_id})
                out["calls"]["job"] = [getattr(b, "text", "") or "" for b in result.content][:2]
            out["ok"] = True
    return out


def main() -> int:
    if not PROMPT:
        print("usage: inspect_comfy_prompt.py PROMPT_ID")
        return 2
    hist = httpx.get(f"http://127.0.0.1:8188/history/{PROMPT}", timeout=20).json()
    entry = hist.get(PROMPT) or (next(iter(hist.values())) if hist else {})
    wf = (entry.get("prompt") or [None, None, {}])
    workflow = wf[2] if isinstance(wf, list) and len(wf) > 2 else {}
    if not isinstance(workflow, dict):
        workflow = {}
    payload = {
        "promptId": PROMPT,
        "historyKeys": list(hist.keys())[:5],
        "summary": summarize(workflow),
        "status": entry.get("status"),
        "mcp": {},
    }
    try:
        payload["mcp"] = asyncio.run(mcp_job(PROMPT))
    except Exception as exc:
        payload["mcp"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "httpHistoryUsed": True}
    OUT.write_text(json.dumps(payload, indent=2)[:120000], encoding="utf-8")
    print(json.dumps({"ok": True, "classes": payload["summary"]["classTypes"], "mcpOk": payload["mcp"].get("ok")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
