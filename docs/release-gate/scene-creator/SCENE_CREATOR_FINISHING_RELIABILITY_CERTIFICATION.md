# SCENE CREATOR FINISHING & RELIABILITY — GOVERNING CERTIFICATION

> **HISTORICAL (Law 30).** This document is no longer the governing Scene Creator cert. Governing document: `SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md`. Do not recertify from this file. The NO-GO verdict below is unchanged.

**Date:** 2026-08-15  
**Branch:** `beta`  
**HEAD SHA:** `513fa8c6a1e8cb78c9d85b213ff750707cc96954`  
**Remote SHA:** `513fa8c6a1e8cb78c9d85b213ff750707cc96954` (`origin/beta`)  
**Hosted UI:** `https://adeptui.vercel.app` bundle `assets/index-M2NNmW2e.js` (frontend unchanged after spec/registry-only commits)  
**Studio API:** `http://127.0.0.1:8758/` via `https://api-beta.adeptui.org` — `/api/health` **ok**  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Shot:** `2a58894b-b5d4-4e86-b068-7cd156199d98` (Shot 3)

This is the single governing document for this milestone (Build Law 30). It does **not** supersede `SCENE_CREATOR_CINEMATOGRAPHER_SYSTEM_CERTIFICATION.md` or `SCENE_CREATOR_3D_CAMERA_ORIENTATION_CERTIFICATION.md` (those GOs remain historical).

`qwen.edit` stays unpublished. Do not resurrect `:8760`. Never `POST /api/projects`.

## Verdict

```text
NO-GO — SCENE CREATOR FINISHING & RELIABILITY NOT CERTIFIED END TO END
```

Blockers (any one is enough):

1. **Z-Image native inpaint Modify / Replace pixel quality FAIL** on the default local family. Tight face masks hit Output Gate; larger face masks destroy identity (fur / unblended patch). Cup Replace produced a double-mug or grey smear. **FLUX Image Edit** (`flux.img2img`) produced a usable irritated expression and a clean teal-mug Replace. Default Shot 3 family remains Z-Image; silent family swap is forbidden.
2. **Final Quality Render inheritance not live-proven after `zimage.ref_edit` recertify.** Job `09e9e751` used the correct Strategy A source (`18bb0bcd`, FLUX Replace) then died on `WORKFLOW_GRAPH_DRIFT` (`c8c2c11c` vs `da4fa8d4`). Registry was recertified to `da4fa8d4` in `513fa8c`. The follow-up hosted Playwright Final test then sat 9.1 minutes on **Approve / Lock Camera** disabled because C1 preview failed: *Qwen Image 2512 has no certified image-to-image / edit workflow. Refusing silent substitute of zimage.ref_edit.*
3. **Independent verifier cannot issue PASS** while pixel Modify/Replace on the default inpaint path and a completed inherited Final are missing.

No Conditional GO.

## Scope implemented

| Area | Status |
|---|---|
| Operation profiles (Remove 0.85/6, Modify 0.82/8, Add 0.94/12, Replace 0.90/8) | IMPLEMENTED |
| Mask coverage gate `< 0.4%` | IMPLEMENTED |
| Expand Tight/Normal/Wide → `grow_mask_by` 2/6/14 | IMPLEMENTED |
| Feather Hard/Soft → export 0/8 | IMPLEMENTED |
| Output Gate creator copy (threshold still 2.0) | IMPLEMENTED and **hosted-visible** |
| Structured `creativeContext.cinematographer` on job params | IMPLEMENTED |
| Candidate lineage IDs + superseded-not-deleted | IMPLEMENTED |
| In-flight frontend + backend idempotency | IMPLEMENTED |
| T2I preflight / Z-Image+FLUX recommend / no `qwen.edit` | IMPLEMENTED (Qwen T2I refused; no silent `zimage.ref_edit` substitute) |
| Labels, compare-with-source, failed Retry/Details | IMPLEMENTED |
| `zimage.inpaint` denoise/grow volatile (earlier `5f6554e`) | IMPLEMENTED |
| `zimage.ref_edit` graphHash recertify after VAEEncode latent path (`513fa8c`) | IMPLEMENTED — **not live-replayed to a complete Final asset** |

## Unit / integration

| Suite | Result |
|---|---|
| `pytest tests/test_scene_creator_region_edit.py tests/test_cinematographer.py tests/test_cinematographer_orientation3d.py` | **49 passed** (earlier this milestone) |
| `pytest studio-api/tests/test_m42_w2_image_runtime.py::test_zimage_inpaint_denoise_and_grow_are_not_graph_drift` + `test_zimage_ref_edit_matches_certified_graph_after_latent_path` | **2 passed** |
| `vitest` Scene Creator regionEdit + contracts + cameraCommandEngine | **39 passed** |

## Playwright (hosted, real runtime)

Suite: `tests/e2e/scene-creator/scene-creator-finishing-reliability.spec.ts`

```text
PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app
STUDIO_API_BASE=https://api-beta.adeptui.org
```

Do **not** use `ADEPT_BETA_TARGET=1` (maps to retired `:8760`).

Latest **full** run (`249983`): **16 passed, 3 failed** (accordion STUDIO_API_OFFLINE flake; duplicate preview 0 POSTs while Generating; Final 0 POSTs while reconnecting).

After wait/retry + idle-button repairs (`3058d3a`, `513fa8c`):

| Test | Isolated re-run |
|---|---|
| 3D and Inpaint accordions open together | PASS |
| duplicate preview click enqueues exactly one job | PASS (`249989`) |
| Final Quality Render inherits latest approved edit | **FAIL** — lock stayed disabled 540s (C1 preview failed on Qwen, no silent fallback) |

Playwright path coverage that did pass in the full hosted run: load, C2↔C3 sync, 3D orientation, zoom vs dolly, low-res preview, inpaint overlay, too-small mask, Expand/Feather payload, Remove/Modify/Add/Replace **enqueue**, model guard, Library/Timeline, reload, Spatial Map, failure UI, console/network.

## Visual / pixel review

Evidence under `docs/release-gate/scene-creator/evidence/finishing/` (local PNGs; do not commit bloat).

| Op | Source | Model | Job | Result |
|---|---|---|---|---|
| Modify (face, 6.15% mask) | Take B `e0d3af5e` | `zimage.inpaint` denoise 0.82 grow 2 | `69d7fdca` | **FAIL** — fur / unblended oval over eyes |
| Modify (brows, 2.45% mask) | Take B | `zimage.inpaint` | `16e0d811` | **FAIL** — Output Gate, creator copy shown |
| Modify (expression) | Take B | `flux.img2img` `kontext-dev` | `ecc004be` asset `166470b4` | **PASS with artifacts** — clear irritated glare, identity mostly held |
| Add pastry left of cup | Take E `b0bd03c3` | `zimage.inpaint` denoise 0.94 | `eafc786e` asset `04d8cb4d` | **PASS** — pastry in corner, cup/hand intact |
| Replace (wide mask) | Take E | `zimage.inpaint` | `1a542eac` | **FAIL** — double mug |
| Replace (tighter) | Take E | `zimage.inpaint` | `811f30d3` | **FAIL** — grey smear |
| Replace | Take E | `flux.img2img` | `c0420da3` asset `18bb0bcd` | **PASS** — one teal mug, same hand/coffee |

Hosted cursor-ide-browser: Shot 3 Standard strip, **Inpaint Z — Replace · Approved** shows FLUX teal mug (`Source: Take E · Edit: Replace · Model: FLUX`). Failed-card copy matches Output Gate. C1 tile shows Qwen refusal (no silent Z-Image substitute).

Cascade Final pixels: **NOT VERIFIED**. Failed job `09e9e751` had the right `source_asset_id=18bb0bcd` and `zimage.ref_edit` Strategy A before graph drift.

## Certification matrix

| Gate | Result |
|---|---|
| Unit tests | PASS |
| Backend integration | PASS |
| Playwright Scene Creator UI | PASS (latest full run, minus load flake) |
| Playwright real local runtime | PARTIAL — preview/ops jobs run; Final not complete after recertify |
| Camera / 3D synchronization | PASS |
| Region Edit operations | PATH PASS / **PIXEL FAIL on Z-Image Modify+Replace**; FLUX Modify+Replace PASS; Z-Image Add PASS |
| Duplicate-submit protection | PASS (preview isolated + unit) |
| Model guard | PASS (no `txt2img`; Qwen edit refused) |
| Final inheritance | PATH PARTIAL (correct source on failed job) / **LIVE COMPLETE FAIL** |
| Persistence/reload | PASS |
| Library | PASS |
| Timeline | PASS |
| Manual visual review | **FAIL** (default Z-Image Modify/Replace); FLUX path shown hosted |
| Independent verifier | **FAILED** — [SC finishing independent verifier](cbfc557b-a094-474d-b290-d63ee68c9d40): `FAILED — Z-Image default Modify/Replace pixels fail (fur oval / broken mug); Final inheritance not live-complete (job 09e9e751 WORKFLOW_GRAPH_DRIFT; hosted Playwright Final lock disabled 540s after Qwen C1 preview refusal; no Final asset)` |

## Independent verifier

[SC finishing independent verifier](cbfc557b-a094-474d-b290-d63ee68c9d40) — no product edits.

```text
FAILED — Z-Image default Modify/Replace pixels fail (fur oval / broken mug); Final inheritance not live-complete (job 09e9e751 WORKFLOW_GRAPH_DRIFT; hosted Playwright Final lock disabled 540s after Qwen C1 preview refusal; no Final asset)
```

Prompt-only Final is FAIL. Verifier required Playwright matrix + runtime IDs + visual review.

## Remaining before GO

1. Either make Z-Image inpaint identity-safe for Modify/Replace **or** make FLUX the creator-visible recommended/default for those ops without a silent swap.
2. Live Final Quality Render after `513fa8c`: lock C1 on a **Z-Image** preview (do not leave Qwen selected), Strategy A from approved FLUX/Z-Image edit, complete asset, inherited pixels.
3. Hosted Playwright Final green with `status=complete` and `asset_id`.
4. Independent verifier PASS on Playwright matrix + runtime IDs + pixels.

## Topology

```text
https://adeptui.vercel.app
→ https://api-beta.adeptui.org
→ Studio API :8758
→ Comfy / local image runtime
```
