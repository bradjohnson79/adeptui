"""Stdio Comfy MCP verification for local video closure.

Never calls launch/stop/restart_comfyui. Points at live Adept :8188.
Run with: data\\venvs\\mcp\\Scripts\\python.exe
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MCP_EXE = ROOT / r"data\venvs\mcp\Scripts\comfy-mcp.exe"
COMFY_BIN = ROOT / r"data\venvs\mcp\Scripts\comfy.exe"
OUT_DIR = Path(__file__).resolve().parent / "evidence"
OUT = OUT_DIR / "COMFY_MCP_CLOSURE.json"

NODES = (
    "LoadImage",
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "VAEDecode",
    "VHS_VideoCombine",
    "LTXVImgToVideo",
    "LTXVConditioning",
    "LTXAVTextEncoderLoader",
    "SamplerCustomAdvanced",
    "BasicScheduler",
    "CFGGuider",
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "WanFirstLastFrameToVideo",
    "KSamplerAdvanced",
    "ModelSamplingSD3",
    "MiniMaxH3ReferenceToVideo",
    "EasyCache",
)

SEARCH = (
    "ltx-2.3-22b-distilled-fp8",
    "wan2.2_i2v_high_noise_14B",
    "wan2.2_i2v_low_noise_14B",
    "umt5_xxl_fp8",
    "minimax_h3_ref2va_pruned_int8",
    "minimax_h3_video_vae",
    "qwen3vl_32b_minimax_h3",
)

GRAPHS = {
    "ltx_23": OUT_DIR / "mcp_graph_ltx_23.json",
    "wan_flf": OUT_DIR / "mcp_graph_wan_flf.json",
    "h3_ref2v": OUT_DIR / "mcp_graph_h3_ref2v.json",
}


def _texts(result) -> list[str]:
    out = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            out.append(text[:8000])
    return out


async def main() -> int:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(command=str(MCP_EXE), env={"COMFY_BIN": str(COMFY_BIN)})
    payload: dict = {
        "ok": False,
        "transport": "stdio",
        "exe": str(MCP_EXE),
        "tools": [],
        "calls": {},
        "graphs": {k: str(v) for k, v in GRAPHS.items()},
        "forbidden": {"launch_comfyui": False, "stop_comfyui": False, "restart_comfyui": False},
        "error": "",
    }
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                payload["tools"] = [t.name for t in listed.tools]
                for name in ("launch_comfyui", "stop_comfyui", "restart_comfyui"):
                    payload["forbidden"][name] = name in payload["tools"]
                for name, args in (
                    ("server_info", {}),
                    ("system_stats", {}),
                    *[("nodes", {"action": "get", "name": node}) for node in NODES],
                    *[("search_models", {"query": q}) for q in SEARCH],
                ):
                    key = name if name != "nodes" else f"nodes:{args.get('name')}"
                    if name == "search_models":
                        key = f"search:{args.get('query')}"
                    if name not in payload["tools"]:
                        payload["calls"][key] = ["TOOL_MISSING"]
                        continue
                    result = await session.call_tool(name, args)
                    payload["calls"][key] = _texts(result)
                if "validate_workflow" in payload["tools"]:
                    for key, path in GRAPHS.items():
                        if not path.exists():
                            payload["calls"][f"validate:{key}"] = [f"MISSING_GRAPH {path}"]
                            continue
                        result = await session.call_tool("validate_workflow", {"workflow_path": str(path)})
                        payload["calls"][f"validate:{key}"] = _texts(result)
                payload["ok"] = True
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    OUT.write_text(json.dumps(payload, indent=2)[:200000], encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "toolCount": len(payload["tools"]), "error": payload["error"]}, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
