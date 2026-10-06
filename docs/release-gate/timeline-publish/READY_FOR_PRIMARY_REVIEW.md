# READY_FOR_PRIMARY_REVIEW — Timeline Publish + MAGI

> **SUPERSEDED for MAGI full-scene upscale (targets, persist, Library fail-closed, live 12B).**  
> Current governing report: [`MAGI_VIDEO_UPSCALER_PRODUCTION_CONVERGENCE.md`](MAGI_VIDEO_UPSCALER_PRODUCTION_CONVERGENCE.md).  
> This file remains historical for Timeline Publish chrome and Venture Corridor Dialogue Playwright A–E.

**When (PT):** 2026-09-13 ~19:45 PT  
**Machine:** BRAD-5090  
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio` @ branch `feat/character-creator-final-closure`  
**Evidence:** `C:\Users\bradj\theme_walk\timeline_publish\`  
**Binary readiness:** **READY**  
**Architecture:** **GO** (live E2E proven)

---

## 1) AUDIT summary (from AUDIT.md)

Pre-implement inventory found Final Check lifecycle, multi-batch stitch, Timeline editability, vacuous no-auto-publish, and GENERATE SCENE idle-hide **DONE**. Missing were Preview Monitor PUBLISH/UPSCALE, publish readiness gate, Library Video Published Master + provenance, Changes Pending / UPDATE PUBLISHED, Timeline-scoped MAGI full-stitch entry, published-master accepted-issues honesty, and Playwright coverage.

**Audit count then:** DONE 6 / MISSING 8 (publish+MAGI product gaps).

Out of scope (honored): no Final Check / Dialogue Authority rewrite; no 12B media touch; no GENERATE SCENE overlay rewrite.

---

## 2) IMPLEMENT summary

Implemented additive Timeline Publish + MAGI on Preview Monitor chrome + BE routes:

- Readiness gate on `SCENE_FINISHED` / `SCENE_FINISHED_WITH_ACCEPTED_ISSUES` + stitch
- Explicit `POST .../publish` → Library `video_published_master` + provenance snapshot
- Dirty detect → Changes Pending + UPDATE PUBLISHED (versioned)
- `POST .../magi-upscale` full-stitch allow-list only; **never** auto-publishes
- FE chrome in `LivePreviewMonitor` publish bar; unit + Playwright coverage

VCD left restored for creator click-test: FC `SCENE_FINISHED`, original stitch, `scenePublish=null`.

### Test results (live)

| Suite | Result |
|-------|--------|
| pytest `tests/test_scene_publish.py` | **10 passed** |
| vitest `scenePublish.test.ts` | **7 passed** |
| Playwright `timeline-publish-magi-cert.spec.ts` (ADEPT_BETA_TARGET=1, chromium) | **6 passed** (A–E + MAGI 2-batch) |

Evidence JSON: `theme_walk/timeline_publish/playwright_artifacts/` and `docs/release-gate/timeline-publish/artifacts/`.

### Live E2E proof points

- **A** CTA gating on Preview Monitor (hidden → visible)
- **B** Refuse before PASS (`NOT_PUBLISH_READY`)
- **C** Publish register + Published badge + mp4 file 200
- **D** Changes Pending + UPDATE → version 2
- **E** MAGI batch blocked; full-stitch ok; `autoPublished=false`
- **MAGI 2-batch** VCD has 3 batches; batch-2 asset blocked

---

## 3) Architecture verdict

**GO** — live Playwright E2E against Adept Beta (`127.0.0.1:5173` / `:8758`) on **Venture Corridor Dialogue** proved the publish/MAGI product path end-to-end. Unit gates + API smoke + creator click-test fixture align.

### Non-blockers / follow-ups

- Surface MAGI `jobId` when `upscaledAssetId` is still null (async job)
- Optional human click for UX placement polish
- Commit only mission paths (see IMPLEMENT.md hygiene) — mixed dirty tree

### Hard blockers for GO

**None** for Architecture GO (live E2E proven).

### Still forbidden

- Touch GENERATE SCENE overlay / `sceneRenderProgress.ts`
- Rewrite Final Check
- Overwrite 12B media
- `git add -A`

---

## 4) READY / NOT READY

**READY** for Primary review.