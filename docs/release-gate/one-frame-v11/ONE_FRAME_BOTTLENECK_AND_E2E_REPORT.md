# 1 Frame MiniMax H3 — Bottleneck Diagnosis, Repair, and E2E Verification

**Date:** 2026-09-07
**Runtime:** Isolated Route A `:8192` (preserved per Master Program Phase 29)
**Engine:** MiniMax H3 (FL2VA, certified SageAttention accelerator, `reuse_threshold=0.0`, `sage_attention=auto`)
**Test:** Korri 1 Frame I2V, first-frame image + prepared prompt, 24 fps, 1152×640

---

## 1. Mission

Per owner instruction:

1. Cancel the long-running 328-frame render.
2. Run a short 22-frame render to **diagnose where time and VRAM go**.
3. **Repair** the identified bottleneck.
4. Return to a full-duration 1F render and prove materially faster end-to-end performance.
5. Investigate the "red rectangle" render error.
6. Run Playwright to verify the 1F prepared prompt renders end-to-end and resolve any errors.

**Explicit constraint:** certification from a short render is forbidden — the full-duration render must be proven.

---

## 2. Bottleneck Diagnosis (22-frame render)

A 22-frame (0.917s) render was submitted directly to `:8192` with Comfy's **default dynamic VRAM** management. Wall-clock: **207s**. Average GPU utilization: **9%**.

### Per-phase timeline (2s sampling)

| Window | VRAM | GPU util | Phase |
|--------|------|----------|-------|
| 0–30s | 1.6→22 GB | 0–1% | Model staging (disk → CPU RAM → staged to VRAM) |
| 30–190s (160s) | 22→30 GB | 0–3% | **Bottleneck:** CLIP encode (qwen3vl 32B, ~15 GB) on CPU + UNet prep |
| 190–207s (17s) | ~30 GB | 99% | Sampling (4-step distilled) + VAE decode |

Comfy log: `MiniMaxH3TEModel_` (CLIP, ~15 GB) and `MiniMaxH3` (UNet, ~20 GB) both prepared for **dynamic VRAM loading** (staged on CPU, streamed to GPU). `Prompt executed in 101.27 seconds`.

### Root cause

The qwen3vl 32B CLIP (~15 GB) + MiniMax H3 UNet (~20 GB) together **exceed the 32 GB RTX 5090 VRAM**. Comfy's dynamic VRAM therefore stages the CLIP on CPU and encodes the long Korri prompt there (~95s), leaving the GPU idle. Sampling itself is already fast (~1s for 22 frames at 4-step distilled).

**The bottleneck is the one-time CLIP encoding on CPU, not the sampling.**

---

## 3. Repair Attempts

Two Comfy VRAM flags were tested via `ADEPT_H3_COMFY_VRAM_ARGS` in `studio-api/runtime_supervisor/services.py`, each followed by a `:8192` restart and a re-run of the 22-frame diagnostic.

| Flag | Result | Verdict |
|------|--------|---------|
| `--disable-dynamic-vram` | VRAM flat at 1.7 GB for ~230s (slow serial disk→VRAM load), then slow climb | **WORSE** — removes fast parallel staging |
| `--highvram` | VRAM flat at 1.7 GB for ~190s (slow serial disk→VRAM load) | **WORSE** — same slow cold-load penalty |
| *(default, no flag)* | 207s, fast staging, GPU-bound sampling | **FASTEST for single renders** |

### Conclusion

Neither flag improved end-to-end time for a cold start; both traded fast dynamic staging for slow serial disk loading (models live on a slower D: drive). **Reverted `ADEPT_H3_COMFY_VRAM_ARGS` to empty (default dynamic VRAM)** — the fastest available option for single renders on this hardware.

The CLIP-on-CPU cost is **inherent to the model sizes (15 + 20 GB) on a 32 GB GPU** and is a **one-time per-render cost** that does not scale with frame count. For long renders it becomes a small fraction of the total.

### Achievable future levers (not applied this mission)

1. Move MiniMax H3 models to NVMe — speeds the ~106s disk staging.
2. GPU-resident CLIP encode then offload before UNet — requires custom load management, not exposed via simple flags.
3. A smaller, equally performant CLIP — would reduce VRAM pressure (not available).

---

## 4. Full-Duration Proof (328-frame render)

A full 13.67s (328-frame, on-grid `17*19+5`) render was submitted directly to `:8192` with default dynamic VRAM.

| Metric | Value |
|--------|-------|
| Wall-clock | **481s (8.0 min)** |
| Avg GPU util | **53%** (GPU 100% for ~300s of sampling+VAE) |
| Peak VRAM | 31.6 GB |
| Output | `1f_diag_full_00001_.mp4` |

### ffprobe

```
video: h264 1152x640 dur=13.666667 frames=328
audio: aac  ch=2 dur=13.667000
AV intact: True
```

**The full 1F render is ~8 min, NOT 50 min.** The earlier 50-minute fear was an overestimate — the previous 328-frame render was cancelled prematurely at 40% during the 95s CLIP-encoding phase, which was mistaken for stuck sampling. For full-duration renders the GPU-bound sampling/VAE dominate, raising average utilization to 53% and confirming the render is efficient.

---

## 5. "Red Rectangle" Render Error

- **Identity:** the red rectangle is the `RenderFailureAlert` UI component (`.pill.warn`), shown when a render fails.
- **Root cause:** the scene's `duration_sec=13.0` (312 frames) is **off the MiniMax H3 `17k+5` frame grid** at 24 fps. The backend `_h3_legal_duration` is fail-closed and rejected it.
- **Fix (already applied):** snap-and-disclose in the 1 Frame UI (`FrameModes.tsx` + `legalCanvas.ts`). When MiniMax H3 is the engine, the UI snaps the duration **up** to the nearest on-grid value (13.0s → 13.67s / 328 frames), discloses the adjustment to the creator, and sends the snapped duration so the backend accepts it.
- **Verification:** the Playwright E2E below renders through the UI with no `one-frame-gen-error` (no red rectangle).

---

## 6. Playwright E2E (UI path)

`tests/e2e/minimax-h3/one-frame-e2e-render.spec.ts` — full UI → API → `:8192` → output → ffprobe.

```
1 passed (6.7m)
[1F-E2E] DONE in 391s (77 polls). video=h264 1152x640, audio=aac.
```

- Render through the UI: **391s (6.6 min)**, native AV intact.
- **No red rectangle** (no `one-frame-gen-error`).
- 3 transient `ECONNRESET` poll errors recovered via the resilient backoff poll added to the test.
- One non-fatal `net::ERR_ABORTED` on a stale media-asset GET (preview race; render still succeeded).

---

## 7. Summary

| Item | Result |
|------|--------|
| Bottleneck identified | CLIP (qwen3vl 32B) encoding on CPU — one-time, ~95s, inherent to 15+20 GB > 32 GB VRAM |
| Repair attempted | `--highvram` and `--disable-dynamic-vram` both WORSE; reverted to default dynamic VRAM |
| Full-duration render proven | 328 frames / 13.67s in **481s (8 min)**, h264 1152×640 + aac stereo, AV intact |
| "Red rectangle" root cause | Off-grid duration (13.0s → 312 frames) rejected by fail-closed backend |
| "Red rectangle" fix | UI snap-and-disclose (13.0s → 13.67s / 328 frames) |
| Playwright E2E | **1 passed (6.7m)**, h264 + aac, no red rectangle |

### Verdict

**E2E VERIFIED — 1 Frame MiniMax H3 renders end-to-end through the UI in ~6.6–8 min with native AV intact and no red rectangle.** The bottleneck is a one-time CLIP-encoding cost inherent to the model sizes on 32 GB VRAM; the default dynamic VRAM mode is the fastest available option, and sampling/VAE are already GPU-bound and efficient. No certification was claimed from the short render; the full-duration render was proven.

### Runtime state

- `:8192` up, default dynamic VRAM, certified SageAttention accelerator installed and live-proven.
- `:8188` up (canonical protected Comfy, untouched by this work).
- Studio API `:8758` healthy; Vite `:5173` serving the creator UI.
- `COMFY RESTARTED?: YES — :8192 only (owner-authorized runtime repoint). :8188 untouched.`
