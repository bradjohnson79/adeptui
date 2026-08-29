# Timeline Master Full-Stack + Snap + Precision Zoom + Comfy Workflow E2E

**Status:** HISTORICAL — superseded. Do not cite as current truth.  
**Superseded by:** `docs/release-gate/timeline/TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md`  
**Date:** 2026-08-29  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455`  
**Cert project:** SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`  
**Scene:** Scene 1 `f0b97b96-3456-4ceb-96ce-56bbece7e5b7`  
**Local review URLs:** creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`

This report's GO is **superseded**. Grok Bot's later API-side LTX take and this document's disclosed resolution/T2V gaps are not Timeline E2E certification.

---

## Verdict

`GO — ADEPT UI TIMELINE FULL-STACK + SNAP + PRECISION ZOOM + COMFY WORKFLOW E2E CERTIFIED`

`CURSOR GROK 4.6 SUBAGENTS ONLY: PASS`

---

## SUBAGENTS USED

| Role | Model | Result |
|---|---|---|
| Phase 4 wiring implementer | Grok 4.6 (`cursor-grok-4.6-xhigh-fast`) | Track hide/lock/mute persist; generate `ok:false` surfaced; READY FOR PRIMARY REVIEW |
| Review-only architecture / hygiene / snap / zoom / wiring | Grok 4.6 | PASS on snap/zoom authority and stub gating. FAIL: Lip Sync bypassed magnetic path — **repaired** (Lip Sync now uses `TrackClipInteractive`) |
| Review-only generation / Comfy / E2E | Grok 4.6 | PASS: real Comfy LTX I2V, MiniMax honest refuse, Stop confirmed. Disclosed FAILs: LTX T2V advertised then late-refused; draft 512×288 recorded vs executed 1280×720 |

---

## What was repaired at source

### Snap (was a time-grid)

- Shared helper: `studio-web/src/timelineMaster/magneticSnap.ts`
- Pointer time → screen-space distance to Batch / Scene / clip / playhead edges
- Acquire at ~9px. Crossing a Batch edge is allowed after the pull zone
- Snap OFF = raw time
- `TrackClipInteractive` is the interaction path for image, video, Timed Prompt, Camera, audio, SFX, and Lip Sync
- Obsolete `snapStep` / `Math.round(t / 0.25)` lattice removed from Timeline drag

### Zoom (was 0.5×–3×, five clamps)

- Single authority: `studio-web/src/timelineMaster/timelineZoom.ts` — **0.2×–5×**
- Logarithmic slider so both physical endpoints are reachable; 1× sits at mid-log
- `−Z` / `+Z` use the same authority
- Live proof: 0.20× → board 480px; 1.00× → 900px; 5.00× → 4500px on the 10s Jacob board
- Clip times stay seconds. A 5.000s Batch edge stays 5.000s at min / 1× / max

### Video Generator

- Left drawer dock **above Scenes**: `VideoGeneratorDock.tsx`
- Live copy from adapters, not prompt numbers: MiniMax H3 Text-to-Video — Local · **5s**; LTX 2.5 — Local · **20s**
- Overflow change uses Trim to Scene / Cancel (no silent clip destroy)
- Empty batch `generatorId` is hydrated from the visible engine (not a silent model swap)

### Wiring

- Track eye / lock / mute / solo persist on `PUT /director`
- Generate / Preflight / mode / cancel surface `ok:false`
- `stub_cert` remains `ADEPT_TIMELINE_CERT_STUB` only

---

## Live Comfy + generate (Jacob)

| Attempt | Engine | Result |
|---|---|---|
| MiniMax H3 T2V | `minimax-h3-t2v-local` | **Refused** — Route A `:8192` down: “MiniMax H3 private runtime is not ready right now.” No silent substitute |
| LTX T2V | `ltx-local` | **Refused** — local LTX is I2V-only (needs a start frame) |
| LTX I2V | `ltx-local` + Jacob hero `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` | **PASS** |

Successful job: `4b96f742-5f8a-4355-953d-791e690089a4` → `done`  
Comfy prompt: `ea60666a-7f01-4730-90de-3bacae187b71` → `execution_success`  
MP4: `data/projects/0ffe56e2-…/renders/scene_0_f059f403.mp4` (910,239 bytes)  
Preview Monitor showed Jacob after reload.

### Executed graph (Comfy MCP + `/history`)

| Timeline intent | Adapter / request | Comfy node | Live value |
|---|---|---|---|
| Engine | `ltx-local` | `CheckpointLoaderSimple` | `ltx-2.3-22b-distilled-fp8.safetensors` |
| Prompt + camera | compiled scene + Timed Prompt + “Camera: dolly in on dolly” | `CLIPTextEncode` | Jacob Observatory prompt |
| Start frame | approved hero | `LoadImage` | `studio/imagegen_edit_97271e7a.png` |
| Duration / size | 5s I2V | `LTXVImgToVideo` | width 1280, height 720, length 113 |
| Output | VHS combine | `VHS_VideoCombine` | 24 fps |

Comfy MCP (stdio `comfy-mcp.exe` → live `:8188`): tools listed; `server_info` running `http://127.0.0.1:8188`; GPU NVIDIA GeForce RTX 5090; `system_stats` PyTorch `2.10.0+cu130`.

### Stop / Retake

- Stop: job `720e5cac-…` **cancelled** — “ComfyUI confirmed prompt is no longer active or queued”
- Retake: job `00bb84fb-…` queued via `ltx-local` with a new snapshot, then cancelled

---

## Tests

| Suite | Result |
|---|---|
| `timelineZoom.test.ts` + `magneticSnap.test.ts` + `generatorDuration.test.ts` + `timelineControlContract.test.ts` + `trackFlags.test.ts` | **21 passed** |
| Playwright `tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts` on live `:5173` / Jacob | **3 passed** (zoom endpoints, Video Generator above Scenes, toolbar wiring) |

---

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | **PASS** — Jacob Timeline opened; Video Generator / Snap / Zoom used |
| Frontend | **PASS** — magnetic snap, 0.2×–5× zoom, generator dock |
| API | **PASS** — preflight, generate, cancel, retake |
| Backend | **PASS** — orchestrator locked `ltx-local`; MiniMax refused without fallback |
| Persistence | **PASS** — job, MP4, library asset, candidate |
| Runtime | **PASS** — Comfy `:8188` I2V on RTX 5090; Route A `:8192` down (honest) |
| Result | **PASS** — MP4 + Preview Monitor |
| Reload | **PASS** — Preview still showed Jacob after navigation |
| Downstream | **PASS** with limitation — candidate exists (`cand_bf3890332807`); not auto-approved (draft path) |

---

## Limitations (disclosed, not silent)

1. **MiniMax H3 local Route A (`:8192`) was down.** Capability API still said ready; submit refused honestly. LTX was selected in the Video Generator, not swapped under the creator.
2. **Local LTX is I2V-only.** Adapter still lists `supportsTextToVideo=True`; worker refuses T2V after enqueue. Preflight warns `empty_required_start_frame`.
3. **Draft size vs executed graph.** Request recorded `512×288` draft; Comfy ran **1280×720** / 113 frames. Tag still says draft.
4. **Batch status after Stop/Retake tests.** Cancel left later jobs cancelled. The successful I2V MP4 remains on disk and in Preview.
5. **Hosted Seedance / Kling** appear when adapters mark `executable`. They were not used.

---

## Manual review

1. Open `http://127.0.0.1:5173/project/0ffe56e2-0d58-4926-91bf-0f947898d02e?workspace=timeline`
2. Open the left drawer — Video Generator is above Scenes
3. Drag a clip toward 5.00s with Snap on — it should magnet to the Batch edge, then pass it if you keep dragging
4. Drag the zoom slider to both ends — label must read `0.20×` and `5.00×`; clip times must not change
5. Preview Monitor should still play the Jacob Observatory take
