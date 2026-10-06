# ERS Full-Sheet GPT Image 2 Certification

**Governing document for this milestone.** Historical component-default reports remain historical. They do not define the normal GPT Image 2 API path.

**Success:** `GO — GPT IMAGE 2 ONE-PASS FULL ERS + CHARACTER CANON + TARGETED REPAIR PIPELINE LIVE E2E CERTIFIED`

**Failure:** `NO-GO — GPT IMAGE 2 ONE-PASS ERS PIPELINE NOT CERTIFIED`

---

## Previous architecture

Normal GPT Image 2 API ERS ran a sequential paid pipeline:

`Master → North → East → South → West → 3D → Occupied` (6–7 Kie I2I jobs)

then a free 2K dashboard compose. `ers_pipeline=components` was the GPT default.

## New architecture

```text
Spatial Map + character canon + cameras
        ↓
compile_environment_reference_sheet_prompt (ers.original.v1)
        ↓
ONE gpt-image-2-image-to-image job
        ↓
validate (per-panel + identity gate)
        ↓
GPT PNG (visual) + Adept machine JSON
        ↓
Library / Scene Creator / Timeline
```

Targeted repair keeps the component pipeline. Full-sheet provider failure does **not** auto-fan-out into seven paid jobs.

| Mode | When |
| --- | --- |
| `generationMode=full_sheet_api` / `ers_pipeline=full_sheet` | Normal GPT API Generate / Regenerate |
| `generationMode=components` / `ers_pipeline=components` | Targeted retry + historical packages |
| `ers_pipeline=collage` | Local / non-GPT empty pipeline (unchanged) |

## Full-sheet prompt

Compiler: `compile_environment_reference_sheet_prompt` in `studio-api/app/codirector/knowledgebase/ers_compiler.py`.

- Template `ers.original.v1`
- Explicit PANEL 1–9 headings (Hero, Spatial, Structural/3D, N/E/S/W, Materials, Lighting, DNA, Continuity, Occupied)
- Spatial Map authority + layout negatives (no dashboard, no omitted/reordered panels, no generic person)
- Occupied identity language is generated from Character Creator canon. Jacob is never hardcoded.

## Input reference roles

Kie GPT Image 2 I2I uses `input_urls` (max 2 in this path):

1. Approved Character Creator hero when Panel 9 requires a saved character
2. Spatial Map / Atlas / original environment

Character pixels are never dropped to keep an optional environment slot. Missing character refs fail `CHARACTER_REFERENCE_UNAVAILABLE`.

Aspect: 16:9 (original sheet 1672×941 class). Operation: `gpt-image-2-image-to-image` only.

## Character grounding

Unchanged resolver: Spatial Map `characterId` → `resolve_character_for_generation` → approved hero + CRS JSON.

Jacob cert fixture (do not recreate):

| Field | ID |
| --- | --- |
| Project | `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Character | `10303eba-ed95-49fe-a86b-e5493b7a1c75` |
| Approved hero | `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` |
| Map | `477b450c-734d-49ae-a40a-51402e0a832f` |

## Generation count

| Path | Paid GPT Image 2 jobs |
| --- | --- |
| Previous normal ERS | 6–7 |
| New normal Generate | **1** |
| New normal Regenerate | **1** |
| Occupied identity repair | 1 component + free restitch |
| Full-sheet provider failure | Retry same 1 job. No hidden 7-job fallback. |

## Performance / cost

Record live timings in evidence when the Playwright paid pass runs:

```text
Previous API ERS: 7 component generations, total = X
New API ERS: 1 full-sheet generation, total = Y
improvement = X - Y
```

Do not claim improvement without measured live numbers. Do not publish API credentials.

## Validation

- Per-panel status on provenance (`Panel 1–9`)
- Occupied identity: crop Panel 9 → `apply_occupied_identity_gate`
- `FAIL_CHARACTER_IDENTITY` is blocking for that panel. The sheet is kept as a repair candidate.
- Advisory layout/environment gate remains advisory.

## Machine JSON

Adept writes `ers-machine-{pkg}.json` from Spatial Map, character IDs/revisions, cameras, placements, and provenance. GPT chrome text is never parsed as production truth.

## Targeted repair

Component pipeline is retained. Panel 9 cover-fit compositor (`compose_occupied_into_collage`) restitches onto `ers.original.v1` using fractional geometry so GPT 16:9 output is allowed. Repair provenance: `originalFullSheetAssetId`, `replacementComponent`, `replacementAssetId`, `repairRevision`, `restitchCompositeAssetId`.

Regenerate = new full-sheet job. Retry failed component = `retry_component` only.

## Backward compatibility

Historical `generationMode=components` packages still load. `directional_assets` are optional on `full_sheet_api`. Scene Creator `has_reference` is true when the composite exists. Mini never ingests the chrome composite; it prefers master, then a lazy hero crop from `ers.original.v1`, then Atlas.

## Downstream handoff

Visual ERS + machine JSON + Spatial Map + canonical characters. No fabricated directional IDs. Lazy derived crops may be created on demand (`derivedFrom=fullSheetAssetId`). Scene Creator Mini A/B, lens, fisheye, lighting, inpaint, and approval are unchanged.

## Progress

Normal full-sheet phases:

Preparing Environment Reference Sheet → Resolving characters and scene canon → Generating full ERS with GPT Image 2 → Validating ERS → Saving ERS → Complete

No fake Master/North/East sequential jobs. No fake percentages.

## Timeline Express

Co-Director nav: Wiki · Notes · Story · Script Writer · Character Creator · Prop Creator · Spatial Map · Scene Creator · **Timeline** · Library

Timeline Express is an informational doorway. **Open Timeline** uses `onGoTab("timeline")` into Timeline Standard. No Express editor, no second Timeline store.

## Tests

- `studio-api/tests/test_ers_full_sheet.py`
- `studio-api/tests/test_ers_component_pipeline.py` (GPT default `full_sheet`)
- `studio-api/tests/test_ers_knowledgebase_compiler.py`
- `studio-api/tests/test_ers_image_product.py` (one GPT job + `generationMode`)
- `studio-web/.../useErsGeneration.test.ts`
- `studio-web/.../timelineContracts.test.ts`
- Playwright: `tests/e2e/codirector/spatial-map-ers-regenerate-button.spec.ts`
- Playwright: `tests/e2e/codirector/codirector-navigation-fix.spec.ts` (Timeline after Scene Creator)

## Live evidence

| Gate | Result |
| --- | --- |
| One paid GPT Image 2 job | PASS — 1 child `gpt-image-2-image-to-image` |
| Original 9-panel layout | PASS — `ers.original.v1` visual sheet |
| Jacob in Panel 9 | PASS after targeted Occupied repair |
| Machine JSON present | PASS — `ers-machine-ce289fb6.json` |
| Stale clears | PASS — fingerprint `e24f7e25a28e5d14` matches map |
| Persistence after reload | PASS — Playwright + API |
| Scene Creator / Timeline handoff | PASS — same project |
| Composer 2.5 | PASS (implementation + repair) |

Review URLs: Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`

## LIVE JACOB CERTIFICATION

Date/time: 2026-08-29 05:04–05:20 UTC (Pacific 2026-08-28 22:04–22:20)

| Field | Value |
| --- | --- |
| Project | SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Character | Special Agent Jacob Barnes `10303eba-ed95-49fe-a86b-e5493b7a1c75` (`APPROVED`) |
| Character revision | CRS 1 / version `324017d4-19f2-4ff3-97dd-10c72f8ef780` |
| Approved hero | `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` |
| Spatial Map | Observatory Control Room `477b450c-734d-49ae-a40a-51402e0a832f` v141 |
| Environment / Atlas asset | `62888b73-2511-4323-8db3-634c94c609fc` |
| Sheet | `93c89cd1-f3db-4c88-971b-6fb7aeaa5504` |
| Package | `ce289fb6-41b1-470a-a783-72109c6fd046` |
| Generation mode | `full_sheet_api` / `ers_pipeline=full_sheet` |
| Template | `ers.original.v1` |
| Model | `gpt-image-2-image-to-image` (hosted `gpt-image-2-kie`) |
| Provider | kie |

Precheck: API `http://127.0.0.1:8758/api/healthz` 200; UI `http://127.0.0.1:5173/` 200. Stale API from 20:34 was restarted to PID started 21:59 before spend. Comfy was down for the paid run and was **not** required. No new Jacob, project, or map.

### Initial Generate / Regenerate

Playwright `tests/e2e/codirector/spatial-map-ers-regenerate-button.spec.ts` with `ADEPT_ALLOW_KORRI_MUTATION=1`, retries=0.

- Request: `capability=ers.generate`, `ers_pipeline=full_sheet`, `forceFull=true`, no `retry_component`
- Parent execution `2b5874bd-5d44-4bb7-a9ff-e964488ce987`
- Paid child jobs: **1** — `8e31170c-2a18-4558-bcc3-853b76939f9e`
- Purpose: `environment_reference_sheet`
- No Master / N / E / S / W / 3D / Occupied child fan-out
- Progress stages: Preparing → Resolving characters and scene canon → Generating full ERS with GPT Image 2 (no component list)

Sanitized reference order (runtime `params_json`, not inferred):

```text
input_urls[0] → asset 90e8c04a-…  role=character_identity
input_urls[1] → asset 62888b73-…  role=environment
```

Prompt contract (runtime): starts with `CREATE ONE COMPLETE ENVIRONMENT REFERENCE SHEET`, identifies `ers.original.v1`, PANEL 1–9, Spatial Map authority, negatives (no dashboard / no redesign / no generic person). Dynamic identity language includes Special Agent Jacob Barnes because he is the saved character. Compiler has no hardcoded Jacob.

Visual result: one GPT PNG `7cb4a3ec-91f3-4749-8520-c3b2971b7c6e` (`imagegen_kie_55ba3201.png`). Coherent original 9-panel sheet (Hero, Spatial, Structural/3D, N/E/S/W, Materials, Lighting, DNA, Continuity, Occupied). Extra camera chrome at the bottom is cosmetic, not a missing-panel fail.

### Panel 9 identity + targeted repair

Initial full-sheet identity gate: `FAIL_CHARACTER_IDENTITY`. Root cause: `ers.original.v1` occupied crop is a short lower-right strip; the crop (`ers-panel9-7cb4a3ec.png`) showed waist-down + camera chrome, not Jacob's face. The full sheet Occupied cell did show a suited figure.

Governed Occupied-only repair (API equivalent of Retry; complete-state monitor had no Retry at the time):

- Execution `83b61f14-c11c-49a5-b987-8193aeaec0e8`
- Paid jobs: **1** — `662e4ef5-5502-465b-8fd8-1be1a4aba17b` label `Occupied scale`
- `ers_pipeline=components`, `retry_component=occupied`, `occupiedOnly=true`
- Refs again: slot 1 Jacob `90e8c04a-…`, slot 2 environment `62888b73-…`
- Occupied asset `3f357c5e-e840-409b-83f1-484d62068b37`
- `identityGateResult=PASS` — “accurately depicts Special Agent Jacob Barnes…”
- Restitch `19ec1b83-1ed4-4cd5-b69f-65f3527803f8` (`ers-composite-ce289fb6.png`)
- Repair provenance: `originalFullSheetAssetId=7cb4a3ec-…`, `replacementComponent=occupied`, `replacementAssetId=3f357c5e-…`, `repairRevision=1`, `restitchCompositeAssetId=19ec1b83-…`
- No Master/N/E/S/W/3D paid jobs

Defects found and repaired (no second full-sheet spend):

1. Sheet provenance kept the initial FAIL after Occupied PASS — `stamp_repair_on_sheet` now writes identity + lineage; live sheet backfilled to PASS.
2. Complete-state monitor hid Retry — Retry now appears when Occupied stage is failed; PASS clears that stage.

### Machine JSON / provenance / fingerprint

- Adept machine JSON: `ers-machine-ce289fb6.json` (not OCR of GPT chrome)
- Contains Spatial Map, Jacob ID/revision, cameras, placements, `generationMode=full_sheet_api`, `ersTemplateId=ers.original.v1`
- Machine `directional_assets` are null (optional). Package may still list historical directional IDs from the reused package; they were not newly paid.
- Grounding fingerprint `e24f7e25a28e5d14` matches map v141. Stale banner did not show after reload.
- After backfill: sheet `identityGate=PASS`, `visualSheetAssetId=19ec1b83-…`

### Reload / downstream

- Playwright reload: same ERS image src persisted, monitor `data-phase=complete`
- Scene Creator: Use in Scene Creator accepted the package; opened `/project/0ffe56e2-…?workspace=scenecreator&sheet_id=93c89cd1-…` with Jacob + Observatory Control Room Spatial 1. No Mini generation.
- Timeline: Co-Director Timeline tab (after Scene Creator) → Open Timeline → `/project/0ffe56e2-…?workspace=timeline` (same project). Doorway only; Timeline editor not modified.

### Performance / cost

| | Paid jobs | User-visible time |
| --- | --- | --- |
| OLD (same map, exec `fe1abb62-…`, 2026-08-29 03:54–04:05 UTC) | 7 component jobs | ~11 min 0 s |
| NEW normal Generate | **1** full-sheet job | provider `elapsedSec=168` (~2 min 48 s); Playwright wall 2.3 min |
| Occupied identity repair (only because initial gate failed) | +1 occupied job | ~1 min 59 s |

Cost evidence is job-count only (no provider dollar metadata recorded): old normal 6–7 paid generations vs new normal 1. Repair adds 1 paid job when identity fails.

### Playwright

`spatial-map-ers-regenerate-button.spec.ts`: **1 passed (2.3m)** — request contract, full-sheet progress, completion, reload persistence.

### Composer

Implementation review: **PASS** ([Composer ERS architecture review](a4f2beec-97de-4f7a-b78e-fee013f92bb9))

Repair review: **PASS** ([Composer ERS repair review](2319829f-4e96-4d7f-8601-e025c4775e53))

Residual (non-blocking): `panelValidation.occupied` on the first persist may still say FAIL until a later rewrite; UI reads `identityGate`. Retry after identity fail appears after sheet hydrate.

## Composer verdict

Composer 2.5 review-only. No GLM. No Kimi. No second peer.

**PASS** (implementation + live-cert repair)

## Binary verdict

Live Jacob one-pass Generate produced exactly one paid GPT Image 2 job on the existing SenseNova / Jacob / Observatory fixtures. Occupied identity passed after the governed one-job targeted repair. Machine JSON, provenance, fingerprint, reload, Scene Creator, and Timeline doorway passed. Post-repair persist/Retry defects were root-caused and fixed; focused tests and Composer PASS.

**GO — GPT IMAGE 2 ONE-PASS FULL ERS + CHARACTER CANON + TARGETED REPAIR PIPELINE LIVE E2E CERTIFIED**

Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`.
