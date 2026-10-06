# Spatial Map Dual-Input + Co-Director Atlas Generation

**HISTORICAL — superseded for Atlas generation.** This report covers the old
single-prompt `qwen2512.ref` I2I path. Current governing document:

`docs/release-gate/spatial-map/SPATIAL_RECONSTRUCTION_COMPILER_CERTIFICATION_REPORT.md`

## Verdict

`NO-GO — FULL-STACK E2E NOT VERIFIED`

Option 1 Library/Upload were not re-certified after the overlay unmount repair. Further live Atlas generation was stopped on owner instruction. Internal routing, source, I2I, Option 2 assign, and the overlay root cause are repaired in source.

## Branch

- Branch: `feat/character-creator-final-closure`
- HEAD at report time: `b6156455e643d5fa430784b3130756f2d8038651` plus uncommitted Atlas work
- Project: SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`
- Local review: Vite `http://127.0.0.1:5173/`, Studio API `http://127.0.0.1:8758/`

## Root cause (measured)

The live “use library image as a reference to create an atlas (top down shot)” hang was `character.assign_reference`, not a Comfy timeout.

1. Atlas phrases required consecutive `atlas shot`. `atlas (top down shot)` missed.
2. Later `use … reference` matched `character.assign_reference` (TOOL / PREVIEW). No image job.
3. Stream ended with no `executionCreated` → “The response ended unexpectedly.”
4. Even a correct `atlas.generate` dropped Library tags (`attachment_asset_ids` overwritten by an empty top-level list).
5. **Option 1 UI / grid:** starting Atlas set `agent_work`, which covered Spatial Map and **unmounted** `SpatialMapPanel`. Assignment and `active-atlas-panel` could not appear. The overlay also paused polling after ~4 minutes while Comfy was still queued.

## Source repairs

- Shared generate-vs-assign intent: `atlas_intent.py` (generate wins over assign-reference).
- Library tag / id / “that corridor” resolve: `atlas_source.py` + `_enrich_execution_context`.
- Pixel classify + Option 2 auto-route to generate when confident: `atlas_classify.py`.
- I2I when a source exists; refuse T2I if source was requested: `atlas_generate.py`. Project-owned sources only.
- `start_execution` keeps `context.attachment_asset_ids` (`merge_start_execution_attachments` + `attachmentAssetIds` alias).
- Dual-input starter: `SpatialMapStartChooser` (Express and Standard share `SpatialMapPanel`).
- **Atlas/ERS keep Spatial Map mounted:** `keepSpatialMapDuringExecution` — no covering overlay for `atlas.generate` / `atlas.assign`.
- Overlay poll budget for Atlas is ~15 minutes; on complete it can still assign if the overlay is showing for another reason.
- Chat cards dedupe by `execution_id`. Failed assign-reference copy is Atlas generation failure, not “response ended unexpectedly.”

## Evidence

| Gate | Result |
|---|---|
| Intent / source / I2I / classify unit | **12 passed** (`test_atlas_intent_and_source.py`, `test_atlas_classify.py`, `test_atlas_generate_i2i.py`) |
| Frontend unit | **35 passed** (Spatial Map panel, overlay helper, liveExecutionSync, AgentWorkSurface) |
| Chat phrasing Playwright | **PASS** — stream is `atlas.generate`, never `assign_reference` |
| Dual-input empty state Playwright | **PASS** |
| Option 2 Library Playwright | **PASS** (3.2s) — assign, no generation |
| Option 2 Upload Playwright | **PASS** (2.7s) — assign, no generation |
| Live corridor I2I (API/Comfy) | **Observed** — several `atlas.generate` completed with source `1211dd83-e3f6-4d17-bf2b-669ec5961418` (`codirector_image_generate_d5d616be`); Comfy ran `qwen_image_2512` |
| Corridor classify | `perspective_environment` → `generate`, `pixelsRead: true`, 1280×720 |
| Option 1 Library/Upload Playwright grid | **NOT RE-VERIFIED** after overlay unmount repair (no further live generation) |
| Character Creator / Prop Creator knobs | Unchanged |

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | PASS (dual-input + chat phrasing) |
| Frontend | PASS (shared starter; Atlas no longer covered by overlay) |
| API | PASS (`atlas.generate` / `atlas.assign`) |
| Backend | PASS (I2I + refuse T2I) |
| Persistence | PASS for Option 2 assign |
| Runtime | PASS observed Comfy Qwen I2I for corridor source |
| Result | PASS for completed Atlas assets; Option 1 grid not re-run |
| Reload | PASS Option 2 |
| Downstream | N/A (grid after assign) |

## Auditors / peers

- Spatial Map auditor (Kimi 2.7): BLOCK on assign-reference copy — repaired (misroute stays generation failure; `atlas.assign` has its own copy).
- Atlas/Comfy auditor (Kimi 2.7): BLOCK on assign→generate auto-route — **rejected**; plan Phase 4 requires confident Option 2 perspective to auto-route to the same `atlas.generate`.
- GLM 5.2 peer: **PASS**
- Kimi K3 peer: BLOCK on dead `atlas.assign` branch + missing generate ownership check — **repaired**, then **PASS**

## Remaining for GO

Re-run Option 1 Library and Option 1 Upload **once** against this overlay fix (no extra generate loops). Visual inspect the derived Atlas. Then the required verdict can be issued:

`GO — SPATIAL MAP EXPRESS/STANDARD DUAL-INPUT + CO-DIRECTOR ATLAS GENERATION LIVE E2E CERTIFIED`
