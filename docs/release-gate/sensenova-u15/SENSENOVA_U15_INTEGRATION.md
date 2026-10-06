# SenseNova U1.5 — Character Creator + ERS Integration

> **SUPERSEDED** — See `SENSENOVA_U15_UNINSTALL.md` (2026-08-23). SenseNova U1.5 runtime has been fully uninstalled and removed from the system. This document is retained as historical record only.

Governing document for this milestone (Build Law 30). Older Character Creator / ERS reports are historical and are not this gate’s truth.

**Date:** 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**Certification project:** `SenseNova Integration Lab` (disposable). Never Schnick Coffee. Never mutate Korri or Venture production assets.

## Verdict

```text
E2E BLOCKED — official SenseNovaU1LocalLoader never reaches CUDA on this 64 GB host
NO-GO — FULL-STACK E2E NOT VERIFIED
```

**Default recommendation (all three surfaces together):**

- Character Creator: **REVERT DEFAULT** (keep Flux)
- Spatial Map → ERS: **REVERT DEFAULT** (keep Qwen 2512 I2I)
- Scene Creator / Mini: **REVERT DEFAULT** (keep Qwen 2512)

SenseNova is wired and selectable as **SenseNova U1.5 / SenseNova U1.5 — Not Ready**. It is **not** the product default. Both native full sheets have not passed live RTX 5090 proof. Defaults will flip together only after both live sheets pass.

## E2E TRACE

| Stage | Result | Notes |
|---|---|---|
| User action | FAIL | Live Generate not run. Official loader never produced an image. |
| Frontend | PASS | Dropdowns, Not Ready label, defaults unchanged. Mini/camera-ref no longer offer SenseNova |
| API | PASS | Routing, refuse T2I ERS, native CRS enqueue, parameterized SenseNova refuse copy |
| Backend | PASS | Builders, compilers, registry Draft entries, installer torch isolate + torch-line exclusion |
| Persistence | PARTIAL | Lab project + Mira + Observatory + Atlas attached. No live SenseNova sheet |
| Runtime | FAIL | Weights 13/13 on disk. Official `SenseNovaU1Local*` nodes present. Torch `2.10.0+cu130`. Two official-node smokes (`fast` `bfcfd213`, `low` `7f053990`) completed `from_pretrained` 1116/1116 then held ~40 GB host RAM, ~2 GB VRAM, never CUDA, no history. Evidence: `docs/release-gate/sensenova-u15/evidence/smoke-ram-pressure.json`. |
| Result | FAIL | No smoke PNG. No native CRS / ERS image |
| Reload | N/A | |
| Downstream | N/A | |

## Dual product law

SenseNova is a Reference Sheet specialist. Flux / Qwen keep the simpler 4-view CRS and current Qwen I2I / GPT Image 2 ERS contracts. Defaults flip together only if both native sheets pass.

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 Comfy probe | DONE | Live Comfy 0.32.0, v3 API, RTX 5090, transformers 5.8.0. No Comfy upgrade. |
| 1 Install | DONE (disk + nodes) | Official nodes cloned (`ComfyUI-SenseNova-U1` v0.2.0). Extra-paths `adept_sensenova` added. Installer now uses `--no-deps` **and** a filtered `requirements.adept-no-torch.txt` that strips `torch` / `torchvision` / `torchaudio` (a direct `torch==2.8.0` pin is no longer installed). Weights complete: `inspect_weights()` `completeShards=13`, `runtimeReady=true`. Live Comfy lists official `SenseNovaU1Local*` nodes. Torch remains `2.10.0+cu130`. |
| 2 Registry | DONE | Draft keys: `sensenova.txt2img`, `.edit`, `.reference`, `.crs`, `.ers`. Fingerprints redact volatile inputs. |
| 3 Prompts | DONE | Native CRS + ERS compilers. Layout/density only. Korri / Venture / Adept Chronicles copy banned. |
| 4 Character Creator | DONE (code) | SenseNova enqueues one `sensenova.crs` job. Flux/Qwen remain 4-tile. Default remains Flux. |
| 5 ERS | DONE (code) | `sensenova.ers` when selected + Atlas pixels. Default remains Qwen. T2I ERS refused. Lab Observatory Atlas attached (`be0a9495-9879-4e3b-9b4f-bdfe7d7d214f`). Scene Creator Mini / camera-ref catalog is Qwen + GPT Image 2 only. |
| 6 GPU / default | E2E BLOCKED | Official loader never allocated CUDA after full weight load. No live native CRS vs Korri-style layout. No live native ERS vs Venture-style layout. Defaults not flipped. |
| 7 Tests | PARTIAL | Installer + adversarial 15 passed. Playwright listing on `:5173`→`:8758`: CC Flux default + ERS Qwen default both passed after sticky-select reset. Live generate not run (GPU proof blocked). |
| 8 Reviews | DONE (code) | Kimi B1/B2 repaired. GLM refuse-copy parameterized. Overall remains NO-GO because GPU proof failed. |

## Torch incident (repaired)

Official `sensenova-u1` metadata pinned `torch==2.8.0` and pip replaced Comfy’s `2.10.0+cu130` with **CPU** `2.8.0+cpu`. That would have broken Flux / Qwen / Z-Image.

Restored:

- `torch 2.10.0+cu130`
- `torchvision 0.25.0+cu130`
- `torchaudio 2.10.0+cu130`
- CUDA available: True
- `sensenova-u1` still imports (0.1.0)

Do **not** `pip install -r` the official node `requirements.txt` again without the installer guard (filtered no-torch requirements + `--no-deps`). Future SenseNova package installs must keep the Comfy CUDA wheel.

## Architecture (implemented)

- Family: `sensenova`
- Dock: `sensenova-u15-local`
- Label: `SenseNova U1.5` / `SenseNova U1.5 — Not Ready`
- CRS job: one native production sheet at 2720×1536 (`sensenova.crs`)
- ERS job: I2I only (`sensenova.ers`) with Atlas pixels
- Official nodes only: `SenseNovaU1LocalLoader`, `SenseNovaU1LocalTextToImage`, `SenseNovaU1LocalImageEdit`
- No KSampler graphs. No community GGUF. No SenseNova cloud API.

## Tests measured

```text
studio-api installer + adversarial: 15 passed
Playwright listing (:5173 → :8758, --grep lists/default): 2 passed
  CC Flux default (8.0s); ERS Qwen default (2.7s after one API timeout retry)
Live generate Playwright: not run
```

Playwright (added, not live-certified):

- `tests/e2e/sensenova/sensenova-character-creator.spec.ts`
- `tests/e2e/sensenova/sensenova-spatial-ers.spec.ts`

Creator UI: `http://127.0.0.1:5173` + Studio API `http://127.0.0.1:8758`. Retired `:8760` not used.

Lab IDs: `docs/release-gate/sensenova-u15/evidence/lab-ids.json`

## Review remediations

- **Kimi B1:** SenseNova / torch-pin installs write `requirements.adept-no-torch.txt` (drops torch/torchvision/torchaudio) and pass `--no-deps`. Regression `test_sensenova_install_cannot_reintroduce_torch_28_cpu` asserts pip never sees `torch==2.8.0`. `--no-deps` alone is insufficient because official requirements list torch as a direct pin.
- **Kimi B2:** `MiniGeneratorId` is `"qwen2512" \| "gpt-image-2"` only. `resolveReadyMiniGenerator("sensenova")` remaps to Qwen. Backend `scene_creator_mini.py` already refused SenseNova.
- **GLM refuse copy:** Character Sheet / scene-shot compile now names the pinned ERS graph (SenseNova vs Qwen) instead of always saying Qwen.
- **Weights:** Partial shards never report Ready. 12-of-13 and truncated-shard fixtures fail closed.

## Remaining blockers

1. **Official local loader host-RAM trap.** `SenseNovaU1LocalLoader` `from_pretrained` materializes U1.5-8B-MoT in CPU RAM (~40 GB) before any CUDA alloc. On this 63.5 GB workstation both official `fast` and `low` finish the 1116-tensor load, drop host free RAM below 1 GB, and never move tensors onto the RTX 5090. No smoke PNG. Do not `pip install -r` official requirements without the torch guard.
2. After a smoke image exists on GPU: Lab Mira native CRS (`sensenova.crs`) then Observatory ERS (`sensenova.ers` + Atlas `be0a9495`). Sequential. Lab only. Never Schnick / Korri / Venture.
3. Playwright live generate on `:5173` → `:8758` (skip, never silent-pass, when Not Ready / Atlas missing).
4. Defaults stay **REVERT** on all three surfaces until both live sheets pass.

Until those pass: SenseNova stays selectable Draft. Flux and Qwen remain the certified defaults. Discover/`executable: true` currently means **weights on disk**, not **this host can generate**.

## Default recommendation (binding)

**REVERT DEFAULT** for Character Creator, Spatial Map → ERS, and Scene Creator.

Allowed later only after both native sheets pass:

```text
GO — SENSENOVA U1.5 ADEPT UI CHARACTER CREATOR + ERS INTEGRATION CERTIFIED
```
