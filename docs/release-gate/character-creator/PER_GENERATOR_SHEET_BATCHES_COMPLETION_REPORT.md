> **HISTORICAL — SUPERSEDED BY CHARACTER CREATOR V2.**

# Per-Generator Character Sheet Batches — Completion Report

Governing increment: per-generator Character Sheet batches + API shortlist + close-up portrait law.

Branch: `beta` (working tree). Studio API live at `http://127.0.0.1:8758/`. Hosted UI at `https://adeptui.vercel.app/` was **not** redeployed (no commit/push this session).

Project reused: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` / Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`.

## Verdict

**NO-GO — PER-GENERATOR BATCH GENERATION NOT FULLY VERIFIED**

**NO-GO — CLOSE-UP GENERATION STILL NOT PRODUCTION-READY**

Routing and expansion are live-proven on Studio API. Hosted Character Creator UI is implemented in source/`studio-web` dist but not on Vercel. Close-up still generates multi-panel design sheets instead of a single head-and-shoulders portrait.

## What shipped in source

- Character-only generator panel with Local master, Auto Select exclusivity, per-family Use + Batches 1–4, Cloud master, Setup-discovered API shortlist (`providerId` + `modelId`), and a visible Generation Plan.
- Request lists replace global `candidateCount=4`. Default per generator is **1**.
- Backend expands enabled `batchCount`s. Unchecked sources create zero jobs. Auto Select contributes zero when any explicit local family is checked.
- Persisted lineage: `batchIndex` / `batchOf` (1-based), `viewRole=front_closeup`, API `providerId`+`modelId`.
- Generator preferences saved separately from candidate authority (`PUT .../visual-sheet/preferences`).
- Close-up negatives no longer fall back to full-body “No close-up”. Compiler “Character sheet mode” is no longer attached to per-view jobs.
- Prop Creator `GeneratorSourceSelector` unchanged.

## Tests

Frontend (vitest): character generator plan, generate request, provenance/batch label — passed.

Backend: `97 passed` across routing, composition, illustrious, plus new `test_character_sheet_batch_expansion.py`.

`studio-web` production build passed.

## Live E2E TRACE

### Scenario A — Illustrious × 2 + Qwen × 1, Cloud OFF

| Stage | Result |
| --- | --- |
| User action | API POST with list-shaped `generatorSources` (hosted checkbox UI not on Vercel) |
| Frontend | IMPLEMENTED, not hosted-verified |
| API | PASS — accepted list expansion |
| Backend | PASS — 3 candidates, 12 view jobs |
| Persistence | PASS — 3 composed sheets in Library |
| Runtime | PASS — 8 `illustrious.txt2img` + 4 `qwen2512.txt2img`, ZERO API |
| Result | PASS counts; close-up tiles FAIL visual gate |
| Reload | N/A for hosted UI |
| Downstream | Sheets ingested; later runs replaced the live pack |

Observed enqueue:

- cand 0 Illustrious Batch 1 of 2 — 4 views, `viewRole=front_closeup`
- cand 1 Illustrious Batch 2 of 2 — 4 views
- cand 2 Qwen Batch 1 of 1 — 4 views

Sheets: `20c0cf43-…`, `d9e76d7e-…`, `dc8e9d51-…`. Evidence under `docs/release-gate/character-creator/evidence/`.

### Scenario B — Z-Image × 1 with reference

PASS routing: 1 candidate, 4 `zimage.ref_edit` jobs, `REFERENCE_CONDITIONED`, no Profile Guided substitution. Sheet completed.

### Scenario C — one API model checked, another unchecked

Kie image models were Ready (`nano-banana`, `flux`). Enqueue PASS:

- Nano Banana — Kie.ai × 1 → 4 API view jobs
- FLUX unchecked → **0** jobs
- `providerId=kie`, `modelId=nano-banana`

Not marked PASS from mocks.

### Close-up visual

Independent inspection of generated tiles (not prompt strings):

- First Illustrious close-ups were collages / contact sheets / too-wide medium shots.
- After disabling compiler character-sheet mode, a dedicated Illustrious recheck (`sheet=96d9acdd-…`, `closeup=49b4c8d2-…`) still produced a multi-panel design sheet rather than one head-and-shoulders portrait.

FAIL against: front-facing head-and-shoulders only, no full-body in the fourth tile, no collage.

## Remaining

1. Ship `studio-web` to Vercel `adeptui.vercel.app` (commit + push `beta`) and repeat Scenario A from hosted checkboxes.
2. Close-up still needs a generator-specific single-portrait lock; prompt/negative changes alone did not stop Illustrious design-sheet collages.
3. Restart Studio API after any further Python change using Beta env (`STUDIO_FEATURE_CHARACTER_IDENTITY_V1=1`). Do not start uvicorn without that env.

## GO / NO-GO

**NO-GO**
