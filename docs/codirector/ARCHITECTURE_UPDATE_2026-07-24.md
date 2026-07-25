# Adept UI Gen Studio — Architecture Update Report

**Date:** 2026-07-24  
**Audience:** product / engineering planning  
**Primary checkout:** `C:\AdeptFilmWorks\AIVideoStudio` → `phase2/codirector-m2-4-intelligence`  
**Last committed tip on that branch:** `8f503f1` (M2.2 docs) — **M2.3 and M2.4 code is implemented but not yet committed**

---

## 1. Executive summary

Adept UI has progressed from a Co-Director chat gateway (M1) through a versioned Production Bible (M2.1), bounded tools (M2.2), structured Bible domains (M2.3), and production intelligence with specialists (M2.4). In parallel, Essential Pack authoring and Production Systems Readiness (PSR) shipped in **isolated worktrees**.

The production loop envisioned by the Co-Director roadmap is now mostly designed in code on the main line through planning/generation proposal — but **vision validation (M2.5) is not started**, **M2.3/M2.4 are uncommitted**, and **PSR’s capability registry is not merged** into the Co-Director branch. Local API/web/ComfyUI were **not responding** at report time.

```text
Production Bible (M2.3)  →  Intelligence / specialists (M2.4)
        ↓                              ↓
   Context packages            Plans + tool proposals (M2.2)
        ↓                              ↓
   Generation (Comfy / jobs)   ← blocked without Comfy + packs
        ↓
   Vision validation (M2.5)    ← not built
        ↓
   Approve + Bible link
```

---

## 2. Worktree topology (what lives where)

| Location | Branch | Tip | Role |
|---|---|---|---|
| `AIVideoStudio` | `phase2/codirector-m2-4-intelligence` | `8f503f1` + **dirty WIP** | Co-Director M2.1–M2.4 (M2.3/M2.4 uncommitted) |
| `AIVideoStudio-psr` | `phase2/production-systems-readiness` | `24384a4` clean | Capability registry, SceneService, Health/Setup/SM integration |
| `AIVideoStudio-pack-authoring` | `phase1c/essential-pack-authoring` | `9af9196` | Essential Pack authoring trees + validate/build tooling |

These lines have **not** been merged into each other. Treating any one checkout as “the whole product” will miss capabilities or Co-Director features.

---

## 3. What has been built

### 3.1 Co-Director milestones (main line)

| Milestone | Status | Persistence | Notes |
|---|---|---|---|
| **M1** Provider reliability | Shipped (earlier commits) | Committed on lineage | Browser → Adept gateway → Ollama/mock; SSE; cancel; settings |
| **M2.1** Bible + proposals | Shipped | Committed (`db06c4f` lineage) | COW versions, proposals/approvals/receipts |
| **M2.2** Tool registry | Shipped | Committed (`2545ab1` / `8f503f1`) | Closed registry; read + mutating tools; `tool_call` proposals |
| **M2.3** Production Bible Foundation | **Implemented, uncommitted** | Migrations `m004` in working tree | Typed domains, lifecycle, context APIs, conflicts, Bible UI, export |
| **M2.4** Production Intelligence | **Implemented, uncommitted** | Migrations `m005` in working tree | 55 prompts, 19 specialists, intent/synthesis/plans, intelligence SSE, eval A–G |
| **M2.5** Vision validation | **Planned only** | — | Plan exists; no `codirector/vision/` package |

**Migrations present in main working tree:** `M001` … `M005` (Bible tools, Bible domain, intelligence).

**Feature flags:** `STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2` (default off). Vision flag not added yet.

**Verified locally (main WIP):** 166 pytest (intelligence + tools + bible + provider); 55 prompts validate via `npm run codirector:validate-prompts`.

### 3.2 Production Systems Readiness (PSR worktree)

Shipped and committed on `phase2/production-systems-readiness`:

- Global capability registry (`/api/capabilities*`) — ~69 capabilities; ~35 callable when environment allows
- `SceneService` with honest scene CRUD; patch-only-present-fields fix
- Structured Comfy/workflow readiness (no false “ready”)
- Health Dashboard, Setup Wizard, Source Manager consume registry
- Docs: readiness report, contracts, matrix, registry guide
- Tests: 51 capability/scene; 41 `@critical` Playwright in that worktree

**Honest blockers reported:** ComfyUI not running; IC-LoRA weights gated/missing; Essential Packs unpublished (`MODEL_SOURCE_PENDING`). Generation intentionally not claimed `production_ready`.

### 3.3 Essential Pack authoring (pack worktree)

Shipped on `phase1c/essential-pack-authoring`: pack specs, authoring trees (stubs, no model binaries), validate/build/publish tooling, catalog packs remain `not_published` / empty sources.

---

## 4. What is currently running

Probed at report time (2026-07-24 evening local):

| Service | Endpoint | Status |
|---|---|---|
| Studio API | `http://127.0.0.1:8742/health` | **Down** |
| Studio Web | `http://127.0.0.1:5173/` | **Down** |
| ComfyUI | `http://127.0.0.1:8188` | **Down** |

Historical terminal sessions show prior uvicorn/Vite/`e2e:start` runs and recent Playwright attempts; none of the core user-facing servers responded to a fresh health probe.

**Implication:** Co-Director M2.3/M2.4 code is on disk in the main checkout, but there is no live stack confirming the WIP end-to-end right now. PSR and pack worktrees are complete as git artifacts, not as a merged running product.

---

## 5. Architecture as implemented (main Co-Director line)

```text
studio-web (React)
  CoDirector/*  → SSE /api/codirector/chat/stream
  ProductionBibleWorkspace → /api/codirector/.../bible/*
        ↓
studio-api FastAPI
  codirector/service.py          gateway + optional IntelligenceService (flag)
  codirector/providers/          ollama | mock (E2E)
  codirector/tools/              M2.2 registry + handlers
  codirector/bible/              M2.1 COW + M2.3 domain/context/conflicts
  codirector/intelligence/       M2.4 orchestration
  codirector/prompts/            55 versioned Markdown prompts
  codirector/evaluation/         fixture harness A–G
        ↓
SQLite (projects, scenes, assets, jobs, bible*, proposals*, tools*, intelligence*)
filesystem (assets/, projects/*/references/, validation/ TBD)
```

**Invariants still holding:**

1. Model never mutates project truth without M2.1/M2.2 approval.  
2. Browser never calls Ollama directly.  
3. Production Bible is COW-versioned; specialists advise only (`may_execute_tools: false`).  
4. Visual comparison remains deferred (`visualValidationPending` set, not cleared by a validator).

---

## 6. Gaps and risks

| Risk | Severity | Detail |
|---|---|---|
| Uncommitted M2.3 + M2.4 | **High** | Large WIP on one branch; easy to lose or mix with merges |
| Three divergent worktrees | **High** | PSR capabilities and Co-Director tools/intelligence not unified |
| M2.5 not started | **High** for “closed loop” | Generation completes ≠ asset validated |
| ComfyUI / packs unpublished | **High** for real renders | Storyboard proposal prepares packages; execution needs Comfy + models |
| Dual capability notions | **Medium** | M2.2 `CapabilityAdapter` vs PSR `/api/capabilities` until merge |
| FE legacy planner | **Medium** | `studio-web/src/codirector/planFromIntention` still parallel to backend plans |
| No live servers | **Medium** | Cannot manually verify WIP without restart |
| Specialist findings under E2E | **Low/known** | Heuristics when mock provider; real multimodal optional |

---

## 7. Recommended next steps (ordered)

### P0 — Stabilize the Co-Director line (do before more features)

1. **Commit M2.3 + M2.4** on `phase2/codirector-m2-4-intelligence` (or split into two commits: Bible foundation, then intelligence) with clear messages.  
2. **Tag checkpoints** if not already present (`checkpoint/codirector-m2-3-start`, `m2-4-start`).  
3. **Restart local stack** (`npm run dev` / API :8742 + web :5173) and smoke: chat, Bible workspace, intelligence flag on, storyboard proposal path.  
4. **Run Playwright** Co-Director + `@critical` against the committed WIP; fix any regressions before merging elsewhere.

### P1 — Integrate Production Systems Readiness

5. **Merge or rebase** `phase2/production-systems-readiness` into the Co-Director tip (or open a PR) so `/api/capabilities` is the single readiness source.  
6. **Retarget M2.2 tool capability probes** to PSR registry (or shared module) — avoid a third matrix.  
7. Keep generation claims honest until a real render is verified.

### P2 — Close the generation loop (M2.5)

8. **Implement M2.5** per approved plan (`m2.5_vision_validation_*.plan.md`): validation engine, reports, mock + local technical providers, clear `visualValidationPending`, human review, bounded correction proposals.  
9. Storyboard vertical slice: generate → validate → correct → approve → Bible/scene link.

### P3 — Environment and packs

10. Start **ComfyUI** and resolve IC-LoRA / Essential Pack source URLs (or keep `not_configured` honest).  
11. Decide Essential Pack **publish** path when ready (authoring worktree already prepared; catalog stays unpublished until intentional).

### P4 — Product hygiene

12. Resolve FE dual planning (`planFromIntention` vs M2.4 plans).  
13. Document operator enablement: `STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2=1`.  
14. Optional: merge pack-authoring docs/tooling when publishing becomes a milestone.

---

## 8. Suggested near-term sequence

```text
1. Commit M2.3 + M2.4 WIP
2. Smoke + E2E green on Co-Director branch
3. Merge PSR → Co-Director tip
4. Implement M2.5 vision validation
5. Verify with Comfy only when environment is real
```

---

## 9. Reference documents

| Doc | Location |
|---|---|
| M2.3 preflight / completion | `docs/codirector/m2.3-production-bible-*.md` |
| M2.4 preflight / completion / intelligence | `docs/codirector/m2.4-intelligence-*.md`, `docs/codirector/intelligence/` |
| Production Bible domain docs | `docs/production-bible/` |
| M2.5 plan | `.cursor/plans/m2.5_vision_validation_*.plan.md` |
| PSR reports (worktree) | `AIVideoStudio-psr/docs/audit/ADEPT_PRODUCTION_*` |
| Pack authoring report (worktree) | `AIVideoStudio-pack-authoring/docs/audit/ESSENTIAL_PACK_*` |

---

## 10. Bottom line

**Built:** Co-Director through M2.4 (intelligence) on disk; PSR and pack authoring complete in sibling worktrees.  
**Running:** Nothing essential answered health checks at report time.  
**Pending for a coherent product:** commit Co-Director WIP → merge PSR → implement M2.5 → stand up Comfy/models when claiming generation readiness.
