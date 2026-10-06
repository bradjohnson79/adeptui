# Adept v1.1 Canvas Fidelity + Precise VRAM Freeze

**Date:** 2026-09-05  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455` (working tree dirty; this freeze is not a commit)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Surfaces:** Vite `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Governing:** this file + `00_FREEZE.md` (generator identity). This file owns canvas, duration, VRAM, 3 Frame honesty, and native/upscale labels.

Supersedes coarse VRAM buckets (`8/16/24/32+`) as **execution** authority.  
Does not replace `00_FREEZE.md` product IDs.

## COMFY BEFORE (read-only, 2026-09-05)

- Port `:8188` HTTP 200 `system_stats`
- PID **69108** · `python` · Comfy Desktop standalone-env
- Comfy `0.32.0` · torch `2.10.0+cu130` · GPU RTX 5090
- `vram_total` 34190458880 B = **31.84 GB** · `vram_free` 32211574784 B
- nvidia-smi: 32607 MiB total · 29215 MiB free · 2973 MiB used · recommended_tier still **32** (coarse)
- Route A `:8192` present — do not start/stop
- **COMFY RESTARTED?: NO**
- Comfy MCP: no Cursor namespace. Workflow-level graph cert = **E2E BLOCKED** until MCP attaches.

## Journey 0 evidence (not rediscovered)

Used, not re-audited from zero:

- `00_FREEZE.md` + prior CRT join (`/api/engines` is now the join view)
- `docs/release-gate/audit-handoff/ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR.md`
- Live 1 Frame tensor class: H3 `/32` — 1280×720 → latent 80×45 → `SamplerCustomAdvanced` pack failure (`route_a_adapter.assert_h3_legal_canvas`)
- LTX 2.5 same `/32` class — `_snap_ltx_25_spatial` still **mutates** 1280×720 → 1280×704 on the execution path
- `clamp_frames` still mutates Timeline export duration
- `resolve_render_plan` still min()s canvas/FPS on ≤24 GB profiles
- `apply_profile_to_project` still overwrites width/height/fps
- Certified registry still **Certified** for `ltx.simple_i2v`, `ltx.scene`, `wan.*`
- `workflow_capabilities` maps LTX 2.5 `multiFrame` → `ltx_25.i2v` (ordinary I2V, last frame optional)
- Frontend `resolutionToSize` publishes 720p as 1280×720 and omits 480p; 1440p is not a v1.1 tier
- Co-Director `systems/video-generation.md` still teaches WAN as a current path
- Live preview tap exists (`video_runtime/live_preview.py` + Comfy WS) — DraftSequencePlayer is not proof
- Ollama factory default is still `gemma4:31b-it-qat`

## Live walk (measured 2026-09-05, confirm-only)

`GET /api/healthz` → `{"status":"ok"}`  
`GET /api/engines` (join view, current):

| id | label | group |
|---|---|---|
| auto | Auto Select | auto |
| minimax-h3 | MiniMax H3 | local |
| ltx-2.5 | LTX 2.5 | local |
| seedance-2.0 | Seedance 2.0 | hosted |
| seedance-2.5 | Seedance 2.5 | hosted |
| fal_kling / fal_veo / fal_runway | hosted | hosted |

No retired local Ready rows. No generic `seedance-fal` product row.

Timeline join: `ltx-2.5-*` adapter `ltx-2.5-distilled`. LTX 2.5 `multiFrame` still reports Ready via `ltx_25.i2v` — **false 3 Frame support**.  
GPU `/api/gpu/stats` still returns `recommended_tier: 32` for 31.84 GB.

## Frozen product law (this journey)

### A. Creator specification fidelity

Adept may inspect, validate, estimate, recommend, warn, or **block before GPU/API spend**.

Adept may never silently:

- clamp / pad / stretch duration
- alter FPS
- change resolution or aspect
- snap dimensions after Generate
- substitute a generator
- downgrade quality
- strip audio
- change frame inputs
- route local → hosted

A generation that “succeeds” by modifying creator specs is a **failed** Adept generation.

### B. Active local families (unchanged from `00_FREEZE.md`)

Only MiniMax H3 and LTX 2.5. Retired: LTX 2.3 / `ltx-local` / WAN / Hunyuan.  
Hosted Seedance 2.0 and 2.5 stay distinct. Auto Select = local-only.

### C. Surfaces

| Surface | Contract | Local Ready only if |
|---|---|---|
| Text2Video | words only, genuine T2V | H3 `route_a.t2va` / LTX `ltx_25.t2v` |
| 1 Frame | exactly one first/start image | H3 `route_a.i2va` / LTX `ltx_25.i2v` |
| 3 Frame | First **required** · Middle **optional** · Last **required** | **none today** — do not infer from ordinary I2V |
| Timeline | R2V / reference-conditioned | H3 `h3.ref2v` / LTX `ltx_25.i2v` one-cond |

LTX 2.5 I2V may *load* extra stills into `optional_cond_images`. That is **not** certified 3 Frame. Last is not required by the builder. Without Comfy MCP proof, local 3 Frame stays **Unsupported / unready**. Do not restore WAN to fill the gap.

### D. One legal-canvas authority

Module: `app.video_runtime.legal_canvas`  
Consumers: CREATE pickers, preflight, builders, Timeline export, GPU panel.  
No second frontend pixel table that can advertise an illegal canvas.

Tiers (standard, nothing below 480p): **480p · 720p · 1080p · 2K · 4K**

Mapping: `model + workflow + aspect + tier → exact legal pixels + native|upscale label`.

Published `/32` 16:9 class (H3 + LTX 2.5). These are the **tier definitions**, not silent snaps of 1280×720:

| Tier | 16:9 legal | Honesty |
|---|---|---|
| 480p | 832×480 | Native 480p |
| 720p | 1280×704 | Native 720p class (704, not 720) |
| 1080p | 1920×1088 | Native 1080p class (1088, not 1080) |
| 2K | 2560×1440 | Native 2K |
| 4K | none native on `/32` (3840×2160 illegal) | Do not advertise Native 4K. If a real upscale graph is wired later: `1080p Generate + 4K Upscale`. Until then: **NOT VIABLE / block** |

Other aspects use the same short-edge class and `/32` legality, computed by the one module.

If the creator (or a saved project) requests 1280×720: **fail before queue**. Suggest 1280×704. Do not snap.

H3 Route A already fail-closes. LTX builders and H3 ref2v must do the same. Remove `_snap_ltx_25_spatial` and ref2v `/32` round from the **execution** path.

### E. Duration fidelity

Remove `clamp_frames` from export/execution.  
Remove silent LTX `8n+1` pad and H3 `snap_h3_length` from execution.

If the workflow cannot honor the exact selected duration at the selected FPS: **block** and name the nearest legal durations. Do not execute a different length.

### F. Precise VRAM authority

Telemetry is exact: GPU name, total GB (e.g. 31.84), allocated, free, residency.

Coarse 8/16/24/32+ may remain as **display history only**. They must not:

- rewrite width/height/fps
- clamp frames
- choose a smaller canvas
- change Auto Select

`apply_profile_to_project` must stop mutating canvas.  
`resolve_render_plan` must stop min()ing creator width/height/fps.  
`/api/gpu/stats` must expose exact GB, not only a bucket.

### G. One viability evaluator (advisory)

`app.video_runtime.vram_viability.evaluate(...)` →

`VIABLE` | `VIABLE WITH MODEL UNLOAD` | `MARGINAL` | `NOT VIABLE`

plus estimated peak, reason, suggestions.

Inputs: model, workflow, legal dims, aspect, FPS, duration/frames, accelerator profile, residency, exact free VRAM.

**Never auto-applies a suggestion.**

### H. GPU panel

Shared across Text2Video / 1 Frame / 3 Frame. Shows exact free/total and per-tier viability for the **selected** workflow. Recommendations are informational.

### I. CRT-A certified leaves

Required v1.1 leaves: LTX 2.5 (`ltx_25.t2v`, `ltx_25.i2v`) and MiniMax H3 (`route_a.*`, `h3.ref2v`).

Demote from active Certified/required product authority (keep readable for old projects):

- `ltx.simple_i2v` · `ltx.scene` · `ltx.ingredients_*`
- `wan.first_last_frame` · `wan.three_frame`

Wave6 may report evidence. It must not decide CREATE eligibility.

### J. CRT-C config

- LTX 2.5 filenames already canonical in `Settings` (`ltx_2_5_*`). Keep them.
- `ltx_checkpoint` (2.3) remains a migration/read field only — not a CREATE readiness gate.
- Ollama factory default: `qwen3.6:35b-a3b`. Fallback: `qwen3.8:27b`. Never overwrite a healthy explicit user selection.

### K. Preview / acceleration / MCP

- Live preview = same job → Comfy WS latent frames → `preview_bus` → `LivePreviewMonitor` → final MP4 replaces preview. Preview failure must not kill the render. No second generation.
- Do not add unbenchmarked accelerators this journey. Preserve Route A isolation, LTX STG/Fast-Quality already in graph, EasyCache on existing Fast paths, no TeaCache.
- If Comfy MCP stays unavailable: workflow-level certification remains **E2E BLOCKED**. Do not restart Comfy to satisfy this.

## Intended replacement (current → frozen)

| Current | Conflict | Replacement |
|---|---|---|
| `resolutionToSize` 720p=1280×720 | Advertises illegal H3/LTX canvas | Legal-canvas module; UI shows 1280×704 for 720p class |
| `_snap_ltx_25_spatial` | Silent execute-time snap | Preflight fail + suggest |
| `snap_h3_length` / LTX 8n+1 pad | Silent duration mutation | Fail + suggest legal duration |
| `clamp_frames` in export | Silent shorten | Remove from execution |
| `resolve_render_plan` min() | Silent downsample | Advisory only |
| `apply_vram_profile` | Mutates project canvas | Telemetry / history only |
| `recommended_tier: 32` | 31.84 GB bucketed | Exact GB + viability |
| LTX 2.5 `multiFrame` Ready | Fake 3 Frame | Unsupported until proven |
| Certified `ltx.*` / `wan.*` | Retired weights still required | Retired / migration only |
| Ollama `gemma4:31b-it-qat` default | Stale factory | `qwen3.6:35b-a3b` + `qwen3.8:27b` fallback |
| Co-Director WAN-as-current | Stale teaching | H3/LTX 2.5 + distinct Seedance |

## Parallel work may begin

This file is the team-release gate for canvas / VRAM / duration / 3 Frame honesty.  
No new catalogs. Extend `legal_canvas`, `vram_viability`, `generator_authority`, `workflow_capabilities`.
