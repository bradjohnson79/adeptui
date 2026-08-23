> **HISTORICAL — SUPERSEDED BY CHARACTER CREATOR V2.**

# Character Creator Generate Hard-Block Repair — Completion Report

**Date:** 2026-08-14  
**Branch:** `beta`  
**HEAD:** `b55db6237b12f593ed76536c5a921262e46da92e`  
**Governing addendum:** `docs/release-gate/character-creator/FULL_STACK_CERTIFICATION_ADDENDUM.md`

This is the governing completion document for the Character Sheet Generate unblock. It supersedes the earlier READY FOR MANUAL BETA draft in this file.

---

## Verdict

**CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED**

Independent verifier result is recorded below. Do not treat source, unit tests, production build, or Vercel READY as this verdict.

---

## What was broken

Hosted Character Creator Express blocked Generate for Illustrious when a Character Reference was attached (`illustrious requires text-to-image generation and cannot use the attached Character Reference.`). Product law: Illustrious/Qwen stay **Profile Guided** with a reference attached. Only **UNSUPPORTED** blocks Generate.

Live addendum work also found two Z-Image execution defects that are not “dropdown-only”:

1. Character Sheet picked a stale generated `hero_identity` whose file was gone instead of the uploaded Character Reference (`reference_image`).
2. Production Dock treated explicit `zimage` as an unlocked legacy default and overwrote it with Qwen, so the worker applied Qwen steps/CFG to `zimage.ref_edit` and tripped `WORKFLOW_GRAPH_DRIFT`.

Both were repaired and re-run live. They are necessary for Z-Image reference-conditioned E2E; they are not a Character Creator redesign.

---

## Candidate count (product vs E2E)

Express E2E certification used `candidateCount=1` (1 candidate × 4 views) for the minimal live proof.

Normal production UX remains Amendment F5: **4** candidates × 4 views (`CHARACTER_SHEET_PRODUCT_CANDIDATE_COUNT = 4` in `studio-web/src/components/character/characterSheetGenerate.ts`). The E2E override is `CHARACTER_SHEET_E2E_CANDIDATE_COUNT = 1` and is not the product contract.

---

## Implementation

| Area | Change |
| --- | --- |
| Mode resolver | `resolveCharacterGenerationMode` — only UNSUPPORTED disables Generate |
| Click path | Starting… / Generating…, `generationMode`, visible errors |
| Product candidate count | Default **4**; E2E may pass `1` |
| Provenance | `LOCAL — Illustrious XL — Profile Guided` (and family-specific equivalents) |
| Reload hydration | GET visual-sheet remounts candidate grid |
| Recommend / compile | Explicit Illustrious/Qwen kept; forced workflow does not silent-fallback |
| Visual sheet | Mixed-mode routing; 4-view prompts |
| Reference pick | Prefer `reference_image`, skip unreadable files |
| Family lock | Character Sheet enqueue sets `lockModelFamily`; compile + worker honor pinned `zimage.*` |

---

## Tests (preconditions — not certification)

- Character candidate routing: **41 passed**
- Forced Z-Image compile + locked dock family + routing: **43 passed** in the focused slice
- Two pre-existing `test_m42_w3_image_product.py` FLUX-vs-Qwen/Z-Image default failures are unchanged and are not this gate

---

## Hosted deploy / runtime

| Field | Value |
| --- | --- |
| Alias | https://adeptui.vercel.app/ |
| Topology | Vercel frontend → live Studio API `:8758` → ComfyUI `:8188` |
| GPU | NVIDIA GeForce RTX 5090 |
| ComfyUI | reused PID 42748 (not killed) |
| Studio API | restarted onto family-lock + readable-reference repairs |

Studio API is not hosted on Vercel. Python repairs required a local uvicorn restart.

---

## Live E2E (observed)

One project: Schnick Coffee / Korri. No new project.

### Illustrious (mandatory hosted click)

Generate click → Starting…/Generating… → POST accepted → `profile_guided` persisted → `illustrious.txt2img` → Comfy executed → four views → sheet `fedab2d3-…` → hosted candidate → provenance **`LOCAL — Illustrious XL — Profile Guided`** → remains after refresh.

### Z-Image (runtime available — live reference-conditioned)

POST `candidateCount=1` `reference_conditioned` (hosted Generate would enqueue 4 candidates; E2E may use 1). After the two repairs: `zimage.ref_edit`, source `60639fa9` (uploaded Korri Front View), four views + sheet `94275a19-…`, Library 5/5, hosted reload provenance **`LOCAL — Z-Image Turbo — Reference Conditioned`**.

### Qwen (runtime available — live Profile Guided)

POST `candidateCount=1` `profile_guided`. `qwen2512.txt2img`, `source_asset_id=None`, `referenceLocked=false`, four views + sheet `2ab0a7bc-…`, Library 5/5, hosted reload provenance **`LOCAL — Qwen Image 2512 — Profile Guided`**.

### Failure path

Local+Cloud OFF → Generate disabled. API both-null → 400 `VISUAL_SHEET_ERROR`.

Screenshots: `tests/e2e/screenshots/character-sheet-unblock/01` through `06`.  
Evidence log: `.runtime/character-sheet-unblock-e2e-evidence.md`

---

## E2E TRACE

```
E2E TRACE
User action:        PASS  (hosted Generate click, Illustrious + reference; Z-Image/Qwen live POSTs with candidateCount=1)
Frontend:           PASS  (enabled Generate, Starting/Generating, hosted candidate grid after reload)
API:                PASS  (POST /visual-sheet/generate 200; both-off 400)
Backend:            PASS  (PROFILE_GUIDED illustrious/qwen; REFERENCE_CONDITIONED zimage.ref_edit; no silent substitute on successful passes)
Persistence:        PASS  (Library 5/5 per engine; pack GET after reload)
Runtime/provider:   PASS  (local Comfy RTX 5090; Illustrious txt2img; Z-Image ref_edit; Qwen txt2img)
Result:             PASS  (four views + composed sheet per engine)
Reload:             PASS  (hosted candidate + required provenance strings remain)
Downstream:         PASS  (roleAssets attached; Spatial Map not in scope)
```

---

## Limitations (honest)

- Express E2E used `candidateCount=1`. Production Generate still sends **4** candidates unless overridden.
- Pack `status` can remain `GENERATING` after the four views and composed sheet exist, because later coverage phases may still be queued. The required 4-view candidate and Library assets are present.
- Queue worker completion message may say `ImageGen (edit) complete` even for `kind=imagegen` Qwen txt2img. Job kind, workflow key, and `source_asset_id=None` are the authority.
- Independent verifier noted Qwen `params.checkpoint` can still say `flux1-kontext-dev.safetensors` while `workflowKey`, engine, and `fallbackApplied: false` are Qwen. Treated as stale metadata, not a silent family swap on the successful pass.
- Illustrious/Z-Image jobs may still record dock `imageFamily: qwen2512` in productionDock metadata. Execution family/workflow on the successful passes matched the selected engine (`lockModelFamily`).
- Working-tree backend repairs for readable reference selection and family lock sit on top of `b55db62` until committed.

---

## Manual review path

1. Open https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=characters&characterId=c49371ed-ba6b-4c16-ba98-a8b28b72118b
2. Confirm Local ON, Cloud OFF. Current pack after the last live pass is Qwen Profile Guided.
3. Confirm the candidate shows **`LOCAL — Qwen Image 2512 — Profile Guided`** (or regenerate Illustrious/Z-Image only if you want a fresh sheet; live 4-view passes already completed).
4. Do not treat a new hosted Generate click as a cheap check: product candidate count is **4** × 4 views.

---

## Independent verifier

Independent inspection ([Independent E2E verifier](a8afe002-a52b-452d-a553-773d11b90f75)) of live hosted UI screenshots 01–06, live visual-sheet pack, Library IDs, on-disk files, and job workflow keys/Comfy prompt IDs — not source/tests as certification:

**VERIFIED — FULL-STACK E2E PASSED**
