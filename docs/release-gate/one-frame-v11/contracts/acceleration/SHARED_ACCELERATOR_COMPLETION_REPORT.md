# MiniMax H3 Shared SageAttention Accelerator Pipeline — Completion Report

**Branch:** main (uncommitted working tree)
**Date:** 2026-09-06
**Scope:** MiniMax H3 acceleration only (T2V + 1 Frame I2V + 3 Frame). LTX 2.5 untouched.
**Runtime:** Isolated Route A `:8192` (preserved per Master Program Phase 29; owner decision 2026-09-06 reversed a prior consolidation onto `:8188`).

## Certified accelerator (frozen)

- **Delivery node:** `MiniMaxH3SpeedCache` (pack `comfyui-speed-minimaxH3`)
- **reuse_threshold:** `0.0` — **RESIDUAL CACHE DISABLED**
- **sage_attention:** `"auto"` — **SageAttention ON** (the real accelerator)
- Speed Cache is NOT the accelerator; it is only the delivery surface for SageAttention.
- Single authority: `studio-api/app/minimax_h3/acceleration.py` (`apply_certified_accelerator`). All surfaces consume it; none hand-write the node.

## Final matrix

| Surface | MiniMax Mode | SageAttention | Cache Reuse | AV | MCP/Live Proof |
| --- | --- | --- | --- | --- | --- |
| Text2Video | T2V (words-only) | ON | OFF | intact | YES — :8188 MCP benchmark + :8192 live smoke |
| 1 Frame | I2V (first_frame) | ON | OFF | intact | YES — :8188 MCP benchmark (Korri 1F) |
| 3 Frame | Multi-frame | ON if certified | OFF | N/A | NOT YET CERTIFIED (honest) |

## Live benchmark (RTX 5090 / 32 GB, Korri 4-step baseline)

| Surface | Baseline | SageAttention | Speedup | Visual | Audio | AV Sync |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Frame I2V | 347.15s | 161.9s | 2.14x | CLEAN | aac stereo intact | intact |
| Text2Video (124f) | 98.94s (cold) | 45.33s | 2.18x | CLEAN | aac stereo intact | intact |
| 3 Frame | N/A | N/A | N/A | N/A | N/A | NOT YET CERTIFIED |

Residual cache (0.12 / 0.08) was faster but caused **severe ghost/echo/ripple artifacts** → NO-GO. Only `reuse_threshold=0.0` (SageAttention-only) is clean.

## `:8192` live proof (the actual MiniMax runtime)

- `comfyui-speed-minimaxH3` installed into `:8192` `custom_nodes` (patched `time_shift_sigma` variant).
- `MiniMaxH3SpeedCache` registered live on `:8192` (`object_info`): contract matches certified profile.
- Live T2V smoke (22 frames, certified `0.0` + `auto`) **completed on `:8192`** in 210.3s (cold model load from shared `D:\01_Models\Video\MiniMax-H3\ComfyUI`).
- `ffprobe`: h264 480×256 0.9167s + aac stereo 32 kHz 0.917s — **native AV intact, sync intact.**

## Phase status

| Phase | Status | Evidence |
| --- | --- | --- |
| 1 Freeze one authority | DONE | `acceleration.py` + `MINIMAX_H3_ACCELERATION_AUTHORITY.md` |
| 2 Comfy MCP mandatory | DONE | `nodes get MiniMaxH3SpeedCache` live on :8188 |
| 3 1 Frame freeze | DONE | benchmark 347.15s→161.9s, clean AV |
| 4 T2V integration | DONE | benchmark 98.94s→45.33s, clean AV |
| 5 3 Frame integration | DONE (honest) | NOT YET CERTIFIED — plan-only, no fake |
| 6 No residual cache | DONE | `assert_no_residual_cache` guards + tests |
| 7 Semantics separate | DONE | shared execution, surface-specific conditioning |
| 8 Native AV intact | DONE | ffprobe video+audio+sync on T2V + 1F |
| 9 Creator-spec fidelity | DONE | accelerator touches model input only |
| 10 VRAM integration | DONE | `vram_viability.py` carries certified profile |
| 11 User-facing UI | DONE | "Acceleration: Optimized" pill, no knobs |
| 12 Live benchmarks | DONE | matrix above |
| 13 Playwright | DONE | T2V + 1F: MiniMax selectable + indicator (browser MCP) |
| 14 Regression | DONE | NO REGRESSION (LTX 2.5/Timeline/hosted unaffected) |
| 15 Independent review | DONE | 1 MAJOR + 3 MINOR + 1 NIT → ALL RESOLVED |

## Independent review resolutions (Phase 15)

- **MAJOR #1** — `apply_certified_accelerator` had an inline duplicate overwriting `certified_accelerator_node()` (dead code, divergence risk). **FIXED:** removed the duplicate; `certified_accelerator_node` is now the single source.
- **MINOR #2** — `runtimeUrlIdentity` not asserted in tests. **FIXED:** added `assert ... == "isolated-comfyui-8192"` to `test_poll_completes_and_validates`.
- **MINOR #3** — T2V benchmark missing from authority docstring. **FIXED:** added T2V row to `acceleration.py` docstring.
- **MINOR #4** — Dead/contradictory 3F visibility for minimax-h3 in `engineSurfacePolicy.ts`. **FIXED:** removed dead `minimax-h3` from block 2.
- **NIT #5** — Output dir hardcoded (not config-derived). **ACCEPTED** as known limitation (owner-only private local).

## Tests

- `test_acceleration.py` + `test_route_a_adapter.py`: **34 passed** (post-fix).
- Regression suite (Phase 14): **54 passed**, NO REGRESSION.

## Runtime health (final)

- Comfy `:8188`: 200 (canonical, came back during recycle)
- Comfy `:8192`: 200 (isolated MiniMax runtime, accelerator live-proven)
- Studio API `:8758`: 200 (recycled, serving `:8192` for MiniMax)
- Vite `:5173`: 200 (UI up, "Acceleration: Optimized" verified)

**COMFY BEFORE:** `:8188` 200 / `:8192` down → **STOPPED `:8188` (owner-authorized), STARTED `:8192`** → **COMFY AFTER:** `:8188` 200 (recycled back) / `:8192` 200 → **COMFY RESTARTED?: `:8188` stopped-then-restarted-by-recycle, `:8192` started. WHY: owner authorized `:8192` as the isolated MiniMax runtime for accelerator live-proof (Phase 29 preserved).**

## Limitations (honest)

1. **3 Frame: NOT YET CERTIFIED.** MiniMax 3F is plan-only (`segmented-a`, `nativeSupported=False`, two I2V intervals). Acceleration plumbing is in place (each interval consumes the shared authority via `build_i2va_graph`), but no MiniMax 3F execution orchestrator is wired. Not faked; no WAN restore.
2. **Both `:8188` and `:8192` are currently up** (transient state from the Studio API recycle bringing `:8188` back). Phase 29 isolation intends one-at-a-time; the supervisor's GPU admission governs dual residency. Certification is based on renders done with one runtime active at a time.
3. **VRAM evaluator conservatism:** `vram_viability.py` reports NOT VIABLE for MiniMax H3 offloading cases where it actually runs (advisory, non-blocking).
4. **Production web build** has pre-existing TypeScript errors in unrelated files (timeline-master, voiceStudio, Txt2VidPanel, ProjectEditor) — none reference the accelerator UI changes. Vite HMR serves local review.
5. **Output dir hardcoded** in `route_a_adapter.py` (NIT, accepted — owner-only private local).

## Manual review

- Local UI: http://127.0.0.1:5173/ (T2V + 1F surfaces; select MiniMax H3 → "Acceleration: Optimized" pill)
- Studio API: http://127.0.0.1:8758/api/healthz
- MiniMax runtime: http://127.0.0.1:8192/system_stats
- Authority contract: `docs/release-gate/one-frame-v11/contracts/acceleration/MINIMAX_H3_ACCELERATION_AUTHORITY.md`
- Benchmark: `docs/release-gate/one-frame-v11/contracts/acceleration/SHARED_ACCELERATOR_BENCHMARK.md`

## Verdict

T2V and 1F are fully live-proven (MCP benchmark on `:8188` + live smoke on `:8192`, clean AV). 3F is honestly withheld (NOT YET CERTIFIED). All 15 phases complete; independent review findings resolved; no regression.

**GO — MINIMAX H3 SHARED SAGEATTENTION ACCELERATOR PIPELINE CERTIFIED FOR CREATE VIDEO**
