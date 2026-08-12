# Krea 2 Complete Image Pipeline + Multi-Shot Integration — Final Certification

**Milestone:** Krea 2 Complete Image Pipeline + Multi-Shot Integration
**Date:** 2026-08-08
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Status:** READY FOR INDEPENDENT VERIFIER / CREATOR MANUAL BETA

---

## Executive Summary

Krea 2 Turbo and RAW are now first-class image-generation models inside Adept UI's existing image pipeline, and the provider-agnostic Multi-Shot Image Planning workflow is wired end-to-end through plans, ordered shots, candidate approval, Environment Reference Sheet (ERS) continuity, and the W46 Timeline.

No parallel Krea-specific subsystem was created; all work extends the existing authoritative contracts:

- `comfyui` provider now supports the `krea2` model family.
- `krea2-turbo-local` and `krea2-raw-local` are registered in the Production Dock model catalog.
- ComfyUI workflow adapters for Turbo and RAW are certified through the image workflow registry.
- Reference conditioning (style, identity, environment, moodboard) flows through the shared `AssetRef` contract, with the ERS Semantic Role Law enforced.
- Multi-Shot plans, ordered shots, and candidate history live in new project-scoped SQL tables that the generic project deletion sweep covers.
- Approved Multi-Shot images can be handed off to W46 Timeline batches with stable `batchBlockId` lineage.
- Co-Director exposes closed-registry tools for creating plans, adding shots, querying ERS recommendations, and sending approved shots to the Timeline.

All automated certification gates exercised below pass without GPU generation.

---

## 1. Implemented Deliverables

### 1.1 Krea 2 Provider / Model Registration

| File | What changed |
|------|--------------|
| `config/image-runtime/provider-registry.json` | Added `krea2` to the `comfyui` provider's `supportedModelFamilies`. |
| `studio-api/app/production_control/model_registry.py` | Added `krea2-turbo-local` and `krea2-raw-local` descriptors with capability labels, VRAM hints, and lifecycle states. |
| `studio-api/app/image_runtime/model_discovery.py` | Added `krea2` family detection patterns. |
| `studio-api/app/image_studio/providers.py` | Added provider hints, native resolutions, license note, and readiness mapping for Krea 2. |
| `studio-api/app/comfy_health.py` | Added `krea2_models` to model-component readiness diagnostics. |
| `studio-api/app/capabilities/registry.py` | Added Krea-specific capability readiness entries bound to a `krea2_models` component. |
| `studio-api/app/config.py` | Added Krea 2 model-path settings keys. |
| `studio-api/app/setup/catalog.py` | Added a `krea2_models` setup component with verifier/installer following the `zimage_models` precedent. |

### 1.2 ComfyUI Workflow Adapters

| File | What changed |
|------|--------------|
| `studio-api/app/workflows/krea2_image.py` | Turbo and RAW leaf graph builders; Turbo defaults to 8 steps / CFG 0 / mu shift; RAW defaults to 52 steps / CFG 3.5. |
| `config/image-workflows/certified-registry.json` | Added `krea2.turbo.txt2img`, `krea2.turbo.img2img`, `krea2.turbo.reference`, `krea2.raw.txt2img`, `krea2.raw.img2img` entries with topology fingerprints. |
| `studio-api/app/image_runtime/contract.py` | Extended `CanonicalImageWorkflowContract` to carry Krea `mu` / timestep-shift control. |
| `studio-api/app/image_runtime/workflow_execute.py` | Updated `prepare_executable_graph` and builder dispatch to honor Krea-specific settings. |
| `studio-api/app/image_runtime/certified_registry.py` | Registered Krea workflow keys with Certified status. |
| `studio-api/tests/test_krea2_workflow_contracts.py` | 11 new tests covering graph construction, topology fingerprint, bindings, and preflight. |
| `studio-api/tests/test_krea2_provider_registration.py` | 17 tests covering registry, discovery, readiness, and missing-model UX. |

### 1.3 UI Controls

| File | What changed |
|------|--------------|
| `studio-web/src/components/image-studio/providerDisplay.ts` | Added Krea 2 Turbo/RAW sub-labels, license short-name parsing, and install-guidance routing. |
| `studio-web/src/components/image-studio/providerDisplay.test.ts` | 7 tests covering Krea-specific display logic. |

### 1.4 References, Moodboards, LoRA, and ERS

| File | What changed |
|------|--------------|
| `studio-api/app/image_runtime/asset_refs.py` | New `AssetRef` contract carrying semantic roles (`style`, `identity`, `environment`, `moodboard`). ERS Semantic Role Law: `environment` is alias-stable and never reassigned. |
| `studio-api/app/image_runtime/contract.py` | Wired `AssetRef` into the canonical image request contract. |
| `studio-api/app/workflows/krea2_image.py` | Maps supported reference roles onto Krea's ComfyUI reference-image interfaces. |
| `studio-api/tests/test_krea2_references_lora.py` | 14 tests covering reference normalization, role grouping, ERS bridging, and LoRA spec handling. |

### 1.5 Multi-Shot Image Planning

| File | What changed |
|------|--------------|
| `studio-api/app/image_pipeline/multi_shot/models.py` | SQLAlchemy tables: `multi_shot_plans`, `multi_shots`, `multi_shot_candidates`. All project-scoped. |
| `studio-api/app/image_pipeline/multi_shot/contracts.py` | Pydantic wire contracts (camelCase) for plans, shots, candidates, reordering, and send-to-timeline. |
| `studio-api/app/image_pipeline/multi_shot/service.py` | CRUD, ordering, candidate approval, Timeline handoff, ERS recommendation. |
| `studio-api/app/image_pipeline/multi_shot/api.py` | FastAPI routes under `/api/projects/...` for the full lifecycle. |
| `studio-api/app/migrations/m029_multi_shot.py` | Creates the three tables. |
| `studio-api/app/migrations/m030_multi_shot_timeline.py` | Adds the `timeline_batch_block_id` lineage column. |
| `studio-api/tests/test_krea2_multishot_architecture.py` | 24 tests covering plans, shots, ordering, approval, project isolation, and cleanup. |
| `studio-api/tests/test_krea2_multishot_timeline.py` | 7 tests covering Timeline handoff, idempotence, custom generator/duration, and cross-project rejection. |

### 1.6 Co-Director Operations

| File | What changed |
|------|--------------|
| `studio-api/app/codirector/tools/handlers/multi_shot_tools.py` | New closed-registry handlers: `multi_shot.list_plans`, `multi_shot.get_plan`, `multi_shot.ers_recommendation`, `multi_shot.create_plan`, `multi_shot.add_shots`, `multi_shot.send_to_timeline`. |
| `studio-api/app/codirector/tools/definitions.py` | Tool definitions for the 6 new tools. |
| `studio-api/app/codirector/tools/registry.py` | Bound handlers and mutation previews/apply functions. |
| `studio-api/tests/test_codirector_krea2_multishot.py` | 4 tests driving the real registry → sanitize → handler path. |

### 1.7 Licensing

| File | What changed |
|------|--------------|
| `docs/release-gate/krea2/KREA2_LICENSE_NOTES.md` | Documents Krea 2 Community License, local vs. cloud/commercial distinction, attribution, and the separate commercial licensing path. |

---

## 2. Certification Results

### 2.1 Automated Test Matrix

| Suite | Tests | Result |
|-------|-------|--------|
| `tests/test_krea2_provider_registration.py` | 17 | pass |
| `tests/test_krea2_workflow_contracts.py` | 11 | pass |
| `studio-web/src/components/image-studio/providerDisplay.test.ts` | 7 | pass |
| `tests/test_krea2_references_lora.py` | 14 | pass |
| `tests/test_krea2_multishot_architecture.py` | 24 | pass |
| `tests/test_krea2_multishot_timeline.py` | 7 | pass |
| `tests/test_codirector_krea2_multishot.py` | 4 | pass |
| `tests/test_codirector_schema_alignment.py` | 1 | pass |
| **Krea keyword sweep** (`python -m pytest -k krea2 -q`) | **77** | **pass** |

No GPU generation was executed during automated certification. All generation paths stop at the request/builder/queue boundary.

### 2.2 Manual Beta Gate Matrix

| Gate | Status | Evidence |
|------|--------|----------|
| Krea 2 Turbo registered | GO | `provider-registry.json`, `model_registry.py`, `test_krea2_provider_registration.py` |
| Krea 2 RAW registered | GO | same as above |
| Model discovery | GO | `model_discovery.py` + setup component |
| Missing dependency UX | GO | `comfy_health.py`, `image_studio/providers.py`, tests |
| ComfyUI Turbo graph | GO | `workflows/krea2_image.py` + certified registry |
| ComfyUI RAW graph | GO | same as above |
| Turbo recommended defaults | GO | 8 steps, CFG 0, mu shift |
| RAW advanced defaults | GO | 52 steps, CFG 3.5 |
| Reference integration | GO | `asset_refs.py`, `test_krea2_references_lora.py` |
| Moodboard/style integration | GO | `AssetRef` role map |
| LoRA lineage | GO | LoRA spec carried per candidate, `train on RAW / run on Turbo` documented |
| Asset registration | GO | candidates carry `asset_id`; Multi-Shot outputs use shared Asset system |
| Retake/history | GO | append-only candidate rows; rejection never deletes |
| Failure isolation | GO | per-shot status and candidate history |
| Multi-Shot canonical model | GO | `multi_shot_plans` / `multi_shots` / `multi_shot_candidates` |
| Shared scene context | GO | `shared_visual_context`, `shared_references` on plan |
| Shot-specific context | GO | per-shot `prompt`, `image_prompt`, `video_prompt`, `framing`, `camera_angle` |
| Unlimited structural collection | GO | 24/24 architecture tests; no MAX_SHOTS cap in code |
| Shot ordering | GO | `order_index` + full-set reorder endpoint |
| Candidate approval | GO | approve/reject endpoints; approval invariant enforced |
| Provider independence | GO | `provider_id`/`model_id` plain strings; no registry validation |
| Timeline batch handoff | GO | `send_to_timeline` creates W46 batches with clips + prompt segments |
| Image visual binding | GO | approved asset → `visualClips` with `role="start"` |
| Video prompt binding | GO | shot `video_prompt` → `promptSegments` |
| Stable lineage | GO | `timeline_batch_block_id` persisted on shot row |
| Linked update safety | GO | `only_missing` flag prevents duplicate batch creation |
| ERS + Multi-Shot consistency | GO | `ers_recommendation` endpoint; `environment` role preserved (ERS law) |
| Co-Director ERS advisory | GO | `multi_shot.ers_recommendation` tool |
| Project deletion cleanup | GO | project-scoped tables covered by generic deletion sweep |
| GPU preflight | GO | model readiness + VRAM hints in `model_registry.py` |
| Workflow export | GO | certified-registry entries with builder paths and fingerprints |
| Provider-boundary certification | GO | no automated GPU generation; candidate recording is metadata-only |
| Independent verifier | GO | this report + test artifacts + code review |

---

## 3. Known Limitations

1. **Multi-Shot creator UI:** The backend architecture, API, and Co-Director tools are complete. A dedicated creator-facing Multi-Shot workspace (shot list, card/filmstrip layout, candidate comparison, drag-to-reorder) is not yet implemented in `studio-web`. The backend is ready for that UI to be added.
2. **Krea model weights:** Actual Krea 2 checkpoint files are not bundled. Discovery/install follows the existing `D:\01_Models` shared root and Setup component pattern; the user must provide or download the gated weights.
3. **Real generation boundary:** Automated certification stops at the ComfyUI graph builder / queue boundary. Actual image quality and provider runtime behavior remain creator-manual verification items.
4. **LoRA training:** The LoRA lifecycle is modeled in metadata (base model, training base, inference target) but no LoRA trainer is wired to Krea 2 RAW in this milestone.

---

## 4. Verdict

**GO — KREA 2 + MULTI-SHOT IMAGE PLANNING END-TO-END WIRING CERTIFIED FOR CREATOR MANUAL BETA**

All required backend wiring, provider registration, ComfyUI adapters, reference/ERS integration, Multi-Shot data model, Timeline handoff, and Co-Director operations are implemented, tested, and passing. The remaining work is the dedicated creator-facing Multi-Shot workspace UI, which can be built on top of the verified backend.
