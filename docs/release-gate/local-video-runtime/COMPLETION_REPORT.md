# Local Video Runtime + Generator Availability — Final Closure Report

> **SUPERSEDED (2026-09-05)** for “no local T2V / LTX 2.3 is the live LTX path” and generic hosted Seedance. Current authority: `docs/release-gate/video-engine-authority/00_FREEZE.md` and `docs/release-gate/video-engine-authority/COMPLETION_REPORT.md`. This report remains historical evidence for the Sept 4 MCP walk only.

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455` (working tree dirty; this closure is not a commit unless requested)  
**Date:** 2026-09-04  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Surfaces:** `http://127.0.0.1:5173/` (Vite) · `http://127.0.0.1:8758/` (Studio API)

## Verdict

**GO — ADEPT UI LOCAL VIDEO RUNTIME + GENERATOR AVAILABILITY E2E CERTIFIED**

Required v1.1 local video generators are live-proven and MCP-verified. Hunyuan remains installed but uncertified and is **not** a v1.1 requirement. No local true T2V model is installed; Text to Video stays hosted Seedance. That is product truth, not a Runtime Fabric defect.

## Closures

### Closure 1 — Comfy MCP — PASS

Cursor has no Comfy MCP namespace. Canonical attach is stdio `data\venvs\mcp\Scripts\comfy-mcp.exe` pointed at `http://127.0.0.1:8188`. Lifecycle tools exist (`launch_comfyui` / `stop_comfyui` / `restart_comfyui`) and were **not** called.

Live MCP: 39 tools, GPU RTX 5090, Comfy 0.32.0, torch `2.10.0+cu130`. Adept-built graphs validated against live `object_info`:

| Graph | Valid | Errors | Notes |
|---|---|---|---|
| LTX 2.3 | Yes | 0 | `LTXVImgToVideo` / `LTXVConditioning` / `LTXAVTextEncoderLoader` |
| WAN 2.2 FLF | Yes | 0 | `WanFirstLastFrameToVideo` + dual 14B + umt5 + Wan VAE |
| MiniMax H3 Ref2V | Yes | 0 | 1 warning: unused LoadImage leftover, not a fail |

Evidence: `docs/release-gate/local-video-runtime/evidence/COMFY_MCP_CLOSURE.json`, `COMFY_MCP_SUMMARY.json`.

### Closure 2 — WAN First/Last Frame live — PASS

Creator surface: Timeline **Generate only the selected Batch** (not Text to Video, not 1 Frame).

| Field | Value |
|---|---|
| Start | `b98585a0-8829-48cc-8c7b-63b9687955bb` Venture Corridor scene |
| End | `4d48b0b0-1f9a-422e-8227-34d60567d33d` Korri Front |
| Workflow | `wan.first_last_frame` → `build_wan_flf_workflow` |
| Job | `6927e969-205f-4afd-955a-ed8a50fc2009` |
| Comfy prompt | `f0c3623f-481c-42ad-8206-88c46015a95c` |
| Time | 48.8 s |
| Output | `scene_0_309732f5_aud.mp4` H264 832×480 33 frames 24 fps 1.375 s + AAC |
| Library | `a3f21fde-8cb1-4667-9982-2fa79d6749f8` |
| Reload | Asset still on `GET /api/projects/{pid}` |
| Route A | No |

### Closure 3 — MiniMax H3 Ref2V on canonical Comfy — PASS

Creator surface: Timeline Batch 3 Generate. Engine `minimax-h3`, adapter `minimax-h3-t2v-local`, mechanism `h3_ref2va`. **Not Route A.**

| Field | Value |
|---|---|
| Job | `94ed6d6d-4475-48ce-b725-f197b9cd9d03` |
| Comfy prompt | `4aac5bd1-6c43-47b5-b639-59306be1a215` |
| Nodes | `MiniMaxH3ReferenceToVideo`, UNET `minimax_h3_ref2va_pruned_int8_convrot`, CLIP `qwen3vl_32b_minimax_h3_nvfp4_awq` type=minimax, dual VAE, EasyCache, SaveVideo `h3_ref2v` |
| Time | 32.9 s |
| Output | `scene_0_8841dc6e.mp4` H264 768×448 124 frames 24 fps 5.167 s + AAC |
| Library | `bd8102f3-e9de-4781-acec-59c3c9b56dd9` tag `minimax-h3-draft` |
| Port | `:8188` |

### Closure 4 — Route A on-demand — PASS (prepare / readiness)

Contract proven: **prepare-on-Generate**, not an idle watchdog.

The NETSTAT.EXE `0xc0000142` dialog on this host was a real blocker. Supervisor port lookup used `netstat -ano`, which crashed and popped a modal. Route A spawn also used `DETACHED_PROCESS`, which Adept already forbids on canonical Comfy (Intel Fortran window-CLOSE abort). First prepare wrote a PID, then the child died (`stale PID`).

Bounded repairs (no architecture redesign):

- Windows port owner uses IP Helper (`GetExtendedTcpTable`). **NETSTAT.EXE is not spawned.**
- Route A / supervisor `_spawn` matches headless Comfy: `CREATE_NO_WINDOW` only.
- Product Generate (`_ensure_route_a_for_generation` → `_start_route_a_sync`) runs current `start_route_a_on_demand` against the live supervisor state store. The long-lived control-plane process cannot be recycled without risking Comfy (PID 69108 is in that process tree).

Live proof:

| Step | Result |
|---|---|
| Before | Route A down. HTTP readiness `onDemand=true`, creator copy “Available on demand — Adept will start Video Runtime when you Generate.” Comfy PID **69108**. VRAM ~1495 MiB after prior `/free` handoff (handoff from the first attempt dropped ~31 GB → ~1.5 GB; Comfy stayed HTTP 200). |
| First prepare | 50.4 s. `:8192` up, PID 17252, HTTP 200, Comfy 0.30.0 (isolated from `:8188` 0.32.0). Readiness **Ready for Private Local Use**. Comfy PID unchanged. VRAM 1892 MiB — no dual-model residency. |
| Stop | `:8192` down. Readiness returns to ON_DEMAND. |
| Second prepare | 16.5 s. `:8192` up again, PID 46192. Ready. |
| Reconcile stop | `:8192` down. ON_DEMAND. Comfy 69108 still healthy. |

No manual start. No visible console. No idle self-heal requirement. Repeatable after stop.

Evidence: `docs/release-gate/local-video-runtime/evidence/ROUTE_A_ONDEMAND.json`.

### Closure 5 — Hunyuan — INSTALLED — TESTING / UNCERTIFIED

Hunyuan 1.5 and 13B weights are present. Product catalog: `readiness=Testing`, `executable=False`. Not a v1.1 required generator. Left on the post-v1.1 / optional-generator queue. **Does not block GO.**

### Closure 6 — Local T2V truth

No local true T2V model is installed. Text to Video shows Auto Select, Seedance Ready, and honest Kling/Veo/Runway Testing/setup. LTX, WAN, H3, and Hunyuan are hidden. Generate stays disabled until a prompt. Hosted Seedance is the v1.1 T2V path. Not a Runtime Fabric defect.

### Closure 7 — Regression — PASS

| Surface | Result |
|---|---|
| Text to Video | Browser: only genuine T2V options. Playwright 1/4 passed. |
| 1 Frame | LTX + MiniMax enabled. WAN disabled with “First and last frame required.” Hunyuan Testing. Generate present. |
| 3 Frame | WAN 2.2 First/Last Frame **enabled**. Hunyuan Testing disabled. Generate from 3 frames present. |
| Timeline | LTX 2.3 Ready selected. WAN / H3 Ready in the dropdown. No “No local engines ready” collapse on this walk. Library + References intact. |
| Co-Director | Availability reply lists Ready vs Testing vs FLF/Ref2V/I2V. WAN T2V is a **mode** limit (regex also accepts “Why can WAN not…”). |
| Library | LTX `6f8de1f5-…`, WAN `a3f21fde-…`, H3 `bd8102f3-…` still on the Korri project. |
| Runtime Supervisor | Studio API recycled only (`20552 → 22512 → 62896`). Comfy PID **69108** unchanged. Route A down after reconcile. |

Tests this closure:

- Backend `test_local_video_availability.py` — **11 passed**
- Backend `test_port_owner_uses_ip_helper_not_netstat_exe` — **passed** (bind + IP Helper, no netstat)
- Frontend `engineSurfacePolicy.test.ts` — **5 passed**
- Playwright `local-video-availability.spec.ts` — **4 passed**

### Closure 8 — Final matrix

| Generator | Mode | Installed | Runtime | Live Proof | MCP | Verdict |
|---|---|---|---|---|---|---|
| LTX 2.3 `ltx-local` | I2V / R2V · not T2V | Yes `ltx-2.3-22b-distilled-fp8` | Comfy `:8188` Ready | Yes — job `d310dd70` + Library `6f8de1f5` | Valid | **GO — MODE-SPECIFIC** |
| LTX 2.5 distilled | I2V / R2V · not T2V | Yes | Comfy `:8188` Ready | Not this pass | Same family | **GO — ON DEMAND** |
| LTX 2.5 full | I2V | Partial | Testing | No | Not evaluated | **TESTING / UNCERTIFIED** |
| LTX 2.5 Comfy INT8 | I2V | Distilled files | Testing | No | Not evaluated | **TESTING / UNCERTIFIED** |
| WAN 2.2 `wan-local` | First/last frame only | Yes dual 14B + umt5 + Wan VAE | Comfy `:8188` Ready | Yes — job `6927e969` + Library `a3f21fde` | Valid | **GO — MODE-SPECIFIC** |
| MiniMax H3 Ref2V | Reference-to-Video | Yes `minimax_h3_ref2va` | Comfy `:8188` Ready | Yes — job `94ed6d6d` + Library `bd8102f3` | Valid (1 unused-node warning) | **GO — MODE-SPECIFIC** |
| MiniMax H3 I2V row | Still Ref2V | Same weights | Comfy `:8188` Ready | Same adapter family | Same | Product identity stale · not Route A |
| MiniMax Route A | Isolated experimental T2V/I2V on `:8192` | Yes FL2VA + CLIP + VAEs | `runtime.video` ON_DEMAND | Yes — down → prepare → Ready → stop → prepare → stop | Isolated 0.30.0 stack; not `:8188` MCP | **GO — ON DEMAND** |
| Hunyuan 1.5 | I2V/R2V · not T2V | Yes | Testing · not executable | No — not required | Not evaluated | **INSTALLED — TESTING / UNCERTIFIED** |
| Hunyuan 13B | Product I2V/R2V | Yes T2V-720p weights | Testing · not executable | No — not required | Not evaluated | **INSTALLED — TESTING / UNCERTIFIED** |
| Seedance fal | True T2V | Hosted | Ready | Prior hosted path; not re-run (paid) | N/A | **GO — HOSTED T2V** |
| Kling / Veo / Runway | Claimed T2V | Hosted | Testing / setup | No | N/A | **TESTING / REQUIRES SETUP** |
| `optional-wan` leftover | none | No | Unsupported | n/a | n/A | **UNSUPPORTED** |

Nothing UNKNOWN.

## E2E TRACE (required locals)

| Stage | LTX | WAN FLF | H3 Ref2V | Route A |
|---|---|---|---|---|
| User action | 1 Frame Generate | Timeline selected-batch Generate | Timeline Batch 3 Generate | Generate / prepare-on-demand |
| Frontend | PASS | PASS | PASS | PASS (ON_DEMAND copy) |
| API | PASS `engine=ltx` | PASS `wan-local` | PASS `minimax-h3` | PASS `_ensure_route_a_for_generation` |
| Backend | `ltx.scene` | `wan.first_last_frame` | `h3_ref2va` | `start_route_a_on_demand` + `/free` handoff |
| Persistence | Library `6f8de1f5` | Library `a3f21fde` | Library `bd8102f3` | State ON_DEMAND ↔ Ready |
| Runtime | `:8188` PID 69108 | `:8188` PID 69108 | `:8188` PID 69108 | `:8192` start/stop; `:8188` survives |
| Result | Valid MP4 | Valid MP4 | Valid MP4 | Readiness Ready (allowed proof) |
| Reload | PASS | PASS | PASS | Repeatable after stop |
| Downstream | Timeline Ready | Not T2V / not 1 Frame | Honest Comfy lineage | No dual-residency corruption |

## Runtime observe

```
COMFY BEFORE: PID 69108 / HTTP 200 ready
COMFY AFTER:  PID 69108 / HTTP 200 ready
COMFY RESTARTED?: NO
WHY?: Ordinary API recycles only (52696 → 20552 → 22512 → 62896). Supervisor POST /restart-api. Comfy was never stopped, adopted, or respawned. Route A /free is model unload, not kill.
```

## Non-blocking leftovers

1. Timeline MiniMax row can show `capabilityLabel=Requires Setup` while `readiness=Ready` and `executable=True`. Catalog copy is stale; execution path is proven.
2. Long-lived control-plane process still contains the old netstat/DETACHED_PROCESS code in memory. Product Generate uses current in-process supervisor services. A future supervisor start (not this session) will load the disk fix. Do not recycle the supervisor while Comfy 69108 is its descendant.
3. Hunyuan stays Testing / uncertified by design.
4. No local true T2V model — hosted Seedance for v1.1.
5. H3 MCP graph warning: unused LoadImage node.

## Manual review

1. Open Korri Anadriya → **Text to Video**. Confirm only Seedance (and honest hosted Testing rows).
2. **1 Frame** → LTX Ready, WAN disabled with first/last copy, Hunyuan Testing.
3. **3 Frame** → WAN First/Last Frame enabled.
4. **Timeline** → LTX 2.3 Ready; Library videos `6f8de1f5`, `a3f21fde`, `bd8102f3`.
5. Co-Director: “Which local video generators are available right now?”
6. Do not start Route A or restart Comfy for this review unless you intend another on-demand prepare.

## Final vote

**GO — ADEPT UI LOCAL VIDEO RUNTIME + GENERATOR AVAILABILITY E2E CERTIFIED**
