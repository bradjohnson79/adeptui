# Adept v1.1 Convergence Journey — Primary Status

**Date:** 2026-09-05  
**Branch:** `feat/character-creator-final-closure`  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Surfaces:** Vite `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Freeze:** `00_FREEZE.md` + `01_CANVAS_VRAM_FIDELITY_FREEZE.md`

This file is the journey status after primary integration of remaining review findings. It does not replace the freeze.

## COMFY

- **COMFY BEFORE:** PID **69108**, `:8188` healthy, RTX 5090, 31.84 GB
- **COMFY AFTER:** PID **69108**, healthy
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Ordinary API recycle + UI walk. Control-plane `POST /restart-api` only. Comfy PID unchanged.
- Comfy MCP: still no Cursor namespace. Workflow-graph certification remains blocked.

Studio API recycle via `scripts/restart_studio_api_only.py` can false-fail when control `/status` exceeds 2s. Direct `POST /restart-api` succeeded in spawning a new API PID; healthz was OK after a short wait. Comfy was not touched.

## Verdict

**NO-GO — ADEPT v1.1 CONVERGENCE INCOMPLETE**

and

**E2E BLOCKED — COMFY MCP REQUIRED FOR VIDEO WORKFLOW CERTIFICATION**

Do not issue GO. Silent mutators on the named LTX/H3 execution paths were removed, but Journey 18 live preview, Journey 20 Comfy MCP graph cert, and a full Playwright generation walk are not live-proven.

## What is now live-true

- `/api/engines` is the CREATE join: auto, minimax-h3, ltx-2.5, seedance-2.0, seedance-2.5, fal_kling, fal_veo, fal_runway. No retired local Ready rows. No generic `seedance-fal` product row.
- LTX 2.5 execution identity is `ltx-2.5-distilled`, not `ltx-local`.
- 720p class is **1280×704**. 1280×720 is rejected before Comfy.
- Native 4K is unavailable for H3 / LTX 2.5. No upscale-as-4K label.
- `/api/gpu/stats` reports exact **31.84 GB** and `recommended_tier: null`.
- Viability ladder is advisory and `mutatesRequest: false`.
- 3 Frame local engines are honestly unready. Ordinary I2V is not treated as 3 Frame.
- Wave6 required locals no longer include retired `ltx.simple_i2v` / `wan.*`. Wave6 does not determine CREATE eligibility.
- Co-Director generator knowledge maps LTX 2.5 IDs to profile `ltx-2.5`, not `ltx-local`.
- LTX EasyCache is Fast-only. Quality does not insert EasyCache.
- Hosted duration snap (`nearest_duration`) fail-closes.
- `clamp_frames` remains a no-op. Queue-worker LTX 8n+1 pad is gone.

## Primary live walk (Korri, Vite)

Text to Video:

- MiniMax H3 and LTX 2.5 selectable after Timeline join hydration.
- Tiers: 480p 832×480, 720p 1280×704, 1080p 1920×1088, Native 2K, 4K disabled.
- GPU panel: RTX 5090 · 29.21 GB free / 31.84 GB total.
- Ladder: 480p Viable · 720p Viable · 1080p Viable with model unload · 2K Not viable · 4K Not viable (honest native-4K denial).
- Generate enables only with a prompt. 5.0s @ 24 fps on LTX 2.5 is illegal; UI now blocks that duration instead of padding.

1 Frame:

- Exactly one First Frame control.
- MiniMax H3 and LTX 2.5 selectable. No WAN / LTX 2.3.
- Preview monitor still shows the earlier 1280×720 H3 tensor refusal (honest, no silent snap).

3 Frame:

- First / Middle / Last present.
- Generate disabled.
- H3 and LTX 2.5 disabled: “ordinary Image-to-Video is not enough.”

Timeline:

- MiniMax H3 Reference-to-Video dock. No CREATE T2V leakage observed.

## E2E TRACE

| Stage | Result | Evidence |
|---|---|---|
| User action | PASS | Korri T2V / 1F / 3F / Timeline walk |
| Frontend | PASS with gaps | Join pickers + legal tiers + viability. Duration block added for LTX. Live preview not proven. |
| API | PASS | `/api/engines`, legal-canvas, viability, gpu/stats |
| Backend | PASS | Fail-closed canvas/duration on local LTX/H3 builders |
| Workflow | E2E BLOCKED | Comfy MCP unavailable |
| Runtime | N/A this walk | No new GPU generation queued |
| Result | N/A | No new asset this walk |
| Persistence | N/A | No new save this walk |
| Reload | PASS | Surfaces reloaded on Korri |
| Downstream | N/A | Timeline isolation observed; no new handoff |

## Remaining blockers (do not hide)

1. Comfy MCP not attached → workflow-level cert **E2E BLOCKED**.
2. Live low-res preview (same job → preview bus → monitor → final MP4) not proven on a live generation.
3. Frontend still hydrates CREATE pickers from Timeline join; first paint can show “Requires setup” until that join arrives.
4. Generic `fal.seedance` certified leaf and leftover `ALL_ENGINES` / `EngineName` retired tokens remain for migration/read. They must not regain CREATE authority.
5. 1 Frame hosted Seedance rows currently say “Unsupported in this workflow” (local I2V is the live path).
6. No full Playwright generation job this walk.
7. AV-stream invariant and accelerator benchmarks were not re-run live.

## Tests measured this continuation

- `studio-api`: 120 + 106 = **226 passed** on the fidelity / knowledge / Seedance / certified / cinematographer / H3 adapter set.
- `studio-web`: legalCanvas + engineSurfacePolicy **14 passed** before the duration-message test; duration test added after the walk.
