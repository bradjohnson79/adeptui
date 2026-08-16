# ERS 2K Production Context + CD → Scene Creator Handoff

**Date:** 2026-08-16  
**Branch:** `beta`  
**Starting SHA:** `32440eb`  
**Hosted UI:** `https://adeptui.vercel.app` (this feature certified against production `studio-web` dist preview `:4173`, not a new Vercel SHA)  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200**  
**Preview:** `http://127.0.0.1:4173/` with `STUDIO_API_PORT=8758`  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (reused; never `POST /api/projects`)

This is the single governing document for ERS 2K production context + Co-Director caption handoff (Law 30). It does **not** rewrite Add (`SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md`, still **NO-GO**) or Spatial Profile GO (`SCENE_SPATIAL_PROFILE_RESET_CERTIFICATION.md`).

Do not resurrect `:8760`. Do not lift ERS T2I law. Pass 2 Scene Creator workspace refinement is a sibling addendum after this verdict.

## Verdict

```text
GO — ERS 2K PRODUCTION CONTEXT + CD → SCENE CREATOR HANDOFF CERTIFIED END TO END
```

Independent visual (pixels, not metadata): environment-dominant Schnick café sheet at **2560×1440**; headings/labels readable; not a character turnaround. Qwen still painted extra figures into some environment panels despite compiler “environment-only” instructions — residual T2I layout obedience, not a silent model/path substitute.

## Phase 0 — native 2K gate

One live `qwen2512.txt2img` job at **2560×1440** (both ÷8).

| Field | Observed |
| --- | --- |
| Path | **Native** (not `image.upscale`) |
| Comfy prompt | `c56d7464-b10f-4e1b-af7e-922b89cb9b73` |
| Decode | success, PNG **2560×1440** |
| Duration | ~86s warm (execution_start → execution_success) |
| Peak VRAM | ~30385 MiB / 32607 MiB RTX 5090, no OOM |
| Artifact | `artifacts/scene-creator/ers-2k-probe/qwen_2560x1440_probe.png` |

Product lock: `build_ers_image_body` uses native 2560×1440. Other aspects use existing `compile.py` `_ASPECT` / `_RES_SCALE` `"2K"`. No sampler retune. No third size.

## What shipped

```text
Spatial Map placements (IDs)
  → one contextual ERS panel (environment + placed subjects)
  → native 2K Library composite (same sheetId)
  → POST production-handoff (existing)
  → Standard Scene Creator hydrate + CD caption
```

- Contextual subjects from **visible placements only** (identity **text** + `compile_structured_blocking`). Hero / N/E/S/W / materials / lighting stay environment-only in the compiler. No `if schnick`. No `referenceImage` on the ERS T2I body.
- IDs stamped on `creativeContext` / package metadata: `characterIds`, `propIds`, approved asset ids.
- `hydrate_workspace` adds `production_context` (`loaded` only after live pointer resolve). Caption under Spatial Profile dropdown: Loading / ✓ loaded / ⚠ failed. Reset hides caption. Reload recomputes from GET.

## Live Schnick identity (after 2K generate)

| Pointer | Value |
| --- | --- |
| sheetId | `db095959-5678-4f11-98d1-e93e0810d119` (frozen) |
| handoffId | `792376c5-013c-51dd-8d3a-dae5834ae77e` (stable) |
| sceneId | `e4550745-f0ef-44c8-99a5-ef9e20bd47d2` |
| spatialMapId | `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` |
| Korri | `c49371ed-ba6b-4c16-ba98-a8b28b72118b` |
| cup | `78c5be96-cd03-4969-9f8b-655fcefd28ea` |
| ersLibraryAssetId | `79a55177-10be-438b-9ae7-477c1781abe7` (new 2K master) |
| ersPackageId | `1c37496b-31a9-4115-9fb0-1b066f9729b3` |
| pixels | **2560×1440**, 4 984 931 bytes |
| job | `4aadf4c9-bad4-4e19-b11a-967db32dddf8` `qwen2512.txt2img` T2I |
| production_context.loaded | **true** |

Generate job prompt contained `Contextual production — occupied scale` and did **not** contain whole-sheet `Characters (scale / occupancy`.

## Tests

- `studio-api` `tests/test_ers_2k_context.py` + compiler + image-product + spatial-profile: **29 passed** (`24` ERS unit + `5` spatial profile)
- `studio-web` vitest `productionContextStatus.test.ts` + `sceneCreatorContracts.test.ts`: **12 passed**
- Playwright `tests/e2e/scene-creator/spatial-profile-reset.spec.ts` against `http://127.0.0.1:4173` + API `:8758`: **2 passed** (4.5s) — select → live hydrate → ✓ caption; Reset hides caption; reload stays empty; reselect hydrates; invalid profile never shows ✓

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Schnick Spatial Map → `ers.generate` (Qwen local) |
| Frontend | PASS — caption derived from hydrate, not dropdown |
| API | PASS — `qwen2512.txt2img` 2560×1440, `operation=image.generate` |
| Backend | PASS — compiler contextual panel + ID stamps |
| Persistence | PASS — sheet `ers_composite_asset_id` = 2K Library asset |
| Runtime | PASS — Comfy native 2K, no upscale, no silent substitute |
| Result | PASS — 2560×1440 PNG |
| Reload | PASS — `production_context.loaded` recomputed from GET |
| Downstream | PASS — handoff `ersLibraryAssetId` + Korri/cup/map/scene/profile IDs |

## Limitations

- Hosted Vercel SHA was not rebuilt for this caption; certification used dist preview `:4173` + live `:8758`.
- Qwen T2I does not perfectly confine figures to one panel. Compiler instructions are environment-only; residual extra people in some panels remain.
- ERS generate still allocates a new `package.id` per run; `sheetId` and handoffId stay stable; handoff pointers update to the new composite.
- Pass 2 (Korri provider reference, splitters, take delete, Preview in 3D Camera, measured accel) is **not** this document.

## Frozen / out of scope (unchanged)

Spatial Map architecture, ERS modal layout, Library architecture, Scene Creator redesign, Image Core rewrite, Add, Timeline, FLUX graph, `:8760`.
