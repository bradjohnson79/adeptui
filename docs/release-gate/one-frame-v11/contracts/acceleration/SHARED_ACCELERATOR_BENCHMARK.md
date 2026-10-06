# MiniMax H3 Shared Accelerator — Per-Surface Benchmark & 3F Status

**Authority:** Live Comfy MCP on canonical `:8188` (RTX 5090 / 32 GB). All graphs built from `route_a_adapter.py` (post shared-authority refit) and validated/run live via MCP.
**Status:** T2V + 1F LIVE-PROVEN. 3F NOT YET CERTIFIED (honest).

## Per-surface benchmark (identical inputs per surface: Baseline vs SageAttention)

| Surface | Mode | Baseline Time | Sage Time | Speedup | Visual | Audio | AV Sync | MCP | Live Proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Text2Video | T2V (124f, 1280×704, 4-step) | 98.94s (cold) | 45.33s (sage-enabled) | ~2.18x | CLEAN ✅ | aac stereo 32kHz ✅ | intact ✅ | ✅ | ✅ run_workflow + ffprobe |
| 1 Frame | I2V (362f, 1280×704, 4-step, Korri) | 347.15s (cold) | 161.9s (sage-enabled) | 2.14x | CLEAN ✅ | aac stereo 32kHz ✅ | intact ✅ | ✅ | ✅ benchmark report |
| 3 Frame | Multi-frame (segmented-a) | N/A | N/A | N/A | N/A | N/A | N/A | ✅ (plan) | NOT YET CERTIFIED |

Conservative speedup reference: the 1F fully-cold benchmark (347.15s → 161.9s = 2.14x) is the conservative figure for the same model/sampler/steps; the T2V observed 2.18x is consistent (SageAttention acts on the per-step model forward pass, identical regardless of T2V-vs-I2V conditioning).

## T2V live smoke (Phase 4) — evidence

- Graph: `code_t2v_sage.json` (built from `route_a_adapter.build_t2va_graph` → `apply_certified_accelerator`).
- `validate_workflow` on `:8188` → valid (0 errors, 0 warnings).
- Baseline (`code_t2v_baseline.json`, accelerator stripped): **98.94s**, ffprobe → h264 1280×704 124f 5.167s + aac stereo 32kHz 5.167s. **Native audio present (joint AV latent).**
- Sage (`code_t2v_sage.json`): **45.33s**, `attention backend: sage-enabled`, ffprobe → identical streams/duration. **AV intact.**
- Visual (frame 62): CLEAN cinematic neo-noir alley, red-coat figure, neon, mist — **no echo/ripple/ghosting**.
- Verdict: clean visual, no fast-motion artifact regression, native audio intact, AV sync intact, measurable speed gain. **T2V CERTIFIED with SageAttention.**

## 1F live (Phase 3) — evidence

- Graph: `code_i2v_sage.json` (built from `route_a_adapter.build_i2va_graph` → `apply_certified_accelerator`), `validate_workflow` → valid.
- Benchmark (frozen): baseline 347.15s → Sage 161.9s = 2.14x, CLEAN, AV intact, stable (0.4% variance). See `SPEEDCACHE_BENCHMARK_REPORT.md`.
- **1F CERTIFIED with SageAttention.**

## 3F (Phase 5) — status & honest verdict

**MiniMax H3 does NOT natively take three timed keyframes.** The genuine Adept contract (`three_frame.py`):
- `strategy = "segmented-a"`, `nativeSupported = False`, honestly disclosed ("MiniMax H3 does not take three timed keyframes natively. Adept plans this as two guided beats: Start to Middle, then Middle to End.").
- Two intervals: Start→Middle, Middle→End. Each interval is an I2V pass.

**Acceleration plumbing (IN PLACE):** each I2V interval consumes the ONE shared certified authority via `route_a_adapter.build_i2va_graph` → `apply_certified_accelerator` (SageAttention, cache off). No per-surface accelerator config.

**Real multi-frame graph (NOT WIRED):** there is no MiniMax 3F execution orchestrator. The workflow registry has no MiniMax 3F leaf (MiniMax H3 executes via `route_a_adapter` T2V/I2V only). The only 3F execution leaf in the codebase is `wan.three_frame` (WAN, retired from v1.1). `hosted_providers/capabilities.py` marks `three_frame_workflows: "Available but Uncertified"`. `model_registry.py` records MiniMax H3 `does_not_support: ["native_three_keyframe", "three_frame_uses_adept_segmented_assembly"]`.

**Verdict:** 3F status = **NOT YET CERTIFIED**. The acceleration plumbing is in place (each interval uses the shared SageAttention authority), but the real multi-frame execution+assembly graph is not yet wired, so 3F cannot be live-proven. Per Phase 5, it is NOT faked through ordinary I2V, and WAN/retired models are NOT restored to fill the gap. The owner can decide when to wire the MiniMax 3F execution orchestrator (two `submit_i2va` interval passes + timeline assembly); when wired, each interval will automatically carry the certified SageAttention authority.

## Required MCP verdicts (T2V + 1F)

- ✅ COMFY MCP VERIFIED · ✅ SPEED CACHE NODE VERIFIED · ✅ LIVE GENERATION VERIFIED · ✅ VIDEO STREAM VERIFIED · ✅ AUDIO STREAM VERIFIED · ✅ AV SYNC VERIFIED · ✅ BENCHMARK VERIFIED
- 3F: ✅ MCP (plan) · ⚠️ LIVE GENERATION NOT YET CERTIFIED (execution orchestrator not wired)

## Final matrix

| Surface | MiniMax Mode | SageAttention | Cache Reuse | AV | MCP | Live Proof |
| --- | --- | --- | --- | --- | --- | --- |
| Text2Video | T2V | ON | OFF | intact | ✅ | ✅ live |
| 1 Frame | I2V | ON | OFF | intact | ✅ | ✅ live |
| 3 Frame | Multi-frame (segmented-a) | ON (per interval, plumbing in place) | OFF | N/A | ✅ plan | NOT YET CERTIFIED |
