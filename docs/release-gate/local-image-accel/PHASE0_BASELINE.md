# Phase 0 — Hardware, Comfy MCP, pipeline profile

Governing plan: Local Image Acceleration + Co-Director Generation Authority.  
No optimizer was applied before this baseline. Character Creator knobs were not changed.

## Live hardware (measured 2026-08-25)

| Field | Value |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5090 |
| Driver | 610.62 |
| VRAM | 32607 MiB (nvidia-smi); Comfy reports 34190458880 bytes |
| Compute capability | 12.0 |
| GPU util at probe | 3% |
| VRAM used at probe | 16329 MiB |

## Desktop Comfy (authoritative Torch, not studio-api `.venv`)

| Field | Value |
| --- | --- |
| URL | http://127.0.0.1:8188 |
| ComfyUI | 0.32.0 (commit c2bcbecd) |
| Python | 3.13.12 |
| PyTorch | 2.10.0+cu130 (CUDA 13.0) |
| Device | cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync |
| Deploy | local-desktop2-standalone |
| Studio API venv torch | **absent** — attention/compile live in Desktop Comfy only |

## Comfy MCP

Stdio client: `data/venvs/mcp/Scripts/comfy-mcp.exe` with `COMFY_BIN=data/venvs/mcp/Scripts/comfy.exe`.  
Cursor has no `comfy` tool namespace. MCP listed tools and called `server_info`, `system_stats`, `which`, `nodes`.

Evidence: `phase0_comfy_mcp.json`, `phase0_comfy_nodes.json`.

Live nodes present: UNETLoader, CLIPLoader, VAELoader, KSampler, TextEncodeQwenImageEditPlus, VAEDecode, SaveImage, LoadImage.

Custom packs observed (MCP freshness): ComfyUI-LTXVideo, ComfyUI-WanVideoWrapper, comfyui-kjnodes, rgthree-comfy, Impact Pack, Easy Use, Hunyuan wrapper, ControlNet aux, Video Helper Suite.

## Production families inspected (code + MCP nodes)

| Family | Workflow class | Inspect | Notes |
| --- | --- | --- | --- |
| Qwen T2I (`qwen2512`) | CD still / Image Generator | MCP nodes + `workflow_execute.py` | Same production path CD already uses |
| Qwen Image Edit 2509 | Character Creator V3 | MCP `TextEncodeQwenImageEditPlus` | Inspect-only. Steps/CFG/size/fp8 frozen |
| Z-Image | CD default still | `zimage.txt2img` | Often the CD family when no reference |
| FLUX | if production-enabled | loaders present | No parallel fast-CD graph |
| Krea/SDXL | selectable | not separately MCP-run this pass | No knobs changed |

## Pipeline profile (optimize only measured bottlenecks)

```
CD request → unified intent → ExecutionPlan persist (PREPARING)
→ capability handler → Studio Job enqueue → Comfy queue
→ load → encode → sample → VAE decode → serialize → Library
→ execution advance → GenerationJob card → next-step chips
```

Image adapter previously did **not** call `free_memory` between CD stills. WAN/video still unloads before heavy graphs. Studio-api has no torch, so attention/compile cannot be certified from this process.

## Timing schema (no invented speedups)

Cold/warm wall-clock for a new optimizer was **not** claimed.  
Residency is quality-neutral policy (skip unload between same-family CD stills; evict for WAN/video or `unload_after_render`). Measured seconds saved vs the previous CD still path: **0** (no unload was occurring).  
Approximate caches, compile-by-default, and attention backend swaps: **rejected / uncertified**.

## Phase 0 gate

MCP verified live Comfy + required production nodes. Hardware recorded. No optimizer applied before this record.
