# M42 Wave 3 — Implementation Report

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 3 — Image Product Integration |
| **Product** | Adept UI Studio — filmmaker image product layer |
| **Branch** | `phase2/m42-image-product-integration` |
| **Baseline** | `phase2/m42-certified-image-workflows` (Wave 2 **GO**; `wave2Go: true`) |
| **Baseline SHA** | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| **Date** | 2026-07-29 |
| **Verdict** | **GO** |
| **wave3Go** | `true` |
| **Final cert** | [`M42_W3_FINAL_CERTIFICATION.md`](./M42_W3_FINAL_CERTIFICATION.md) |

---

## Executive summary

Wave 3 exposes the Wave 2 certified image runtime as a filmmaker-facing product layer. All product surfaces compile through:

```text
CreativeContext → recommend / prompt_intel → ImageIntent
  → WorkflowResolver (allow_draft=False) → pinned imageRuntime
  → QueueWorker (execute-only) → Output Gate → Asset Library + ImageProvenance
```

No product surface builds Comfy graphs. Production execution remains Certified keys only (`zimage.txt2img`, `zimage.ref_edit`). FLUX / Qwen / Imagen may be recommended; execution falls back to certified ZImage when those families are not Certified — readiness stays honest (Draft / Deferred / Blocked).

---

## Gate conjunction (all true)

| Flag | Status |
|---|---|
| GenerateStudioIntegrated | ✓ |
| CoDirectorImageIntelligenceOperational | ✓ |
| ModelRecommendationOperational | ✓ |
| CostResourceIntelligenceOperational | ✓ |
| WhyThisModelOperational | ✓ |
| ImageSessionPresetsOperational | ✓ |
| CharacterBuilderOperational | ✓ |
| EnvironmentBuilderOperational | ✓ |
| StoryboardOperational | ✓ |
| AssetLibraryIntegrated | ✓ |
| ProvenanceGraphOperational | ✓ |
| ProductionCollectionsOperational | ✓ |
| ReferenceManagementOperational | ✓ |
| PromptIntelligenceOperational | ✓ |
| ProductionBibleIntegrationOperational | ✓ |
| ProjectPersistenceOperational | ✓ |
| JobMonitoringOperational | ✓ |
| RuntimeCertificationPreserved | ✓ (`wave2Go`) |

Evaluator: `evaluate_image_wave3_gate()` → `GET /api/image-product/gate`  
Artifact: [`artifacts/m42/w3/wave3_gate_results.json`](../../../artifacts/m42/w3/wave3_gate_results.json)

---

## What shipped

### 1. Image Product package (`studio-api/app/image_product/`)

| Module | Role |
|---|---|
| `compile.py` | CreativeContext + request → ImageIntent; digest only into runtime |
| `recommend.py` | Family recommendation + cost/VRAM/time + `whyThisModel` |
| `presets.py` | 8 built-ins + project CRUD |
| `prompt_intel.py` | Expand prompt with camera/lighting/composition/continuity |
| `references.py` | ReferenceAsset CRUD + UI `{assetId,role}` → referenceIds |
| `collections.py` | Production Collections CRUD + seeded named groups |
| `history.py` | Project intent/prompt history persistence |
| `service.py` | Compile + enqueue batch jobs |
| `api.py` | FastAPI `/api/image-product/*` |
| `production_gate.py` | `wave3Go` evaluator |

Config: `config/image-runtime/cloud-price-table.json`

### 2. API surface

- `POST /api/image-product/generate` · `/projects/{id}/generate`
- `POST /api/image-product/recommend`
- `POST /api/image-product/expand-prompt`
- `GET /api/image-product/families`
- Presets / collections / references CRUD under `/projects/{id}/…`
- `GET /projects/{id}/history` · `prompt-history`
- `GET /api/image-product/gate`

### 3. Legacy migration

Hardcoded `workflowPreference: "zimage.txt2img"` removed from `ops.enqueue_imagegen`. Callers route through the product compiler:

- `studio-api/app/routers/extra.py` (`/imagegen`)
- `studio-api/app/generation_tools/ops.py`
- `studio-api/app/storyboard_jobs.py`
- `studio-api/app/codirector/production_intent/execute.py`
- `studio-api/app/codirector/tools/handlers/media_execution.py`
- `studio-web/src/codirector/execute.ts`

Artifact: `artifacts/m42/w3/legacy_callers_migrated.json`

### 4. Generate Studio

`ImageGenPanel.tsx` evolved to production Generate Studio (`workspaces.ts` → `futureDestination: "generate"`):

- Family selector from readiness (ZImage / FLUX / Qwen / Imagen + status badges)
- Session preset picker (built-ins + project-saved)
- Recommendation card: family + whyThisModel + time/VRAM/cost (overridable)
- Batch 1–8; server-backed prompt history
- Modes → ImageIntent operation (no workflow-key picker)
- `api.imageProduct.generate` / `recommend` / presets

### 5. Co-Director image intelligence

- `propose_image_generate` preview: recommend + prompt_intel before approve
- Preview lines: whyThisModel + estimates (local vs cloud)
- Tool schema: purpose / modelFamilyPreference / presetId / acceptExpandedPrompt
- ProductionIntent `_image_generate` → `image_product` only
- Web queue actions → `api.imageProduct.generate`
- CreativeContext digest from Bible when available

### 6. Character + Environment builders

- Character: front / side / rear / expression / costume via `builtin-character-sheet` + ReferenceAsset bridge
- Environment: concept / room / landscape / city / spacecraft / fantasy / background via `builtin-environment-sheet` (M2.13 camera-spin preserved)

### 7. Storyboard + Asset Library + Collections

- Storyboard frame enqueue via Image Product (`purpose: storyboard`, continuity IDs in metadata)
- Library: favorites, modelFamily / hasReferences / collectionId filters, provenance + generation-history inspector, gate thumbnails
- Production Collections: seeded groups + CRUD + add asset

### 8. Job monitoring

QueueWorker `_imagegen` emits `ImageJobStage` on `job.stage`:

```text
Queued → Preparing → LoadingModels → Sampling → Validating → RegisteringAsset → Completed
(Failed / Cancelled terminal)
```

JobPanel renders the stage pipeline for image jobs.

---

## Image Session Presets (built-in)

Concept Art · Storyboard · Character Sheet · Environment Sheet · Marketing Artwork · YouTube Thumbnail · Poster · Matte Painting

Each stores: `preferredModelFamily`, `aspectRatio`, `qualityPreset`, `resolution`, `guidance`, `promptTemplate`, `defaultReferenceAssetTypes[]`.

See [`M42_W3_SESSION_PRESETS.md`](./M42_W3_SESSION_PRESETS.md).

---

## Recommendation envelope

```yaml
recommendedFamily: flux | qwen | imagen | zimage
whyThisModel: "…"
estimates:
  generationTimeSec: number
  vramGb: number | null
  costUsd: number | null
  costLabel: "Local GPU" | "$0.04"
  providerKind: local | cloud
alternatives: [...]
overridable: true
```

Rules: photoreal → FLUX (else ZImage); stylized/anime → Qwen (else ZImage); cloud edit → Imagen (else `zimage.ref_edit`). Never invent Certified status.

See [`M42_W3_COST_INTELLIGENCE.md`](./M42_W3_COST_INTELLIGENCE.md).

---

## Tests

| Suite | Result |
|---|---|
| `studio-api/tests/test_m42_w3_image_product.py` | **12 passed** |
| `studio-api/tests/test_m42_w2_image_runtime.py` | **11 passed** (runtime preserved) |
| Product package builder-import ban | pass |

Coverage: recommend (+why/cost), presets, collections, compile (no `workflowPreference`), references, prompt_intel, history, ImageJobStage enum, gate structure.

See [`M42_W3_TEST_REPORT.md`](./M42_W3_TEST_REPORT.md).

---

## Companion reports

| Report | Topic |
|---|---|
| [`M42_W3_ARCHITECTURE.md`](./M42_W3_ARCHITECTURE.md) | Product → runtime ownership |
| [`M42_W3_GENERATE_STUDIO.md`](./M42_W3_GENERATE_STUDIO.md) | Generate Studio surface |
| [`M42_W3_CODIRECTOR.md`](./M42_W3_CODIRECTOR.md) | Co-Director image intel |
| [`M42_W3_BUILDERS.md`](./M42_W3_BUILDERS.md) | Character / Environment |
| [`M42_W3_STORYBOARD_LIBRARY.md`](./M42_W3_STORYBOARD_LIBRARY.md) | Storyboard + Library |
| [`M42_W3_COLLECTIONS.md`](./M42_W3_COLLECTIONS.md) | Production Collections |
| [`M42_W3_SESSION_PRESETS.md`](./M42_W3_SESSION_PRESETS.md) | Session presets |
| [`M42_W3_COST_INTELLIGENCE.md`](./M42_W3_COST_INTELLIGENCE.md) | Cost / whyThisModel |
| [`M42_W3_JOB_MONITORING.md`](./M42_W3_JOB_MONITORING.md) | ImageJobStage |
| [`M42_W3_GATE_REPORT.md`](./M42_W3_GATE_REPORT.md) | Gate conjunction |
| [`M42_W3_FINAL_CERTIFICATION.md`](./M42_W3_FINAL_CERTIFICATION.md) | Binary GO + Wave 4 handoff |

---

## Artifacts (`artifacts/m42/w3/`)

`prerequisites.json` · `generate_studio_results.json` · `codirector_results.json` · `model_selection_results.json` · `cost_intelligence_results.json` · `presets_results.json` · `character_builder_results.json` · `environment_builder_results.json` · `storyboard_results.json` · `asset_library_results.json` · `collections_results.json` · `reference_results.json` · `project_persistence_results.json` · `job_monitor_results.json` · `legacy_callers_migrated.json` · `unit_test_results.json` · `wave3_gate_results.json`

---

## Wave 4 handoff

Wave 3 owns filmmaker-facing image product integration.

Wave 4 owns advanced editing / reference workflows:

- Inpaint / outpaint / relight / ControlNet-class pipelines  
- Deeper reference-guided edit UX beyond `zimage.ref_edit`  
- No identity continuity enforcement (Wave 5)

---

## Explicit non-claims

- FLUX / Qwen / Imagen are **not** Production Ready unless Wave 2-style live dual-stage certification exists  
- No Wave 2 runtime redesign; no fabricated Certified status  
- No advanced editing pipelines (Wave 4)  
- No identity continuity enforcement (Wave 5)  
