# MiniMax H3 Shared Acceleration Authority — Frozen Contract (v1.1)

**Authority:** Live Comfy MCP `object_info` on canonical `:8188` (comfyui-speed-minimaxH3 pack). Benchmark verdict live-proven on RTX 5090 / 32 GB with the Korri 4-step baseline. No accelerator invented from source/memory — all from live MCP + live `run_workflow`.
**Status:** CONTRACT FROZEN. This is the ONE shared MiniMax H3 acceleration authority. T2V, 1 Frame I2V, and 3 Frame multi-frame assembly all consume it. It must not be duplicated per-surface.

## Certified accelerator

**SageAttention** — delivered via the `MiniMaxH3SpeedCache` node (pack `comfyui-speed-minimaxH3`, display "MiniMax H3 Speed Cache (Safe)").

| input | certified value | live default | note |
| --- | --- | --- | --- |
| `reuse_threshold` | **0.0** | 0.12 | **RESIDUAL CACHE DISABLED.** Do not re-enable. |
| `sage_attention` | **"auto"** | "auto" | SageAttention ON — the real accelerator |
| `start_percent` | 0.10 | 0.10 | default |
| `end_percent` | 0.90 | 0.90 | default |
| `max_consecutive_skips` | 2 | 2 | default (moot: cache off) |
| `cache_device` | "auto" | "auto" | default |
| `model` | `[UNETLoader, 0]` | — | link input |

Output: `MODEL` → consumed by `BasicScheduler.model` and `BasicGuider.model`.

**Speed Cache is NOT the certified accelerator.** The `MiniMaxH3SpeedCache` node is only the delivery surface for SageAttention. Residual reuse is OFF.

## Benchmark verdict (live, MCP-verified)

| Arm | Config | Time | Speedup | Visual | AV |
| --- | --- | --- | --- | --- | --- |
| Baseline | no accelerator | 347.15s | 1.00x | CLEAN | intact |
| Speed Cache 0.12 | residual reuse ON | 272.67s | 1.27x | **SEVERE artifacts** | intact |
| Speed Cache 0.12 + sage | residual reuse ON + sage | 136.11s | 2.55x | **SEVERE artifacts** | intact |
| Speed Cache 0.08 + sage | qfirst reuse ON + sage | 132.89s | 2.61x | **SEVERE artifacts** | intact |
| **SageAttention-only** | **reuse 0.0 + sage auto** | **161.9s** | **2.14x** | **CLEAN** | **intact** |

Root cause of cache regression: residual reuse reuses a prior step's transformer-block residual; with 4-step distilled sampling each step makes large latent changes, so the reused residual is a poor approximation → echo/ghost/ripple artifacts. The quality-first threshold (0.08) does not help (accumulated signature 0.04390 < 0.08, same skip, same artifacts). Only `reuse_threshold=0.0` avoids it.

## Shared authority module

`studio-api/app/minimax_h3/acceleration.py` — the single source of truth. Exposes:

- `apply_certified_accelerator(graph, model_node_id="1", accel_node_id="16")` — inserts the certified node, strips legacy EasyCache, rewires scheduler/guider model inputs. **All surfaces call this; they do not hand-write the accelerator.**
- `assert_no_residual_cache(graph)` — fails closed if EasyCache or any `reuse_threshold > 0` residual cache is present in a production CREATE graph (Phase 6 enforcement).
- `assert_certified_accelerator_present(graph)` — fails closed if a production MiniMax H3 graph lacks the certified accelerator.
- `ACCELERATOR_PROVENANCE` — provenance record (`accelerator: "SageAttention"`, `residualReuse: False`, `creatorLabel: "Optimized"`).

## Runtime

**Isolated Route A `:8192`** (preserved per Master Program Phase 29 — MiniMax H3 runs on a separate Comfy instance from production `:8188` to prevent GPU contention; per owner decision 2026-09-06). The certified SageAttention accelerator (`comfyui-speed-minimaxH3`) must be installed on this `:8192` instance. `route_a_adapter.py` targets `:8192` via `settings.minimax_h3_runtime_url` (config default `http://127.0.0.1:8192`); `private_access.py` enforces the `:8192` isolation gate. The `:8192` lifecycle is owned by the canonical supervisor; MiniMax H3 shares the GPU under the standard admission policy.

### `:8192` live proof (2026-09-06)

- `comfyui-speed-minimaxH3` installed into `:8192` `custom_nodes` (patched `time_shift_sigma` variant, copied from `:8188`).
- `MiniMaxH3SpeedCache` node registered live on `:8192` (`object_info`): required `model, reuse_threshold, start_percent, end_percent, max_consecutive_skips, cache_device`; optional `sage_attention` (default `"auto"`). Matches the certified profile.
- Live T2V smoke (22 frames, certified `reuse_threshold=0.0` + `sage_attention="auto"`) **completed on `:8192`** in 210.3s (cold model load from shared `D:\01_Models\Video\MiniMax-H3\ComfyUI`).
- `ffprobe`: h264 480×256 0.9167s + aac stereo 32 kHz 0.917s — **native AV intact, sync intact.**
- Accelerator live-proven on the actual isolated MiniMax `:8192` runtime (MCP targets `:8188`; `:8192` verified via direct HTTP `object_info` + `api/prompt` + `history`).

## Surface wiring (shared execution, separate conditioning)

Only the MiniMax model execution layer is shared. Conditioning stays surface-specific:

- **Text2Video:** `MiniMaxH3ImageToVideo` (words-only, no `first_frame`) → certified accelerator → scheduler/guider/sampler → Video VAE + Audio VAE → CreateVideo.
- **1 Frame I2V:** `LoadImage` → `MiniMaxH3ImageToVideo.first_frame` → certified accelerator → scheduler/guider/sampler → Video VAE + Audio VAE → CreateVideo. (Benchmark authority — preserved exactly.)
- **3 Frame:** MiniMax H3 does NOT natively take 3 timed keyframes. Genuine contract = two I2V segments (Start→Middle, Middle→End), each consuming the certified accelerator, assembled on the timeline. `nativeSupported=False`, honestly disclosed. Status NOT YET CERTIFIED until the real multi-frame graph is live-proven.

## Absolute quality law

Quality > speed. Acceleration may not trade fast-motion clarity, temporal stability, character consistency, fine detail, audio quality, or AV sync for speed. Any surface showing quality regression with SageAttention is NOT certified until fixed.

## Native AV (hard output contract)

All certified MiniMax CREATE graphs retain: MiniMax Video VAE + MiniMax Audio VAE + CreateVideo (24fps) + AV container. `ffprobe` must show video + audio streams, correct duration, valid sync. A fast-but-silent render fails certification.

## Creator-spec fidelity

Acceleration may not alter: prompt, seed, frame inputs, duration, FPS, resolution, aspect ratio, audio, or generator identity. No hidden fallback or mutation.

## Forbidden in v1.1 production

- `reuse_threshold` > 0.0 (0.12, 0.08, or any residual reuse)
- `EasyCache` node (legacy, threshold 0.2 — same regression)
- Stacking Speed Cache with EasyCache or another full-model cache
- `sage_attention: "disabled"` (disables the certified accelerator)
- Per-surface hand-written accelerator configs (must use `apply_certified_accelerator`)

Cache reuse may be investigated later for 20+ step trajectories; it is NOT part of this mission.

## MCP verification (Phase 2, complete)

- `nodes get MiniMaxH3SpeedCache` → live contract confirmed on `:8188` (pack, inputs, defaults, output MODEL).
- `validate_workflow` + `run_workflow` → live-proven during benchmark (all arms).
- `server_info` / `system_stats` → `:8188` healthy, RTX 5090 / 32 GB.

**Contract freeze complete. Downstream phases must not invent accelerators outside this frozen authority; changes require primary approval.**
