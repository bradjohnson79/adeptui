# MiniMax H3 + PoseCraft — Unified Implementation Report

**Date:** 2026-08-03  
**Program:** Parallel Track A (MiniMax H3) + Track B (PoseCraft v1.1)  
**Baseline SHA:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Primary branch:** `feature/ai-guided-setup`  
**Safety gate:** [`PARALLEL_SAFETY_GATE.md`](PARALLEL_SAFETY_GATE.md)  
**Prior status note:** [`H3_POSECRAFT_PARALLEL_PROGRAM.md`](H3_POSECRAFT_PARALLEL_PROGRAM.md)  
**Authoritative MiniMax H3 status (supersedes H3 runtime rows in this document):** [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md)

---

## Executive verdict

| Layer | Verdict | Meaning |
|---|---|---|
| **Parallel program (isolated handoffs)** | **COMPLETE — BOTH TRACKS READY** | Both worktree handoff packages finished for deliberate integration review |
| **MiniMax H3 local GPU generation** | **See unified MiniMax report** — `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED` (PRIMARY ACCEPTED); Creator Disabled | Canada Diffusers spike remains historical NO-GO; Route A Comfy-Org path produced genuine local T2VA |
| **MiniMax H3 Adept UI surface wiring** | **GO — SURFACE WIRING READY** | Creator surfaces plan/preflight/fallback honestly; ComfyUI not creator-facing |
| **PoseCraft v1.1 foundation** | **READY WITH LIMITATIONS** | Isolated `/posecraft-lab` foundation complete; not production-wired |

**Program binary for production merge of both features into live creator workflows:** **NO-GO** until deliberate Adept UI H3 integration + Law #28 cert and intentional PoseCraft integration review complete.  
**Program binary for isolated delivery / review readiness:** **GO** for handoff packages as disclosed above.

---

## Worktree map

| Track | Branch | Path | HEAD (handoff) | Current HEAD |
|---|---|---|---|---|
| Primary / H3 surface wiring | `feature/ai-guided-setup` | `C:\AdeptFilmWorks\AIVideoStudio` | baseline `fa09c99` | `fa09c99` + uncommitted H3 surface work |
| MiniMax H3 spike | `spike/minimax-h3-33b-rtx5090` | `C:\AdeptFilmWorks\AIVideoStudio-h3` | `c932214` | `c932214a233fbc0fddb009ef6f80638dd60c8082` |
| PoseCraft v1.1 | `feature/posecraft-v1-1-foundation` | `C:\AdeptFilmWorks\AIVideoStudio-posecraft` | foundation `7198962` + reviewer `2e4246f` | `2e4246f54aee8fe76bd81ba771b5b2fe579f3fa6` |

Protected project (never mutated): Manual Beta Handoff `77a4b96c-8e3f-4501-897c-51bab99bedb7`.

Live Beta (primary tree, H3 surface cert):  
http://127.0.0.1:8760/ · API http://127.0.0.1:8758/

---

## Track A — MiniMax H3

### A1. Parallel spike (isolated worktree)

> **Supersession:** For current H3 local-runtime status, use [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md). The Canada Diffusers spike verdict below is historical only.

**Handoff:** `AIVideoStudio-h3/docs/models/minimax-h3/H3_PARALLEL_SPIKE_HANDOFF.md`  
**Reviewer:** `AIVideoStudio-h3/docs/models/minimax-h3/H3_REVIEWER_PASS.md`  
**Historical Canada spike verdict:** `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO`  
**Current Route A verdict (PRIMARY ACCEPTED):** `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED`

#### Delivered

1. Official source and Community License audit (live HF LICENSE / README / MiniMax blog).
2. Checkpoint inventory **without** downloading weights.
3. Isolated runtime audit and RTX 5090 memory matrix scaffold (not measured).
4. Integration contract drafts under `docs/models/minimax-h3/contracts/`.
5. Experimental stubs under `studio-api/app/experimental/minimax_h3/` (unregistered).
6. Territory gate corrected for Canadian development; excluded-territory local blocking retained and fail-closed on unknown territory.

#### Critical legal finding

Pinned public H3 sources place Canada inside the default `Applicable Territory`, while excluding the United States, EU, UK, and Korea for open-weight community-license use.  
Canada-only local H3 development is reopened **with conditions**; excluded-territory open-weight deployment still requires MiniMax authorization.

#### Explicit non-actions (correct)

- No multi-hundred-GB weight download  
- No production ComfyUI mutation  
- No silent replacement of LTX  
- No promotion of H3 to primary video engine  

#### Closed Canada runtime spike

The isolated worktree later resumed a real Canada-only runtime spike under `RUN-20260803-145133`.
Primary has now accepted that evidence package as the authoritative close for this spike.

- Gate A passed: FL2VA minimum download completed at `144,051,182,625 / 144,051,182,625 bytes` (`100.00%`)
- CUDA was proven on RTX 5090 in the repaired isolated `torch 2.11.0+cu128` runtime
- Released Diffusers still did not expose `MiniMaxH3Pipeline` / `MiniMaxH3ModularPipeline`
- A secondary isolated ComfyUI retry on `:8192` also failed honestly because the official H3 template
  expects single-file Comfy weights, while the downloaded payload is the Diffusers-sharded FL2VA tree
- The isolated Comfy execution hit missing-key warnings and `NotImplementedError: Cannot copy out of meta tensor; no data!`
- No genuine H3 MP4 was produced in this Canada Diffusers/shard attempt; Gate B failed and Gate C remained NO-GO

**Historical Canada-spike verdict string (not current Route A status):**

**CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO**

**Current local-runtime status:** see [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md) — `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED` (PRIMARY ACCEPTED); Creator Disabled.

#### Next steps after Route A (supersedes prior unblock checklist)

1. Deliberate Adept UI Runtime Adapter integration (feature-flagged; Creator Disabled until cert).  
2. Keep LTX as the permanent explicit fallback.  
3. Trained-range quality proof and/or cu130 kernel path before any creator-facing toggle.  
4. Law #28 Co-Director disposable-project Playwright certification before Creator enablement.  
5. Retain Diffusers FL2VA for Route B only; do not force shards into Comfy Route A.

### A2. Adept UI surface wiring (primary tree)

**Certification:** [`../minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md`](../minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md)  
**Surface verdict:** **GO — H3 ADEPT UI SURFACE WIRING READY**  
*(Surface honesty only — not local media GO.)*

#### Creator surfaces wired

| Surface | Implementation |
|---|---|
| Co-Director | `minimax_h3.*` tools — capability, plan, three-frame, LTX fallback |
| Text2Video | Engine `minimax-h3` + MiniMax H3 Plan panel |
| One Frame | Start Frame + motion prompt + H3 plan |
| Three Frame | Start / Middle Guidance / End strip + Strategy A disclosure |
| Timeline | H3 plan panel on Timeline Master |
| Production Dock / Model Library | Requires Setup (honest; not fake Coming Soon) |
| Library / provenance | Plan receipts + fallback acceptance records |
| Native audio | Import/metadata helper; **no false stem claims** |

#### Canonical contract

`AdeptMiniMaxH3Request` → `/api/minimax-h3/*`  
Docs:

- `docs/architecture/minimax-h3/ADEPT_MINIMAX_H3_REQUEST_CONTRACT.md`
- `docs/models/minimax-h3/H3_SURFACE_WIRING.md`
- `docs/models/minimax-h3/H3_THREE_FRAME_RUNTIME_TRUTH.md`

Backend package: `studio-api/app/minimax_h3/`  
UI panel: `studio-web/src/components/minimax-h3/MiniMaxH3PlanPanel.tsx`

#### Runtime truths (certified)

1. FL2VA-class conditioning accepts **0/1/2 frames only** — not three native temporal anchors.  
2. **`threeFrameNative: false`** → Adept **Strategy A**: Start→Middle, Middle→End, Timeline assembly.  
3. Excluded-territory local weights stay **blocked**; Canadian local development is no longer hard-blocked by default.  
4. LTX is permanent fallback — **explicit accept only**, never silent.  
5. Jobs do not invent completed H3 assets when runtime cannot run.  
6. Creator copy avoids ComfyUI nodes, workflow JSON, checkpoints, and filesystem paths.

#### Evidence

```text
# Unit
python -m pytest studio-api/app/minimax_h3/test_minimax_h3_surfaces.py -q
# 7 passed

# Adept-UI-only Playwright (no ComfyUI)
ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758
npx playwright test tests/e2e/minimax-h3/minimax-h3-adept-ui-surface-cert.spec.ts --project=chromium
# 6 passed (A–F)
```

Artifacts: `docs/release-gate/minimax-h3/artifacts/H3-SURFACE-AUTONOMOUS-CERT-2026-08-03T21-24-57-798Z/`

| Spec | Result |
|---|---|
| A Co-Director tools / no Comfy jargon | PASS |
| B Text2Video + plan + LTX fallback | PASS |
| C One Frame Start Frame plan | PASS |
| D Three Frame Strategy A honesty | PASS |
| E Blocked local + explicit LTX + no fake complete | PASS |
| F Capability matrix native three-frame false | PASS |

---

## Track B — PoseCraft v1.1 Foundation

**Handoff:** `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_V1_1_PARALLEL_FOUNDATION_HANDOFF.md`  
**Reviewer:** `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_REVIEWER_PASS.md` → `READY FOR PRIMARY REVIEW`  
**Foundation SHA:** `719896280782434b49aa80594290900413886932`  
**Reviewer commit:** `2e4246f54aee8fe76bd81ba771b5b2fe579f3fa6`  
**Verdict:** **READY WITH LIMITATIONS**

### Delivered

- Isolated creator route: `/posecraft-lab` (not production Image Studio / Co-Director wired)
- Babylon neutral stage (floor, grid, axes, light, resize, dispose cleanup)
- Four procedural low-poly archetypes with major-joint posing
- Figure CRUD, local version history, undo/redo, pose presets, blocking boxes
- Camera lenses / aspect / guides
- Local exports: scene JSON, snapshot + metadata, reference pack JSON
- Draft contracts + SceneCraft compatibility notes only

### Evidence

```text
npx vitest run src/posecraft/sceneState.test.ts
# 5 passed

PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test \
  tests/e2e/posecraft/posecraft-foundation.spec.ts --project chromium
# 1 passed (21-step creator checklist on isolated Vite target)
```

### Limitations (disclosed)

- No Co-Director / registry / project-DB / shared Library wiring  
- Eager import of PoseCraft into `App.tsx` (bundle-cost risk; lazy-load recommended before broad merge)  
- Scene schema slightly ahead of wired stage controls (`gridSize` / `showAxes` gaps)  
- Full `studio-web` production build in PoseCraft worktree still blocked by unrelated Voice Studio TS errors  
- Accessibility for viewport posing not yet certified  
- Not present in primary tree path `studio-web/src/posecraft` (still worktree-only)

### Forbidden-surface check

Passed — no edits to production Co-Director registries, project schemas, scheduler, model router, Timeline/Audio Studio production flows, or Manual Beta Handoff data.

---

## Cross-track relationship

```text
PoseCraft (pose / figure refs)
        │
        ▼ (future, after merge + adapters)
Image Pipeline / SceneCraft staging
        │
        ▼
MiniMax H3 / LTX video generation
        │
        ▼
Timeline + Library + native audio lanes
```

**Today:** tracks are **intentionally decoupled**.  
PoseCraft does not yet feed H3. H3 surface wiring does not depend on PoseCraft.  
Future step 7 in merge policy: wire PoseCraft refs → H3/LTX only after H3 local becomes lawful **or** via approved hosted/API path with explicit creator consent.

---

## Merge policy (unchanged intent)

Do **not** auto-merge either track into production without primary review.

1. Review/merge H3 docs + experimental namespace from spike (as needed).  
2. Keep / promote Adept UI H3 surface package from primary tree with honest capability labels.  
3. Preserve Canadian-local clearance and excluded-territory blocking **before** any local H3 weight runtime.  
4. Certify H3 E2E media only after real GPU proof; preserve LTX fallback.  
5. Independent review already recorded for PoseCraft; primary decides merge of `/posecraft-lab` first.  
6. PoseCraft project persistence + shared routing.  
7. Wire PoseCraft → Co-Director / Image Studio.  
8. Wire PoseCraft refs → H3 / LTX when lawful.  
9. Cross-feature Playwright (PoseCraft → Image → H3/LTX → Timeline).

---

## Unified evidence index

| Artifact | Location |
|---|---|
| H3 Canada clearance memo | `docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md` |
| H3 Canada clearance unified report | `docs/release-gate/minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md` |
| Parallel program status | `docs/release-gate/parallel/H3_POSECRAFT_PARALLEL_PROGRAM.md` |
| This unified report | `docs/release-gate/parallel/MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md` |
| H3 spike handoff | `AIVideoStudio-h3/docs/models/minimax-h3/H3_PARALLEL_SPIKE_HANDOFF.md` |
| H3 surface cert | `docs/release-gate/minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md` |
| H3 request contract | `docs/architecture/minimax-h3/ADEPT_MINIMAX_H3_REQUEST_CONTRACT.md` |
| PoseCraft foundation handoff | `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_V1_1_PARALLEL_FOUNDATION_HANDOFF.md` |
| PoseCraft reviewer pass | `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_REVIEWER_PASS.md` |
| PoseCraft file manifest | `AIVideoStudio-posecraft/docs/posecraft/FILE_MANIFEST.md` |

---

## Mandatory completion checklist (program)

```text
[x] Branch + baseline SHA verified (fa09c99)
[x] Parallel safety gate respected (isolated worktrees)
[x] H3 license audit completed; Canadian local clearance documented with conditions
[x] H3 contracts drafted; surface request contract frozen
[x] H3 Adept UI surfaces wired (plan / preflight / fallback)
[x] Three Frame honesty (Strategy A, not fake native)
[x] LTX fallback explicit only
[x] H3 unit + Adept-UI Playwright passed
[x] PoseCraft isolated foundation delivered
[x] PoseCraft vitest + Playwright foundation passed
[x] PoseCraft reviewer second-pass recorded
[x] No silent model / CPU / ComfyUI creator path
[x] Manual Beta Handoff isolation preserved
[x] Limitations honest in both tracks
[x] Unified Markdown report created
[ ] Production merge of both tracks — deferred (primary decision)
[x] Local H3 GPU generation — Route A proven with limitations (see unified MiniMax report); Creator Disabled
[ ] PoseCraft → Co-Director / Image / H3 wiring — not started
[ ] Cross-feature E2E — not started
```

---

## Final program statements

> For MiniMax H3 runtime and program status, prefer [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md).

1. **MiniMax H3 Canada Diffusers spike (historical):** **NO-GO — `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO`**.  
2. **MiniMax H3 Route A local runtime (current):** **`ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED`** (PRIMARY ACCEPTED); Creator production remains Disabled.  
3. **MiniMax H3 Adept UI surfaces:** **GO** for planning, honesty, and fallback UX.  
4. **PoseCraft v1.1 foundation:** `READY WITH LIMITATIONS`.  
5. **Combined production integration:** **NO-GO** until deliberate Adept UI H3 integration + Law #28 cert and PoseCraft merge sequence.  
6. **Combined parallel handoff readiness:** **GO** — both tracks delivered for primary review.

**Authoritative program label:**  
**PARALLEL IMPLEMENTATION COMPLETE — HANDOFFS READY; PRODUCTION INTEGRATION DEFERRED**
