# PoseCraft Production Master Program — Status Tracker

**Date opened:** 2026-08-04
**Authority:** `posecraft_production_master_program_fd11551a.plan.md`
**Baseline:** GREEN (see `POSECRAFT_PRODUCTION_CERTIFICATION.md` — v1.1 Promotion)
**Scope:** Quality + capability elevation of the already-promoted PoseCraft Babylon production workspace. This is **not** a second landing-page merge.

## Two separate verdicts (locked)

1. **PoseCraft Master Program** — `GO | CONDITIONAL | NO-GO` based on Master gates only (route, viewport + humans, integrity catalog ≥ 50, manipulation evidence, persistence + handoff, coffee-shop Master cert, compat). A PoseCraft-only quality defect must not be silently folded into an unrelated pipeline RED.
2. **Integrated product** — separately, after a fresh full creator-pipeline run: `GREEN | CONDITIONAL | RED`.

Expected outcome when Master gates pass and the baseline stays intact:

```text
GO — POSECRAFT MASTER PROGRAM READY
GREEN — ADEPT UI FULL CREATOR PIPELINE READY
```

## Master gap status (drivers)

| # | Gap | Today (GREEN baseline) | Master target | Phase todo | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Figures | Block-like procedural creatures (box segments + sphere head) | Readable low-poly adult/child male/female + joint hierarchy | `posecraft-human-figures` | ✅ done |
| 2 | Viewport | Narrow / constrained center; light blue gradient stage | ~18–20% / 60–64% / 18–20%; ~5% internal margins; gray matte stage; rule-of-thirds preserved | `posecraft-viewport-refinement` | ✅ done |
| 3 | Backward compat | No adapter; rig upgrade could orphan baseline scenes | Deterministic migration preserving IDs/revisions/transforms/camera/mappings/colors; unsupported joints → provenance | `posecraft-compat-gate` | ✅ done |
| 4 | Poses | ~8 text presets, no thumbnails | ≥ 50 integrity-gated visual poses (unique ID, distinct joints, real thumbnail, category, archetypes, title + description); scrollable pane; search/filters/favorites | `posecraft-pose-library` | ✅ done (56 poses) |
| 5 | Manipulation | Slider-only joint editing | Move / Rotate / Pose Body modes + in-canvas joint handles + root gizmos; ground snap; numeric alternatives; undo/redo | `posecraft-manual-controls` | ✅ done |
| 6 | UI persistence | Shell hydrates from per-project localStorage draft key; API is SoT but UI still writes localStorage | `PoseCraftWorkspace` save/load wired to `/api/posecraft/*`; retire localStorage as production SoT (session undo may stay client-side) | `posecraft-persistence` | ✅ done |
| 7 | Custom poses | Missing | Project-scoped custom pose CRUD + thumbnails; revisions | `posecraft-persistence` | ✅ done (M027 + CRUD endpoints) |
| 8 | Co-Director tools | 13 `posecraft.*` tools registered; `send_to_image_pipeline` exists; no `send_to_storyboard` | Expand `posecraft.*` incl. `send_to_storyboard`; `creatorModified` protection; honesty label | `posecraft-codirector` | ✅ done (14 tools) |
| 9 | Storyboard handoff | Direct tool incomplete | `posecraft.send_to_storyboard` + package preserving scene/revision/preview/camera/mappings | `posecraft-image-pipeline` | ✅ done |
| 10 | Thumbnails | None (text-only pose cards) | Build-time render from canonical pose data → WebP/AVIF; lazy thumbs (no 50 live Babylon thumbnail scenes) | `posecraft-image-pipeline` | ✅ done (SVG, 56 on disk) |
| 11 | Coffee cert | Coffee-shop GO on current (block-figure) quality | Master scenarios A–K (humans, ≥ 50 poses, thumbnails, joint handle + root gizmo, table block, custom pose, Storyboard, isolation) | `posecraft-coffee-cert` | ✅ live Master A–K passed |
| 12 | Runtime gates | :8188 / :8192 preserved | Preserve `:8188` probe/reuse/`ADEPT_COMFY_LAUNCH`/`IMAGE_RUNTIME_STARTUP_FAILED`; separate `:8192` H3; never substitute | `posecraft-runtime-hardening` | ✅ done (locked by test + live) |
| 13 | Tests | Unit (sceneState 5/5) + API contracts (8/8) | Add catalog integrity count, compat migration, manipulation save/reload; full pipeline rerun with Master-quality staging | `posecraft-full-pipeline-rerun` | ✅ FE 20/20, API 14/14; full pipeline live GREEN |
| 14 | Verdict | n/a (program not started) | Master GO + integrated GREEN | `posecraft-final-verdict` | ✅ Master GO · integrated GREEN (see amalgamated report) |

## Out of scope (enforced)

SceneCraft, detailed furniture, mesh import, mocap/animation/facial/cloth, photoreal/final render in PoseCraft, public MiniMax/Best Match, CUDA/downloads, Home/ERS/Timeline redesign.

## Implementation order (locked)

0. Doc reconciliation (this doc) → 1. Merge review → 2. Canonical route audit → 3–4. Viewport → 4.5 Compat gate (BEFORE rig/catalog) → 5. Human figures → 6–11. Pose library → 12–14. Manual controls → 15–20. Persistence + API → 21–23. Co-Director + handoffs → 24–28. Coffee cert + UX/a11y/perf → 29. Runtime → 30–34. Tests, full pipeline, dual verdict.

## Update log

- 2026-08-04 — Program opened. Baseline reconciled to GREEN; historical RED labeled historical. Master gap table initialized (all pending). Doc reconciliation phase complete.
- 2026-08-04 — Merge review + canonical route audit complete (artifacts under `artifacts/`). Viewport refined (19/62/19 grid, 5% margins, gray matte stage). Compat gate shipped (schemaVersion 1→2 migration, TS + Python, tested). Human figures upgraded (capsule limbs, tapered torso, neck cylinder; joint hierarchy preserved). Pose library: 56 integrity-gated poses with real matching SVG thumbnails, scrollable pane, search/filters/favorites; integrity test green. Manual controls: Move/Rotate/Pose Body gizmos + pickable joint handles + root drag; manipulation round-trip test green. Persistence: PoseCraftWorkspace wired to `/api/posecraft/*` (no localStorage SoT); M027 `posecraft_custom_poses` migration + custom pose CRUD endpoints + UI save/delete; API test green. Co-Director: `posecraft.send_to_storyboard` added (14 tools), honesty-labelled handoff, approval-gated; API test green. Image pipeline: build-time thumbnail pipeline (vitest) writes 56 SVGs on disk; lazy inline thumbnails (no live Babylon thumbnail scenes). Coffee cert spec upgraded with Master A–K scenarios (run requires live stack). Runtime gates locked by test (:8188 Comfy / :8192 H3, never substitute). Final unit evidence: FE posecraft 20/20, API posecraft 14/14.
- 2026-08-04 — Verdict: **GO — POSECRAFT MASTER PROGRAM READY**. Integrated: **GREEN — ADEPT UI FULL CREATOR PIPELINE READY** (both live-proven). Amalgamated status: `POSECRAFT_AMALGAMATED_REPORT.md`.
