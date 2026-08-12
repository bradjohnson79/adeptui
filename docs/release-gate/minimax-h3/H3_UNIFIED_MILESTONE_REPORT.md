# MiniMax H3 — Unified Milestone Report

**Date:** 2026-08-03  
**Primary tree:** `C:\AdeptFilmWorks\AIVideoStudio` · branch `feature/ai-guided-setup`  
**H3 spike worktree:** `C:\AdeptFilmWorks\AIVideoStudio-h3` · Route A branch `spike/minimax-h3-rtx5090` · starting SHA `c932214`  
**Route A run:** `RUN-20260803-181526`  
**Primary acceptance:** Route A verdict PRIMARY ACCEPTED 2026-08-03  

> **Current authoritative status**
>
> MiniMax H3 has produced genuine local media through the accepted Route A isolated runtime on the RTX 5090. The runtime is accepted with limitations and may proceed to deliberate Adept UI integration work. MiniMax H3 remains disabled for creator production use, Best Match, and general model routing until product-level integration and Adept-UI-only certification are complete.

---

## Authority and Supersession

For MiniMax H3 status, **this report is the authoritative milestone summary in the main repository.**

Where earlier reports conflict:

1. Route A completion evidence and primary acceptance govern the **current local-runtime verdict**.
2. The Canadian licence-clearance report governs the **private Canadian development verdict**.
3. The Adept UI surface certification governs **surface-wiring readiness**.
4. The earlier Canada Diffusers runtime report remains authoritative **only as evidence of that failed runtime approach**.
5. Earlier parallel-program summaries are **historical** and are **superseded for current H3 runtime status**.

Do not treat older strings such as `NOT LOCALLY FEASIBLE YET` or parallel-program `NO-GO — RUNTIME NOT PROVEN` as the current local-runtime status after Route A primary acceptance.

---

## Executive summary

| Track | Accepted status |
|---|---|
| Canada private-dev licence | Cleared with conditions (`CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS`) |
| Adept UI surface wiring | `GO — H3 ADEPT UI SURFACE WIRING READY` (Creator Disabled; honesty + tools only) |
| Canada Diffusers FL2VA / early Comfy shard attempt | Closed NO-GO — `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO` (historical) |
| Route A Comfy-Org optimized checkpoints on RTX 5090 | `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED` (PRIMARY ACCEPTED) |
| Adept UI integration readiness (Addendum D) | `READY WITH LIMITATIONS` |
| Creator availability / Best Match / production wiring | **Disabled** — not authorized by this report |
| FL2VA Diffusers payload (~144 GB) | Retain for Route B; not used by Route A |

---

## Worktrees, branches, and ports

| Role | Path / value |
|---|---|
| Primary Adept UI | `C:\AdeptFilmWorks\AIVideoStudio` · `feature/ai-guided-setup` |
| H3 spike | `C:\AdeptFilmWorks\AIVideoStudio-h3` · Route A on `spike/minimax-h3-rtx5090` (earlier Canada spike docs also cite `spike/minimax-h3-33b-rtx5090`) |
| Isolated Route A ComfyUI | `http://127.0.0.1:8192` · ComfyUI `16e3f303` · PyTorch `2.11.0+cu128` |
| Production ComfyUI | Port `8188` — untouched by Route A |
| Canonical Route A model root | `D:\01_Models\Video\MiniMax-H3\ComfyUI\` |
| Retained Diffusers FL2VA | `C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\models\MiniMax-H3\FL2VA\` (Route B only) |

---

## Chronology (preserved)

1. **Official source / licence audit** — MiniMax H3 Community License; Canada not in Excluded Territories; private Canadian local development permitted with conditions.  
   Evidence: `docs/release-gate/minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md`, `docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md`

2. **Adept UI surface wiring** — Co-Director / Text2Video / One Frame / Three Frame honesty / Timeline / Library provenance / LTX fallback; Playwright surface cert. Creator remains Disabled.  
   Evidence: `docs/release-gate/minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md` → `GO — H3 ADEPT UI SURFACE WIRING READY`

3. **Canada Diffusers / shard Comfy attempt (closed)** — FL2VA Diffusers payload completed (~144 GB); released Diffusers lacked H3 pipeline classes; forcing shards into Comfy single-file workflow → meta-tensor failure; no MP4.  
   Evidence: `C:\AdeptFilmWorks\AIVideoStudio-h3\docs\models\minimax-h3\artifacts\rtx5090-canada\RUN-20260803-145133\H3_CANADA_RUNTIME_GATE_REPORT.md`  
   Verdict (historical only): `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO`

4. **Route A Official ComfyUI proof (accepted)** — Comfy-Org single-file optimized pack on `D:\01_Models`; isolated Comfy `:8192`; Gates A/B/C + reliability GO; Gate D experimental/limited; Addendum D `READY WITH LIMITATIONS`.  
   Evidence: `C:\AdeptFilmWorks\AIVideoStudio-h3\docs\models\minimax-h3\artifacts\route-a-rtx5090\RUN-20260803-181526\H3_ROUTE_A_COMPLETION_REPORT.md`  
   Verdict (current local runtime): `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED`

---

## Gate matrix (proof vs permission)

| Gate | Exact verdict | What it proves | What it does not authorize | Evidence |
|---|---|---|---|---|
| Canada licence clearance | `CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS` | Private Canadian local development may proceed under pinned licence conditions | Excluded-territory open-weight deployment; Creator production enablement | `docs/release-gate/minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md` |
| Adept UI surface certification | `GO — H3 ADEPT UI SURFACE WIRING READY` | UI contracts, honesty states, planning/preflight/fallback surfaces exist | Runtime-backed generation; Best Match; Creator enablement | `docs/release-gate/minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md` |
| Canada Diffusers / shard runtime (historical) | `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO` | That Diffusers/shard approach failed (no MiniMaxH3Pipeline; meta-tensor on forced Comfy load) | Current Route A status (superseded for local runtime) | `C:\AdeptFilmWorks\AIVideoStudio-h3\docs\models\minimax-h3\artifacts\rtx5090-canada\RUN-20260803-145133\H3_CANADA_RUNTIME_GATE_REPORT.md` |
| Route A Gate A (official sources) | `GO — OFFICIAL ROUTE A CHECKPOINTS VERIFIED` | Comfy-Org filenames, revision, licence inheritance, template match | That files are downloaded or load | `docs/models/minimax-h3/H3_ROUTE_A_OFFICIAL_SOURCE_GATE.md` (main) and h3 worktree twin |
| Route A download integrity | Pack verified (4 files, all `ok=true`) | Exact sizes/SHA-256 on `D:\01_Models` | Creator use; quality | `C:\AdeptFilmWorks\AIVideoStudio-h3\docs\models\minimax-h3\artifacts\route-a-rtx5090\RUN-20260803-181526\download_verify.json` |
| Route A dry-run | `GO — ROUTE A WORKFLOW DRY-RUN VALIDATED; SAFE TO QUEUE` | Nodes/paths resolve; Diffusers shards blocked from executable Route A path | Media generation success | `H3_ROUTE_A_WORKFLOW_VALIDATION.md`, `workflow_dry_run.json` |
| Route A Gate B | `GO — ROUTE A CHECKPOINTS LOAD ON GPU; NO META-TENSORS` | Ordered load on `cuda:0`; 2752 params; zero meta-tensors | Creator Adept UI; trained-range quality | `H3_ROUTE_A_CHECKPOINT_LOAD_PROOF.md`, `checkpoint_load_proof.json` |
| Route A Gate C | `GO — ROUTE A GENUINE T2VA MEDIA PRODUCED ON RTX 5090` | Isolated runtime can generate local video + audio on RTX 5090 | Creator-facing Adept UI use; Default/Best Match | `H3_ROUTE_A_LOCAL_MEDIA_PROOF.md`, `gate_c_t2va_run2.json`, mp4 outputs |
| Route A Gate D (practicality) | Experimental / limited on RTX 5090 (`GO WITH LIMITATIONS` in completion report) | Measured operating envelope (VRAM saturation, cold/warm timings, quality class) | Default or Best Match status; interactive creator latency | `H3_RTX5090_MEMORY_MATRIX.md`, `memory_profiles.json` |
| Route A reliability | `GO — ROUTE A REPEATABLE AND RECOVERABLE ON RTX 5090` | Repeat, warm, interrupt, recovery, cold restart at API/runtime level | Adept UI cancel UX; production queue semantics | `H3_ROUTE_A_RELIABILITY.md` |
| Integration readiness (Addendum D) | `READY WITH LIMITATIONS` | Adapter-oriented integration work may begin deliberately | Production enablement; Creator toggle; Law #28 cert complete | `H3_ADEPT_UI_INTEGRATION_READINESS.md` |
| Route A final | `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED` | Local Route A proof package accepted by primary | Creator production; LTX replacement | `H3_ROUTE_A_COMPLETION_REPORT.md` + primary acceptance |

---

## Runtime architecture (current)

```text
Creator Adept UI (Disabled for H3 generation)
        │
        │  (future Runtime Adapter — not production-registered)
        ▼
Isolated ComfyUI :8192  ← temporary rendering backend
        │
        ▼
D:\01_Models\Video\MiniMax-H3\ComfyUI\
  diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors
  text_encoders\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
  vae\minimax_h3_video_vae_fp16.safetensors
  vae\minimax_h3_audio_vae_fp32.safetensors
```

- **Route A uses** Comfy-Org official single-file optimized checkpoints only (`Comfy-Org/MiniMax-H3` @ `0543966fbdce5ba05709a8f2031c94bdba629b4a`).
- **Route A forbids** Diffusers FL2VA shards as Comfy drop-ins (prior meta-tensor regression).
- **FL2VA Diffusers tree retained** on the C: spike root for future Route B only.
- Production Comfy Shared / `:8188` / LTX / WAN / Adept registry were not modified by Route A.

---

## Measured Route A profile (exact values from accepted run)

Source of truth: `C:\AdeptFilmWorks\AIVideoStudio-h3\docs\models\minimax-h3\artifacts\route-a-rtx5090\RUN-20260803-181526\` and linked Route A docs. Values are copied, not estimated.

### Checkpoint pack

| File | Size (bytes) | SHA-256 | Verified |
|---|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 20,970,379,616 | `e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a` | `ok=true` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15,687,142,551 | `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6` | `ok=true` |
| `minimax_h3_video_vae_fp16.safetensors` | 5,207,808,496 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` | `ok=true` |
| `minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` | `ok=true` |
| **Total** | **42,470,585,471** | — | all verified |

### Gate C generation settings and output

| Metric | Recorded value |
|---|---|
| Requested width × height | 480 × 270 (height model-snapped to 256) |
| Output resolution | **480 × 256** |
| Frame count | **5** |
| Frame rate | **24 fps** |
| Video duration | **0.208333 s** |
| Steps | **4** |
| Sampler / scheduler | `res_multistep` / `simple` |
| Seed (Gate C success) | 424242 |
| Container | mov/mp4 (QuickTime / MOV) |
| Video codec | h264 High, yuv420p |
| Audio codec | **aac (LC), 32000 Hz, stereo** — native audio stream present and validated via ffprobe |
| Gate C output file size | 21,336 bytes (`MiniMax_H3_RouteA_00001_.mp4`) |
| Quality classification | **Experimental** — below trained range (~124–362 frames); low resolution; heavy temporal smearing/motion blur |

### Memory (profiles A–E, `memory_profiles.json`)

| Profile | VRAM used (MB) | VRAM free (MB) | RAM used (MB) | RAM free (MB) |
|---|---|---|---|---|
| A — baseline (nothing loaded) | 1,615.6 | 30,991.0 | 20,744.9 | 44,233.9 |
| B — +UNET | 21,771.6 | 10,835.0 | 21,848.6 | 43,130.2 |
| C — +UNET + CLIP | 32,606.6 | 0.0 | 31,242.9 | 33,735.9 |
| D — +UNET + CLIP + Video VAE | 32,606.6 | 0.0 | 46,913.7 | 18,065.1 |
| E — full pack | 32,606.6 | 0.0 | 48,021.2 | 16,957.6 |

- VRAM total recorded: **32,606.6 MB** (RTX 5090).
- Peak VRAM: **32,606.6 MB (100% / zero headroom from stage C onward)**.
- Full pack RAM used at profile E: **48,021.2 MB** of **64,978.7 MB** total (~10 GB spill relative to pack size narrative in completion report).
- Pagefile peak: **Not measured in the accepted Route A run.**
- Policy note recorded: `NORMAL_VRAM (async offload via comfy-aimdo)`.

### Timings

| Metric | Recorded value |
|---|---|
| Cold generation (model-load bound) | ≈ **259 s** |
| Warm generation (seed 71717) | **2.05 s** |
| Interrupt test | Sampling reached **85% (17/20)**; interrupted; prompt executed in **27.20 s**; `cancelled=True` |
| Machine usability during generation (interactive OS responsiveness metric) | **Not measured in the accepted Route A run.** |

### CUDA / kernel limitations

| Item | Recorded value |
|---|---|
| PyTorch | `2.11.0+cu128` |
| Device | `cuda:0 NVIDIA GeForce RTX 5090` |
| Meta-tensors at Gate B | **0** (2752 params, all `is_meta=False`, `device=cuda:0`) |
| CPU-only fallback | **Did not occur** |
| Optimized CUDA kernels (comfy-kitchen) | **Disabled** — torch cu128; cu130 required; eager backend used |

### Reliability results

| Test | Result |
|---|---|
| Outputs produced | **4** genuine mp4s (seeds 424242, 71717, 99999, 55555) |
| Warm repeat | Success |
| Interrupt | Success (`cancelled=True`; server remained healthy) |
| Recovery after interrupt | Success (new job completed) |
| Cold restart + generation | Success |

---

## Contracts inventory

| Contract | Location | Role |
|---|---|---|
| Adept request contract | `docs/architecture/minimax-h3/ADEPT_MINIMAX_H3_REQUEST_CONTRACT.md` | Shared planning request shape |
| Surface wiring design | `docs/models/minimax-h3/H3_SURFACE_WIRING.md` | UI/API surface (not runtime GO) |
| Three Frame runtime truth | `docs/models/minimax-h3/H3_THREE_FRAME_RUNTIME_TRUTH.md` | Honesty: no native three-frame mode |
| Route A runtime contract | `AIVideoStudio-h3/docs/models/minimax-h3/H3_ROUTE_A_RUNTIME_CONTRACT.md` | Adapter-oriented runtime contract (not production-registered) |
| Capability registry draft | `AIVideoStudio-h3/docs/models/minimax-h3/H3_CAPABILITY_REGISTRY_DRAFT.md` | Evidence-driven draft only |
| Integration readiness | `AIVideoStudio-h3/docs/models/minimax-h3/H3_ADEPT_UI_INTEGRATION_READINESS.md` | Addendum D |
| FL2VA payload decision | `AIVideoStudio-h3/docs/models/minimax-h3/H3_EXISTING_FL2VA_PAYLOAD_DECISION.md` | Retain for Route B |

---

## Explicit non-claims

This report does **not** authorize or claim:

- Creator-facing MiniMax H3 Ready / Available as a production engine  
- Best Match or Production Dock enablement  
- Replacement of LTX as the permanent local fallback  
- Law #28 Co-Director disposable-project Playwright certification  
- Trained-range quality (≥768p, ≥124 frames)  
- Production Capability Registry registration  
- Timeline Re-take, native Three Frame, PoseCraft→H3, or ERS→H3 product paths  
- Any change to the accepted Canadian licence verdict  

---

## Remaining work (three levels)

### Required before integration begins

- Merge or register the Runtime Adapter contract into the deliberate Adept integration design (still disabled for creators).
- Reconcile the capability draft with the production Capability Registry (labels only; no optimistic Supported claims).
- Resolve runtime lifecycle, health, progress, errors, and cancellation boundaries in the adapter layer.
- Preserve the isolated backend abstraction (ComfyUI remains replaceable).

### Required before creator beta

- Wire H3 through Adept UI rather than direct Comfy interaction.
- Complete Co-Director, Text2Video, One Frame, and Timeline paths appropriate to proven capabilities only.
- Run a real Adept-UI-only disposable-project certification (Law #28).
- Confirm Library import, provenance, persistence, cleanup, and explicit LTX fallback.
- Complete missing-model and Setup readiness UX (including configured model root `D:\01_Models` policy).

### Required before broader production enablement

- Improve or accept the RTX 5090 quality/performance profile beyond the experimental envelope.
- Resolve CUDA 13.0 / kernel optimization work where needed.
- Complete repeated reliability testing at creator-relevant settings.
- Establish regional/licence enforcement for any use beyond private Canadian operation.
- Prove operational support and upgrade strategy.

---

## Synthesis rule (for this report)

This document is **evidence reconciliation only**. It does not rerun runtime tests, reinterpret accepted measurements, promote capabilities, modify the Canadian licence conclusion, upgrade Creator availability, or erase historical verdicts.

---

## Final program status (MiniMax only)

```text
MINIMAX H3 PROGRAM STATUS — LOCAL ROUTE A PROVEN WITH LIMITATIONS; CREATOR PRODUCTION REMAINS DISABLED
```
