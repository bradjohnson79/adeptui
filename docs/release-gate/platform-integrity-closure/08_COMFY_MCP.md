# 08 — Gate H Comfy MCP

**Surface:** CURRENT DEVELOPMENT (session MCP catalog has no Comfy namespace)  
**Date:** 2026-08-30

## Method

Stdio `data/venvs/mcp/Scripts/comfy-mcp.exe` via `mcp.client.stdio` — **not** HTTP `/history`.

Evidence: `08_COMFY_MCP.json`

## Observed

- Tools listed: 39 (`server_info`, `system_stats`, `nodes`, `validate_workflow`, `job`, …)
- `server_info.server.url` = `http://127.0.0.1:8188`, `running: true`
- GPU: NVIDIA GeForce RTX 5090
- `system_stats` devices: `cuda:0 NVIDIA GeForce RTX 5090`
- Nodes present: `LoadImage`, `LTXVImgToVideo`, `CheckpointLoaderSimple`
- Checkpoints include `ltx-2.3-22b-distilled-fp8.safetensors` and `ltx-2.3-22b-dev-fp8.safetensors`

Cursor session still has no Comfy MCP namespace. Certification used the installed stdio client, same method as prior Timeline MCP certs.

## Peer close

- Kimi K3 (`f5cca296`): **PASS** — real stdio `comfy-mcp.exe`, not HTTP `/history`.
- GLM 5.2 (`7b99191e`): **PASS** — 39 tools match the installed server; live `:8188` system_stats / checkpoints corroborate the JSON.

**Gate H: CLOSED**
