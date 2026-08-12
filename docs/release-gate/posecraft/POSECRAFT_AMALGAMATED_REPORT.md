# PoseCraft — Amalgamated Report

**Date:** 2026-08-04  
**Product:** Adept UI PoseCraft (Babylon.js 3D staging)  
**Authority:** This document is the single amalgamated status for PoseCraft. Detail docs and the implementer handoff are evidence only; they must not contradict **CURRENT AUTHORITATIVE STATUS** below.

---

## CURRENT AUTHORITATIVE STATUS

```text
GO — POSECRAFT MASTER PROGRAM READY
```

> **Governing status** is the most restrictive open program. The Final Mandatory GO program for
> human figures is now independently verified **GO** (all gates PASS — see **Final Mandatory GO
> Independent Verification** below). The **PoseCraft Snapshot Workflow** capability remains
> independently verified **GO** (see **Snapshot Workflow status** below).

**Implementation status:** IMPLEMENTED — Final Mandatory GO program (figures, cast UX, walls, custom import, storyboard) is implemented and uncommitted on `feature/ai-guided-setup`. Prior Master GO suspension is **lifted**.

**Independent verifier verdict (glm-5.2, non-implementer — 2026-08-04, re-verification):** GO. The Final Mandatory GO Playwright spec was re-run independently against live Beta (exit code 0; 1 passed in 4.1m). All ten gates PASS: D1–D4 (low-poly human figure models), D5 (figure context menu — rename debounce race resolved), D6 (Delete/Backspace cross-platform contract), FURN (walls + window walls — accordion hydration race resolved), IMPORT (custom OBJ → project Library, transform persists), STORY (storyboard package preserves figures + customs + furniture + camera), COFFEE (coffee-shop certification). Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never mutated (404). Full evidence: [`POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md).

> **Prior NO-GO superseded:** The earlier 2026-08-04 independent verification (NO-GO at FURN,
> deterministic) is retained in **Historical Certifications** for audit trail only. The
> implementer subsequently repaired the Furniture accordion hydration race and the D5 rename
> debounce race (`mutateAndFlush`); this re-verification confirms all gates PASS.

The historical pipeline GREEN and prior Master GO remain in **Historical Certifications**. Viewport layout (Gates A–C shell) is **accepted — no further layout work**.

### Snapshot Workflow status (capability — independently verified GO)

```text
GO — POSECRAFT SNAPSHOT AND PRODUCTION HANDOFF READY
```

**Independent verifier verdict (glm-5.2, non-implementer — 2026-08-04):** GO. The PoseCraft Snapshot Workflow Playwright spec (`tests/e2e/posecraft/posecraft-snapshot-workflow.spec.ts`, Scenarios A–F) was re-run independently against live Beta (exit code 0; 1 passed in 33.8s). All eight snapshot gates PASS: capture matches viewport camera (SNAP-1), clean capture excludes editing UI (SNAP-2), rename/duplicate/delete (SNAP-3), scene revision provenance with frozen composition + honesty label `PoseCraft Snapshot — Visual Staging Reference` (SNAP-4), gated Co-Director handoff (SNAP-5), gated Image Generation handoff (SNAP-6), gated Storyboard handoff (SNAP-7), and multiple-snapshot independence (SNAP-8). Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never mutated (404 on this Beta — vacuously satisfied). Full evidence: [`POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md).

> This GO is scoped to the Snapshot Workflow capability only. The Final Mandatory GO program for
> human figures is now also independently verified **GO** (see **CURRENT AUTHORITATIVE STATUS**
> above and the **Final Mandatory GO Independent Verification** section). Both statuses are GO.

### Gate matrix (Final Mandatory GO program)

| Gate | Scope | Result | Independent Verify |
| --- | --- | --- | --- |
| D1 | Adult Male low-poly v2 model | PASS | PASS |
| D2 | Adult Female low-poly v2 model | PASS | PASS |
| D3 | Child Boy / Child Girl low-poly v2 models | PASS | PASS |
| D4 | Same-color silhouette distinction (male≠female, boy≠girl) | PASS | PASS |
| D5 | Figure context menu (Rename / Duplicate / Delete) | PASS | PASS (rename debounce race resolved) |
| D6 | Delete / Backspace cross-platform keyboard contract | PASS | PASS |
| FURN | Walls + Wall-with-Window (S/M/L) | PASS | PASS (accordion hydration race resolved) |
| IMPORT | Custom figure import (OBJ/FBX/glTF/GLB → project Library) | PASS | PASS (transform persists) |
| STORY | Storyboard / Image package preserves figures + customs + furniture + camera | PASS | PASS |
| COFFEE | Coffee shop cert (male+female+medium table+2 chairs+wall-window-medium) | PASS | PASS |

> **Independent verifier sign-off:** GO. A separate `glm-5.2` non-implementer verifier re-ran the
> Final Mandatory GO Playwright spec against live Beta (exit 0; 1 passed in 4.1m). All ten gates
> PASS with full artifact evidence. The prior deterministic FURN FAIL (accordion hydration race)
> and D5 rename debounce race are resolved. The verifier did not implement or repair; the
> implementer cannot self-certify. Full evidence: [`POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md).

---

## Implementation evidence (Mandatory GO Corrective)

| Gate | Topic | Implementer artifacts |
| --- | --- | --- |
| A | Viewport metrics @1920×1080 + fullscreen | `A-layout-default.json`, `A-fullscreen.json/.png` |
| B | Resizable panes + collapse | `B-divider-drag.json`, `B-layout-collapsed.json`, `B-both-collapsed.png` |
| C | Accordions | `C-accordions.json` |
| D | Adult male/female distinct humans | `D-figures.json`, `D-two-figures.png` |
| E | Six staging colors | `D-figures.json` (colorOptions=6) |
| F | Real 3D gizmos + pointer drag | `F-move-before/after.json/.png`, `F-move-debug.json`, `F-pose-before/after.json/.png`, `F-pose-debug.json` |
| G | Professional pose library UI | `G-pose-library.json` (totalPoses≥50) |
| H | Furniture | `H-furniture.json`, `H-furniture.png` |
| I | Persistence (layout + furniture) | `I-reloaded-doc.json`, `I-persistence.json` (layoutPrefs=true) |
| J | Playwright live | `J-per-gate-verdict.json`, `J-master-verdict.txt` (all PASS) |

Artifact root: `docs/release-gate/posecraft/artifacts/mandatory-go-corrective/POSECRAFT-MANDATORY-GO-2026-08-04T20-41-37-498Z/`

Focused spec: `tests/e2e/posecraft/posecraft-mandatory-go-corrective.spec.ts`

---

## Independent Verification (glm-5.2-high, non-implementer — 2026-08-04)

**Beta probe (verifier):** `curl.exe` → Web `http://127.0.0.1:8760/` = **200**; API `http://127.0.0.1:8758/` = **200**; `/api/projects` = **200**. Beta live; no restart required.

**Independent Playwright re-run (verifier's own):**

```bash
ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 \
  STUDIO_API_BASE=http://127.0.0.1:8758 \
  npx playwright test tests/e2e/posecraft/posecraft-mandatory-go-corrective.spec.ts \
  --project=chromium --reporter=list --workers=1 --retries=0
```

Result: `1 passed (38.4s)` — **exit_code=0**

Verifier's own artifact run: `docs/release-gate/posecraft/artifacts/mandatory-go-corrective/POSECRAFT-MANDATORY-GO-2026-08-04T20-44-09-462Z/`

**Per-gate independent verdict (verbatim):**

```text
Gate A — PASS
Gate B — PASS
Gate C — PASS
Gate D — PASS
Gate E — PASS
Gate F — PASS
Gate G — PASS
Gate H — PASS
Gate I — PASS
Gate J — PASS

GLM 5.2 INDEPENDENT VERIFIER — ALL MANDATORY POSECRAFT GATES PASSED
```

**Key verifier measurements (own run):**

| Gate | Measurement | Verifier value |
| --- | --- | --- |
| A | default viewport % / fullscreen % | 0.6404 / 1.0 |
| B | divider drag ΔW / collapsed % | 320→400 (dragged=true) / 0.9659 |
| D | archetypes | [adult-male, adult-female] |
| E | colorOptions | 6 |
| F (move) | position.x before→after / moveCount / gizmo | 0 → 1.2 / 12 / move·x (down+up) |
| F (pose) | head joint before→after / moveCount | {0,0,0} → {24,0,36} / 22 |
| G | totalPoses | 56 |
| H | furniture kinds | [table-medium, block-chair, block-chair] |
| I | figures / primitives / layoutPrefs | 2 / 3 / true |

Full report: [`POSECRAFT_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md)

**Master verdict (independent, historical):** `GO — POSECRAFT MASTER PROGRAM READY` (superseded — see Historical Certifications)

---

## Final Mandatory GO Independent Verification (glm-5.2, non-implementer — 2026-08-04, re-verification GO)

> This section supersedes the prior NO-GO verification (retained in Historical Certifications).
> The implementer repaired the Furniture accordion hydration race and the D5 rename debounce
> race (`mutateAndFlush`) after the prior NO-GO; this re-verification confirms all gates PASS.

**Beta probe (verifier):** Web `http://127.0.0.1:8760/` = **200**; API `http://127.0.0.1:8758/api/health` = **200**. Beta live; no restart required. The freshly rebuilt `studio-web/dist` (built 2026-08-04 16:02, after the latest `PoseCraftWorkspace.tsx` source change at 16:00) is served by the Beta web server.

**Protected project:** `77a4b96c-8e3f-4501-897c-51bab99bedb7` probed → `404 {"detail":"Project not found"}`. Never created or mutated on this Beta instance; the spec reads it via `getJson(...).catch(() => null)` and never writes to it.

**Independent Playwright re-run (verifier's own, one clean run per instructions — first run non-flaky):**

```powershell
$env:ADEPT_BETA_TARGET="1"; $env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:8760";
$env:STUDIO_API_BASE="http://127.0.0.1:8758";
npx playwright test tests/e2e/posecraft/posecraft-final-mandatory-go.spec.ts `
  --project=chromium --workers=1 --retries=0
```

| Run | Started (UTC) | Duration | Exit code | Result |
| --- | --- | --- | --- | --- |
| 1 (verifier) | 2026-08-04T23:06:09Z | 4.1m (247.3s) | **0** | 1 passed |

**Playwright exit code: 0.** The spec reached the end and emitted `master-verdict.txt = "GO — POSECRAFT LOW-POLY HUMAN FIGURE MODELS READY"`.

**Per-gate independent verdict (verbatim):**

```text
Gate D1 — Adult Male Human Model: PASS
Gate D2 — Adult Female Human Model: PASS
Gate D3 — Child Human Models: PASS
Gate D4 — Same-Color Silhouette Distinction: PASS
Gate D5 — Figure Context Menu: PASS
Gate D6 — Delete/Backspace Cross-Platform Contract: PASS
Gate FURN — Walls and Wall-with-Window: PASS
Gate IMPORT — Custom Figure Import: PASS
Gate STORY — Storyboard Handoff Preserve: PASS
Gate COFFEE — Coffee Shop Certification: PASS

GO — POSECRAFT MASTER PROGRAM READY
```

**Key verifier measurements (own run):**

| Gate | Measurement | Verifier value |
| --- | --- | --- |
| D1–D3 | archetypes in scene | [adult-male, adult-female, child-boy, child-girl] |
| D1–D4 | modelIds | [adult-male-lowpoly-v2, adult-female-lowpoly-v2, child-boy-lowpoly-v2, child-girl-lowpoly-v2] |
| D4 | jointCount / bodyRegions / legacyBlockModel | 17 / 17 / false (all four figures) |
| FURN | primKinds / allWallsPresent | [wall-small, wall-medium, wall-large, wall-window-small, wall-window-medium, wall-window-large] / true |
| D5 | rename / duplicate / delete | "Eli"→"Eli Renamed" / 4→5 (dupId) / dup gone (count=4) |
| D6 | keyboard delete figure / furniture / blocked in input | kidGone / furnitureGone / stillThere |
| IMPORT | customAssetId / transform persist (reload) | 04cea7ee-… / position.x=1.5, rotationY=30, scale=1.2 |
| STORY | figures / furnitureKinds / lensMm / aspect | 4 (archetype+custom, hasPose) / walls+table+chairs / 35 / 16:9 |
| COFFEE | hasMaleFemale / figureCount / furniture | true / 4 / wall-window-medium + table-medium + 2×block-chair |

Verifier artifact run: `docs/release-gate/posecraft/artifacts/final-mandatory-go/POSECRAFT-FINAL-MANDATORY-GO-2026-08-04T23-09-34-803Z/`
Console log: `docs/release-gate/posecraft/artifacts/final-mandatory-go/verifier-run-3.log`

Full report: [`POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_FINAL_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md)

**Master verdict (independent, current):** `GO — POSECRAFT MASTER PROGRAM READY`

---

## PoseCraft Snapshot Workflow Independent Verification (glm-5.2, non-implementer — 2026-08-04)

**Beta probe (verifier):** Web `http://127.0.0.1:8760/` = **200**; API `http://127.0.0.1:8758/` = **200**; `/api/health` = **200**. Beta live; no restart required.

**Protected project:** `77a4b96c-8e3f-4501-897c-51bab99bedb7` probed → `404 {"detail":"Project not found"}`. Never created or mutated on this Beta instance; the spec reads it via `getJson(...).catch(() => null)` and never writes to it.

**Independent Playwright re-run (verifier's own):**

```powershell
$env:ADEPT_BETA_TARGET="1"; $env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:8760";
$env:STUDIO_API_BASE="http://127.0.0.1:8758";
npx playwright test tests/e2e/posecraft/posecraft-snapshot-workflow.spec.ts `
  --project=chromium --workers=1 --retries=0
```

| Run | Duration | Exit code | Result |
| --- | --- | --- | --- |
| 1 (verifier) | 33.8s | **0** | 1 passed |

**Per-gate independent verdict (verbatim):**

```text
Gate SNAP-1 — Snapshot Matches Viewport Camera: PASS
Gate SNAP-2 — Clean Snapshot Excludes Editing UI: PASS
Gate SNAP-3 — Rename/Duplicate/Delete: PASS
Gate SNAP-4 — Scene Revision Provenance: PASS
Gate SNAP-5 — Co-Director Handoff: PASS
Gate SNAP-6 — Image Generation Handoff: PASS
Gate SNAP-7 — Storyboard Handoff: PASS
Gate SNAP-8 — Multiple Snapshots Remain Independent: PASS

GLM 5.2 INDEPENDENT VERIFIER — POSECRAFT SNAPSHOT WORKFLOW PASSED
```

**SNAP-4 provenance / honesty label spot-check (verifier's own API reads):**
`posecraft.inspect_scene` with `snapshotId` returns the frozen composition (frozen `snapshotId`, `imageAssetId`, `lensMm=35`, `aspect=16:9`, `semanticSummary`, frozen figures) plus `honestyLabel = "PoseCraft Snapshot — Visual Staging Reference"` and a `narrativeHint` instructing Co-Director to treat the snapshot as a visual staging reference (not a final frame) and to use creator labels (not staging colors). `export-preview?snapshot_id=` returns the frozen camera + renamed `sceneName="Wide master"` + the same honesty label. Restore-camera leaves the original snapshot's frozen `sceneRevision` unchanged.

Verifier artifact run: `docs/release-gate/posecraft/artifacts/snapshot-workflow/POSECRAFT-SNAPSHOT-WORKFLOW-2026-08-04T23-01-41-855Z/`

Full report: [`POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md)

**Capability verdict (independent):** `GO — POSECRAFT SNAPSHOT AND PRODUCTION HANDOFF READY`

> Scoped to the Snapshot Workflow capability only. The Final Mandatory GO program for human
> figures is now also independently verified **GO** (see **CURRENT AUTHORITATIVE STATUS**).

---

## Product law

```text
There shall be exactly one creator-facing PoseCraft experience.
The Babylon.js workspace is the product.
Landing / help / introduction pages are secondary overlays only.
```

**Failure if violated:** `NO-GO — POSECRAFT ROUTE DOES NOT OPEN THE 3D WORKSPACE`

**Canonical staging path:**

```text
Character Creator → PoseCraft → Image Generation → Storyboard → Timeline → MAGI
```

Creator-driven character blocking goes through PoseCraft — not a fixture or landing-page bypass.

---

## Journey (one timeline)

| Era | Status | What changed |
| --- | --- | --- |
| Parallel foundation | Worktree `AIVideoStudio-posecraft` / `feature/posecraft-v1-1-foundation` (~`2e4246f`) | Babylon lab at `/posecraft-lab`; localStorage; reviewer READY WITH LIMITATIONS |
| Pre-promotion main tree | Experimental landing only | `PoseCraftWorkspace` = Character Creator / Image Gen CTAs; no canvas |
| Historical RED cert | `ADEPT-FULL-CREATOR-CERT-2026-08-04T06-05-28Z` family | Pipeline blocked on PoseCraft Experimental-only (+ then-current Comfy/H3 issues). **Historical only** |
| Recovery | Comfy `:8188` + H3 `:8192` restored | Integrated path became CONDITIONAL with sole PoseCraft blocker |
| **v1.1 Promotion** | **GREEN baseline** | Babylon promoted to `?workspace=posecraft`; API `m026`; Co-Director `posecraft.*`; live Image Pipeline package; coffee-shop + full pipeline live GO |
| **Master Program** | Master Program era | Humans, viewport, 56 integrity poses, gizmos, API SoT, custom poses, Storyboard tool, compat migration; live re-cert evidence retained — see Historical Certifications |

---

## What creators get today

| Capability | State |
| --- | --- |
| Route | `/project/:id?workspace=posecraft` — Babylon canvas (`posecraft-babylon-canvas`) + Production pill |
| Entry points | Home, Production menu, Explore, Co-Director — same workspace |
| Viewport | ~19/62/19 layout, ~5% margins, gray matte stage, rule-of-thirds + snapshot rectangle |
| Figures | Low-poly adult/child male/female; staging colors (incl. sea-glass); character mapping |
| Pose library | **56** integrity-gated poses; SVG thumbnails from joint data; search / filters / favorites; scrollable pane |
| Manipulation | Move / Rotate / Pose Body; joint handles + root gizmos; undo/redo; save/reload proof |
| Persistence | Project-scoped `/api/posecraft/*` (SoT); revisions; custom poses (M027); legacy schema 1→2 migration |
| Co-Director | 14 `posecraft.*` tools; approval-gated mutations; no silent overwrite after `creatorModified` |
| Handoffs | Export as **PoseCraft visual staging reference** → Image Generation; `send_to_storyboard` honesty package |
| Runtime policy | Production Comfy `:8188` (images); MiniMax Route A `:8192` (private H3 only) — never substituted |

---

## Architecture

```text
Home / Production / Co-Director
        ↓
?workspace=posecraft
        ↓
PoseCraftWorkspace (thin shell)
        ↓
Babylon engine + state + pose catalog
        ↓
POST/PUT /api/posecraft/projects/{id}/scene
        ↓
Co-Director tools  |  Image Pipeline control package  |  Storyboard handoff
```

**Key packages**

- Frontend: [`studio-web/src/posecraft/`](../../../studio-web/src/posecraft/), [`PoseCraftWorkspace.tsx`](../../../studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx)
- Backend: [`studio-api/app/posecraft/`](../../../studio-api/app/posecraft/)
- Migrations: `m026_posecraft_persistence`, `m027_posecraft_custom_poses`
- Dependency: `@babylonjs/core@^9.19.0`

---

## Certification evidence

### Master Program (coffee-shop A–K)

| Item | Result |
| --- | --- |
| Spec | `tests/e2e/posecraft/posecraft-production-two-character.spec.ts` |
| Live result | **1 passed** (~1.1m) against Beta |
| Artifacts | `docs/release-gate/posecraft/artifacts/coffeeshop-cert/`, `test-results/posecraft-coffeeshop/` |
| Gates | Humans, 56 poses, gizmos, catalog apply, custom pose CRUD, Storyboard handoff, reload, compat, honesty label |
| Verdict | See **Historical Certifications** |

### Integrated full creator pipeline

| Item | Result |
| --- | --- |
| Spec | `tests/e2e/integration/adept-ui-full-creator-pipeline.spec.ts` |
| Run ID | `ADEPT-FULL-CREATOR-CERT-2026-08-04T18-17-47-331Z` |
| Live result | **exit 0** — 8 passed + 1 flaky-on-retry (persist race hardened) |
| Classification | `POSECRAFT_PRODUCTION_READY` |
| Also proven | Character/ERS/shot assets; private H3 T2VA (Route A); Library + Timeline; reload/isolation |
| Report / matrix | `docs/release-gate/integration/ADEPT_UI_FULL_CREATOR_PIPELINE_PLAYWRIGHT.md`, `..._MATRIX.md` |
| Verdict | See **Historical Certifications** |

### Automated suites (Master delta)

| Suite | Result |
| --- | --- |
| Vitest posecraft (catalog, manipulation, thumbnails, scene) | **20/20** |
| Pytest posecraft contracts + runtime gates | **14/14** |
| `studio-web` production build | **passed** |

### Runtime (live certification environment)

| Service | Port | Role |
| --- | --- | --- |
| Beta UI | `8760` | Creator surface |
| Studio API | `8758` | Product API |
| Production Comfy | `8188` | Images / ERS / shot ref |
| MiniMax H3 Route A | `8192` | Private owner-only T2VA |

Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never mutated. Disposable cert projects cleaned in `afterAll`.

---

## Master gap closure (14/14)

| # | Gap | Outcome |
| --- | ---: | --- |
| 1 | Human figures | Capsule limbs / tapered torso / neck; adult & child archetypes |
| 2 | Viewport | Gray matte stage; dominant center canvas |
| 3 | Backward compat | schemaVersion 1→2; migrate on load **and** save; legacy joints in provenance |
| 4 | Pose library ≥50 | 56 integrity-gated poses (distinct joints + matching thumbs) |
| 5 | Manipulation | Gizmos with viewport → canonical → API → reload proof |
| 6 | UI persistence | API SoT via `posecraftApi.ts` |
| 7 | Custom poses | M027 + CRUD + UI |
| 8–9 | Co-Director / Storyboard | 14 tools incl. `send_to_storyboard` |
| 10 | Thumbnails | Deterministic SVG from joint data (56 on disk) |
| 11–14 | Cert / runtime / tests / verdict | Live evidence captured; independently re-verified (2026-08-04) |

---

## Hardening during live Master cert

1. **`save_scene` migration-on-PUT** — Legacy `schemaVersion: 1` was only migrated on load; PUT echoed v1. Fixed in `service.save_scene` to migrate `currentScene` + revisions before persist. Regression test strengthened.
2. **Full-pipeline Phase 12 persist race** — Conversation API poll until awareness turn is durable (requirement unchanged).

---

## Limitations (honest)

- Thumbnails are **SVG** stick projections from joint data, not WebP/AVIF raster (format drop-in later if required).
- Joint drag is a **blocking gizmo**, not full IK / animation.
- Storyboard **ingest consumer** is the existing storyboard surface; the tool returns an honesty-labelled package (`next: storyboard.ingest_posecraft_sketch`).
- WebGPU may be unavailable in headless Chromium; WebGL fallback is acceptable for cert.
- H3 / Comfy GPU contention can flake external runtimes under heavy load; certification left production Comfy running and kept Route A isolated.

---

## Out of scope (still enforced)

SceneCraft, detailed furniture modeling, custom mesh import, mocap/animation/facial/cloth, photoreal humans, final render inside PoseCraft, public MiniMax / Best Match / general routing, CUDA experimentation, new model downloads, Home/ERS/Timeline redesign.

---

## Manual review path

1. Open Beta: http://127.0.0.1:8760/
2. Open a project → PoseCraft (`?workspace=posecraft`)
3. Confirm Babylon canvas, gray stage, Production pill (not Experimental landing)
4. Add adult male + female; browse 56-pose library; apply a conversational pose
5. Use Move / Rotate / Pose Body; save; reload; confirm persistence
6. Export staging reference; Send to Image Generation / Storyboard via Co-Director as needed

**Replay certs:**

```bash
ADEPT_BETA_TARGET=1 STUDIO_API_BASE=http://127.0.0.1:8758 \
  npx playwright test tests/e2e/posecraft/posecraft-production-two-character.spec.ts --project=chromium --workers=1

ADEPT_BETA_TARGET=1 STUDIO_API_BASE=http://127.0.0.1:8758 \
  npx playwright test tests/e2e/integration/adept-ui-full-creator-pipeline.spec.ts --project=chromium --workers=1
```

---

## Historical Certifications

> **Not current authority.** Governing status is **CURRENT AUTHORITATIVE STATUS** at the top of this document. This section records superseded verdicts and prior certifications for audit trail only.

### Historical Final Mandatory GO NO-GO (superseded)

```text
NO-GO — POSECRAFT HUMAN FIGURE MODELS AND DELETION UX NOT YET VERIFIED
```

The first independent verification of the Final Mandatory GO program (glm-5.2, non-implementer — 2026-08-04) returned NO-GO: D1–D4 PASS, but FURN deterministically FAILED (Furniture accordion hydration race — `posecraft-furniture-grid` never rendered after toggle), and D5/D6/IMPORT/STORY/COFFEE were not reached. Two deterministic runs (exit 1 both). The implementer subsequently repaired the Furniture accordion hydration race and the D5 rename debounce race (`mutateAndFlush`); the re-verification (above) confirmed all gates PASS. Retained here for audit trail only — **superseded by the current GO**. Prior verifier artifact runs: `…/final-mandatory-go/POSECRAFT-FINAL-MANDATORY-GO-2026-08-04T21-46-29-236Z/` and `…/2026-08-04T21-49-24-960Z/`.

### Superseded Master GO (historical only)

```text
GO — POSECRAFT MASTER PROGRAM READY
```

Prior Master GO was issued during the Master Program quality-elevation era and covered the original block-figure rig, 56-pose library, gizmos, persistence, and coffee-shop staging. It was **superseded** by the Final Mandatory GO program, which required new low-poly human figure models (D1–D4), Cast three-dot / keyboard deletion UX (D5–D6), expanded furniture (walls + window walls), custom mesh import, and storyboard package preservation before any new Master GO could be issued. **Those requirements have now been independently verified PASS** (see **CURRENT AUTHORITATIVE STATUS** and the **Final Mandatory GO Independent Verification** section), and a fresh Master GO has been issued. This prior Master GO is retained here as historical context only. Full historical context: [`POSECRAFT_MASTER_COMPLETION_REPORT.md`](POSECRAFT_MASTER_COMPLETION_REPORT.md).

### Historical Mandatory GO Corrective (superseded)

The 2026-08-04 Mandatory GO Corrective independent verification (glm-5.2-high, non-implementer) — Gates A–J PASS live — is retained here as historical evidence only. It covered the block-figure rig and the original coffee-shop staging, not the new low-poly human figure models. Full report: [`POSECRAFT_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_MANDATORY_GO_INDEPENDENT_VERIFIER_REPORT.md).

### Historical Pipeline Certification

```text
GREEN — ADEPT UI FULL CREATOR PIPELINE READY
```

This certification remains the most recent pipeline certification. It is **not** re-certified or modified by the PoseCraft Final Mandatory GO program. Pipeline GREEN is historical only.

---

## Document index

| Document | Role |
| --- | --- |
| **This file** — `POSECRAFT_AMALGAMATED_REPORT.md` | Single amalgamated status — **CURRENT AUTHORITATIVE STATUS** governs |
| [`POSECRAFT_SNAPSHOT_WORKFLOW_IMPLEMENTER_HANDOFF.md`](POSECRAFT_SNAPSHOT_WORKFLOW_IMPLEMENTER_HANDOFF.md) | Snapshot Workflow implementer evidence pack |
| [`POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md`](POSECRAFT_SNAPSHOT_WORKFLOW_INDEPENDENT_VERIFIER_REPORT.md) | Snapshot Workflow independent verifier (GO — capability scoped) |
| [`POSECRAFT_MANDATORY_GO_IMPLEMENTER_HANDOFF.md`](POSECRAFT_MANDATORY_GO_IMPLEMENTER_HANDOFF.md) | Implementer evidence pack for independent verifier |
| [`POSECRAFT_MASTER_COMPLETION_REPORT.md`](POSECRAFT_MASTER_COMPLETION_REPORT.md) | Master Program completion — verdict in Historical Certifications |
| [`POSECRAFT_MASTER_PROGRAM.md`](POSECRAFT_MASTER_PROGRAM.md) | Gap tracker (may lag amalgamated verdicts — prefer this file for current strings) |
| [`POSECRAFT_PRODUCTION_CERTIFICATION.md`](POSECRAFT_PRODUCTION_CERTIFICATION.md) | v1.1 promotion certification |
| [`POSECRAFT_PRIMARY_MERGE_REVIEW.md`](POSECRAFT_PRIMARY_MERGE_REVIEW.md) | Promotion merge review (not parallel retention) |
| [`../integration/ADEPT_UI_FULL_CREATOR_PIPELINE_PLAYWRIGHT.md`](../integration/ADEPT_UI_FULL_CREATOR_PIPELINE_PLAYWRIGHT.md) | Integrated pipeline report |
| [`../integration/ADEPT_UI_FULL_CREATOR_PIPELINE_MATRIX.md`](../integration/ADEPT_UI_FULL_CREATOR_PIPELINE_MATRIX.md) | Integrated pipeline matrix |
| [`../parallel/H3_POSECRAFT_PARALLEL_PROGRAM.md`](../parallel/H3_POSECRAFT_PARALLEL_PROGRAM.md) | Historical parallel-track program notes |
| [`../parallel/MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md`](../parallel/MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md) | Historical H3 + PoseCraft parallel report |

---

## Final product law

> PoseCraft is a filmmaker’s 3D staging workspace. Fast creators use the visual pose library. Precise creators refine bodies with direct joint handles. Every creator can move complete figures, block simple furniture, compose the camera, save the project scene, and carry that staging into Image Generation and Storyboard. A landing page, block creature, text-only pose list, slider-only rig, or unsaved viewport is not production PoseCraft.
