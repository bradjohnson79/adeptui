# MiniMax H3 — Selective Model Loading + Warm Residency Audit

**Status:** GOVERNING DOCUMENT for H3 model-loading / residency / prewarm (2026-09-07)
**Scope:** MiniMax H3 on Route A `:8192` — cold/warm loading, lifecycle phases, warm residency, selective unload, opportunistic prewarm.
**Supersedes:** none (first governing doc for this topic).

---

## 1. What loads during a cold 1 Frame execution

The production 1F graph (`build_i2va_graph` in `studio-api/app/minimax_h3/route_a_adapter.py`) references exactly **four** model files, served from `D:\01_Models\Video\MiniMax-H3\ComfyUI` via `extra_model_paths.yaml` (`is_default: true`):

| Model / component | File | Disk size | Why loaded | Graph consumer | Required for 1F? | Residency phase | Classification |
|---|---|---|---|---|---|---|---|
| Text encoder (Qwen3-VL 32B, NVFP4-AWQ) | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | **14.61 GB** | Encodes prompt (+ negative) into conditioning | `CLIPLoader` → `MiniMaxH3TextEncode` | YES | Encoding phase; idle after | REQUIRED / WARM-REUSABLE |
| Diffusion UNET (FL2VA pruned int8 convrot) | `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | **19.53 GB** | Joint A/V latent sampling | `UNETLoader` → `MiniMaxH3Sampler` | YES | Sampling phase | REQUIRED / WARM-REUSABLE |
| Video VAE (fp16) | `vae/minimax_h3_video_vae_fp16.safetensors` | **4.85 GB** | Encodes first frame → latent; decodes video latent → pixels | `VAELoader` → `MiniMaxH3ImageEncode` + `MiniMaxH3VideoDecode` | YES | Encoding (brief) + decode (brief) | REQUIRED / WARM-REUSABLE |
| Audio VAE (fp32) | `vae/minimax_h3_audio_vae_fp32.safetensors` | **0.56 GB** | Decodes audio latent → waveform | `VAELoader` → `MiniMaxH3AudioDecode` | YES | Decode phase only | REQUIRED / WARM-REUSABLE |
| Source first frame | creator's image asset | — | I2V conditioning | `LoadImage` → `MiniMaxH3ImageEncode` | YES (1F) | Encoding phase | REQUIRED (input, not a model) |

**Total staged: 39.6 GB on disk / ~45.5 GB staged in RAM+VRAM** (dynamic-VRAM staging includes runtime overhead). Matches the owner-reported "~35 GB of model loading."

**No T2V-specific or 3F-specific model files exist.** T2V, 1F, and 3F share the identical four-model stack; only the conditioning nodes differ. The production rule — *load only dependencies reachable from the selected graph* — is therefore already structurally satisfied: the 1F graph can only ever pull these four files.

**UNNECESSARY — QUARANTINED (owner-approved 2026-09-07):** the shadow copy of the video VAE at `runtime\minimax-h3\comfyui\models\vae\minimax_h3_video_vae_fp16.safetensors` (**9,933 MB**, SHA-256 `5F0C2E16…FE0D3`) was moved to `.quarantine\2026-09-07_h3-shadow-video-vae\` with full metadata. Proof before move: (1) this fork's `folder_paths.add_model_folder_path` inserts `is_default` paths at position 0 → `D:` searched first; (2) runtime log `MiniMaxH3VideoVAE … 4965MB Staged` = D: copy; (3) deterministic `get_full_path` → D: copy. Post-move: exactly one resolvable H3 video VAE (live `:8192` `VAELoader` list = 1 entry), preflight resolves all four components to D:, Route A healthy, no restart needed. **~9.9 GB reclaimed from active model-path storage.** Note: `ComfyUI-Shared\models\vae\` holds a separate 4,966.6 MB copy (same size as D:) used by the `:8188` ref2v path — intentionally untouched. Permanent deletion only after soak, in a later storage-cleanup pass.

---

## 2. Lifecycle phases and co-residency

Measured on the cold run (124-frame, 4-step 1F render, RTX 5090 32 GB):

| Phase | Models needed | Cold time | Warm time (new seed) | Warm time (new prompt) |
|---|---|---|---|---|
| Boot `:8192` | none | 30.6 s → **1.4 GB baseline** | — | — |
| Prompt/reference encoding | TE + video VAE | **143.6 s** (TE-dominated) | ~0 s (node cache, same prompt) | **14.5 s** (TE resident) |
| Sampling | UNET (+ TE output) | **408 s** (102 s/it × 4) | 57.6 s (14.4 s/it) | 82 s (20.5 s/it) |
| Video + audio decode | video VAE + audio VAE | ~25 s | ~15 s | ~15 s |
| **Total** | | **690 s** | **78.3 s (8.8×)** | **111.4 s (6.2×)** |
| Peak VRAM | | **32.0 GB** | 31.9 GB | 31.9 GB |
| First draft preview | | ~17 s into sampling | 16.8 s | 56.4 s (after TE re-encode) |

**Co-residency findings:**
- All four models end up resident simultaneously (45.5 GB staged > 32 GB VRAM ⇒ the fork's **dynamic-VRAM layer streaming** is mandatory, not optional — this is inherent to running a 40 GB model stack on a 32 GB card, not a defect).
- **Sampling dominates cold cost** (408 s of 690 s) because the UNET streams layers from RAM every step on first touch. Warm, the same sampling is 7× faster.
- **TE encode is the second-largest cold cost** (143.6 s) and drops 10× when warm.
- The video VAE is needed at both ends (encode first frame, decode result) — it cannot be unloaded between phases without a reload penalty. The audio VAE (0.56 GB) is needed only at decode but is too small to matter.

**"Does the second render reload the same 35 GB?"** — **No disk reload.** The log line "prepared for dynamic VRAM loading … Staged" on warm runs is *re-registration* of already-RAM-resident weights, not a re-read from disk. Warm runs are 6–9× faster end-to-end. This is **not a lifecycle defect**. The residual warm cost (dynamic-VRAM re-streaming during sampling) is the price of the 40 GB-on-32 GB fit and can only be removed by `--disable-dynamic-vram` (which would OOM) — rejected.

---

## 3. Boot weight + selective loading — VERIFIED

- **`:8192` boots lightweight:** 30.6 s to healthy, **1.4 GB VRAM baseline, zero models preloaded**. Confirmed via supervisor `POST /restart-route-a` + `nvidia-smi`.
- **On-demand load:** models load only when a graph that references them executes. Confirmed: post-boot baseline stayed 1.4 GB until the first job.
- **No eager loading** of any H3 component at boot, API start, or page open.

---

## 4. Selective unload under GPU admission — IMPLEMENTED

Gap found: `gpu_admission.py` could free `:8188` models (`free_comfy_models`) but had **no** mechanism to release `:8192` H3 models when another service needed the GPU.

**Changes (`studio-api/runtime_supervisor/gpu_admission.py`):**
- **`free_route_a_models()`** — POSTs `/free` to `:8192`, mirroring the `:8188` path. Safety gates: Route A must be healthy; **refuses if a job is running** (never interrupts an active render); reports freed VRAM.
- **`request_comfy_admission_with_route_a_handoff()`** — when `:8188` (or another service) requests the GPU and Route A is idle-warm, releases H3 models first, then admits.

**Live-verified:** VRAM 30,985 MB → **1,332 MB** (−29.65 GB) on `/free`; Route A process stayed alive and healthy; subsequent job reloaded cleanly.

**Tests:** `studio-api/tests/test_gpu_admission_route_a_free.py` (hermetic, mocked network) — covers healthy/idle free, busy refusal, unhealthy refusal, admission handoff.

---

## 5. Opportunistic prewarm on generator selection — IMPLEMENTED

Owner rule: *when the creator selects MiniMax H3, quietly begin loading; opportunistic only.*

**Backend (`studio-api/app/minimax_h3/prewarm.py` + routes in `api.py`):**
- `POST /api/minimax-h3/prewarm` — submits a **micro-render probe** (5 frames, 1 step, 480×256 T2V graph) that touches all four H3 models. State machine: `idle → starting_runtime → loading → warm | failed`. `GET` returns status; `POST /prewarm/cancel` interrupts an in-flight load.
- **Opportunistic gates:** refuses if `:8188` is actively rendering (GPU admission); starts Route A if down; refuses if Route A's queue is busy; never evicts an active workload.
- **No stale-warm lie (bug fixed during verification):** `start_prewarm` originally short-circuited on internal `status == "warm"`. After an external eviction (`/free`), that returned fake readiness. Fix: every explicit prewarm re-submits the probe — cache-hit cheap (~3–10 s) when resident, a genuine reload when not. Unit test updated (`test_prewarm_warm_reverifies_with_probe`).

**Frontend (`studio-web/src/components/minimax-h3/prewarmTrigger.ts`):**
- `h3PrewarmOnGeneratorSelect()` — fires prewarm on transition INTO `minimax-h3` (deduplicated), fires cancel on switch away. Wired into `EngineAuthoritySelect` (all CREATE surfaces: 1F/3F/T2V), `TimelineInspector`, and `ModelMenuDrawer`.
- **Does NOT fire on page open** — only on explicit selection.

**Live-verified:**
- Cold prewarm after eviction: **419 s** genuine reload → `warm`, VRAM 1.3 GB → 31.2 GB. (This is the cold cost now hidden behind frame-picking/prompt-writing instead of after the Generate click.)
- Warm prewarm (models resident): **10.2 s** → `warm`.
- UI hook: browser-verified — selecting MiniMax H3 in the 1F panel produced a fresh prewarm (`clientId h3-prewarm-1788836075`, `status: warm` in ~3 s with models resident). Cancel-on-switch is wired and backend no-ops gracefully when already warm (nothing to cancel).

**Tests:** `studio-api/app/minimax_h3/test_prewarm.py` — state machine, busy-runtime refusal, GPU-blocked refusal, idempotency, cancellation, warm re-verify.

---

## 6. Measurements summary

| Metric | Value |
|---|---|
| `:8192` boot (lightweight) | 30.6 s, 1.4 GB baseline |
| Cold 1F job (124f/4-step) | 690 s total; TE 143.6 s; sampling 408 s; peak VRAM 32.0 GB |
| Warm job, same prompt+seed | 3.0 s (full node-cache hit — not a residency measure) |
| Warm job, same prompt, new seed | 78.3 s (**8.8×** vs cold) |
| Warm job, new prompt+seed | 111.4 s (**6.2×** vs cold) |
| Selective unload (`/free`) | −29.65 GB released; process alive |
| Prewarm cold reload | 419 s → warm |
| Prewarm warm re-verify | ~3–10 s |

---

## 7. Verdict

**GO — H3 SELECTIVE MODEL LOADING + WARM RESIDENCY CERTIFIED.**

- ✅ Exact 1F load set enumerated (4 models, 39.6 GB); no surface-specific files exist; graph-reachable-only rule structurally satisfied.
- ✅ Lightweight boot confirmed (1.4 GB, nothing preloaded).
- ✅ Warm residency confirmed real (6–9× speedup, no disk reload) — the "second render reloads 35 GB" concern is disproven.
- ✅ Selective unload implemented + live-verified (−29.65 GB, process survives, busy-render protected).
- ✅ Opportunistic prewarm implemented end-to-end (API + state machine + UI hook on all CREATE surfaces), cold-reload and warm-verify both live-proven, stale-warm bug found and fixed.
- ⚠️ ~~One follow-up for the owner~~ **DONE (owner-approved):** the shadowed 9.9 GB local video-VAE duplicate was quarantined to `.quarantine\2026-09-07_h3-shadow-video-vae\` with SHA-256 metadata after triple resolution proof (code semantics, runtime log, deterministic `get_full_path`). Post-move: exactly one resolvable copy, preflight green, Route A healthy, zero renders burned. Permanent deletion after soak.

**Out of scope (unchanged):** golden A/V path untouched; no quantization, no SpeedCache/VDN, no alternate encoders; `--disable-dynamic-vram` rejected (would OOM the 40 GB stack on 32 GB).
