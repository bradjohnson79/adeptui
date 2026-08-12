# Krea 2 Complete Image Pipeline + Multi-Shot Integration — Codebase Audit

**Milestone:** Krea 2 Complete Image Pipeline + Multi-Shot Integration
**Audit type:** READ-ONLY (no source/test/config files modified)
**Auditor:** k2-audit agent
**Date:** 2026-08-08
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`

---

## Executive Summary

Adept UI already has a **complete, opinionated image-generation architecture** that Krea 2 can and must plug into; nothing about Krea 2 justifies a parallel subsystem. The spine is:

1. **Provider/family registration** is config-driven (`config/image-runtime/provider-registry.json`) with a *model family* concept (`qwen2512`, `zimage`, `flux`, …) — Krea 2 is a **new model family under the existing `comfyui` local provider**, not a new provider.
2. **Workflows are certified contracts**: `config/image-workflows/certified-registry.json` + `CanonicalImageWorkflowContract` + graph/builder fingerprinting already give Krea 2 the exact "certified-registry/topology-fingerprint" pattern used for video (`config/video-workflows/certified-registry.json`). An image equivalent **exists and is authoritative**.
3. **Execution is a single funnel**: `image_product.compile → service.generate_images → Job(imagegen) → QueueWorker._imagegen → build_leaf_graph (sole builder import site) → prepare_executable_graph (fingerprint enforcement) → ComfyUI → Output Gate → Asset + provenance`. Krea 2 generation must flow through this funnel.
4. **Image Planning foundation exists** (`app/image_pipeline/`) with plan → candidate group → select/approve contracts, Co-Director tools, HTTP API, JSON store, and a Law 28-style Playwright cert. **Multi-Shot does not exist anywhere** (zero matches for `multiShot`/`multi_shot`) — it is greenfield and should extend `image_pipeline` rather than fork it.
5. **Model install/discovery** is component-based (Setup catalog + diagnostics verifiers + model discovery family scan + capability registry). Krea 2 needs one new catalog component, one new verifier, one new discovery family, and settings keys — all following the `zimage_models` precedent exactly.

**Biggest gaps found:**
- **Project deletion cascade is DB-only.** `app/project_cleanup.py:131-149` deletes rows; nothing deletes `data/projects/{id}/assets/`, `data/image_pipeline/{id}/`, `data/image_product/{id}/`, or take-registry files. Multi-Shot would inherit (and worsen) this orphan family.
- **No imagegen execution-boundary stub** exists (the timeline has `ADEPT_TIMELINE_CERT_STUB`; imagegen does not). Image cert today relies on "honest draft" candidate behavior. Krea certification should add a mirror-image stub at the ComfyUI queue boundary rather than build new infrastructure.
- **Krea 2's signature sampler control (timestep-shift `mu`) is not representable** in the current builder dispatch signature (`build_leaf_graph` has steps/cfg but no `mu`/shift). The contract/dispatch layer needs a small, contract-governed extension.
- **GPU evidence for image jobs is thin**: there is no per-image-job device/VRAM provenance capture (Law 26 checklist items) — only ComfyUI reachability + component verification + job-history model/checkpoint strings.

**Krea 2 plan claims vs. official sources:** architecture (Qwen Image VAE + Qwen3-VL text encoder, 12B DiT), Turbo settings (8 steps, CFG 0.0, mu 1.15), RAW settings (52 steps, CFG 3.5), LoRA guidance (train on RAW, run on Turbo), and the Krea 2 Community License are all **VERIFIED** against official sources (§14). Exact Comfy-Org FP8 repack filenames are **UNVERIFIED** (not enumerated in official sources; do not invent).

---

## 1. Image Provider Registry

**Authoritative registry file:** `config/image-runtime/provider-registry.json`
- Providers array with `{providerId, displayName, kind, runtime, supportedModelFamilies, operations, credentialEnvKeys?}`.
- The local ComfyUI provider is a single entry (`provider-registry.json:6-13`): `"providerId": "comfyui"`, `"kind": "local"`, `"runtime": "comfy"`, `"supportedModelFamilies": ["qwen2512","zimage","flux","qwen","hidream","checkpoint","sdxl"]`, operations `image.generate|edit|reference|upscale` (`:12`).
- Cloud providers: `google_imagen` (`:23-30`), `openai` (`:31-39`), `replicate` (`:41-48`), `ideogram`, `recraft`, `leonardo`, `runware`, `together`, plus the M42 hosted tier `kie`/`wavespeed`/`fal` (`:95-129`) and `black_forest_labs`/`stability` (`:131-147`).

**Loader/prober:** `studio-api/app/image_runtime/provider_registry.py`
- `load_provider_registry` (`:16`), `get_provider` (`:32`), `probe_provider_availability` (`:39`), `provider_inventory` (`:76`).

**Second (hosted) provider tier:** `studio-api/app/hosted_providers/registry.py:35-87` — `HostedProviderDefinition` for `kie`/`wavespeed`/`fal` with `integration_status`, `supported_modalities`, `certified_models`. Krea is open-weight local, so it does **not** belong here.

**UI-facing model registry (Production Dock catalog):** `studio-api/app/production_control/model_registry.py`
- Static `_CATALOG` (`:55`) of `ModelDescriptor`s via `_desc` (`:24-52`): `{id, modality, label, locality, providerId, capabilityLabel, lifecycle, supports, doesNotSupport, estimatedVramGb, gpuCompatible, executable}`.
- Image local entries: `qwen-image-2512-local` (`:195-207`, Certified), `flux-local` (`:208-220`), `zimage-local` (`:222-233`, Testing), then many `Requires Setup` rows (`flux-schnell-local` :234-246 through `hunyuan-image-local` :390-402). Hosted image rows: `:403-524`.

**Dock-model → image family map:** `studio-api/app/production_control/runtime_map.py:18-24` (`IMAGE_FAMILY_BY_MODEL`), `image_family_for_dock_model` (`:64-67`), and `apply_image_dock_preference` (`:118-130`) which injects the dock-selected family into requests that don't explicitly override it.

**Image Studio unified provider layer (what the creator sees):** `studio-api/app/image_studio/providers.py`
- `_FAMILY_FALLBACK` (`:11-21`), per-model `_HINTS` with `nativeResolutions`/`upscaleSupported`/`licenseNote`/`costHint` (`:23-78`), readiness mapping `_map_local_readiness` (`:93-105`: lifecycle `not_installed`/`missing` → `"not_installed"`; Certified+executable → `"ready"`), `list_image_providers` (`:183-262`), `providers_for_mode` (`:265-316`, modes `best_match|choose_model|all_models` with cost preflight), `family_catalog` (`:319-344`, hard-coded family labels at `:323-331`).

**Capability registry bindings:** `studio-api/app/capabilities/registry.py`
- `models.image.ready` (`:644-652`, bound to component `zimage_models`), `workflows.image.ready` (`:623-632`), and the M2.9 image capability family `image.generate` … `image.publish_reference` (`:1009-1119`).

**Where Krea entries go (extension points):**
1. `provider-registry.json:11` — add `"krea2"` to the `comfyui` provider's `supportedModelFamilies` (Krea 2 Turbo/RAW are two checkpoints of **one family**; see §14 LoRA guidance).
2. `model_registry.py` `_CATALOG` — add `krea2-turbo-local` (and optionally `krea2-raw-local`, non-executable-by-default for creators) `modality="image"` descriptors.
3. `runtime_map.py:18-24` — map `krea2-turbo-local → "krea2"`.
4. `image_studio/providers.py` — add `_HINTS["krea2-turbo-local"]` (nativeResolutions 1K/2K, licenseNote naming the Krea 2 Community License), `_FAMILY_FALLBACK`, and `family_catalog` labels/families (`:323-331`).
5. `capabilities/registry.py` — new capability entries bound to a new `krea2_models` component (e.g. `models.image.krea2.ready`) instead of overloading `models.image.ready`.

---

## 2. Model Discovery / Install

**Authoritative model root.** There is no single `ADEPT_MODEL_ROOT`; there are two coordinated roots:
- **Model Storage (Source Manager):** `studio-api/app/model_storage/store.py:17` — `DEFAULT_PREFERRED_ROOT = r"D:\01_Models"`; categories `("default","llm","ollama","image","video","audio","voice","3d","temp_cache")` (`:19-29`); defaults derive from `settings.minimax_h3_model_root` (`:37`, set at `app/config.py:71` to `D:\01_Models`); `set_root`/`registeredFolders` API (`:106-121`). **This is the authoritative shared root the milestone brief references** (`D:/01_Models`, krea2 subtree).
- **ComfyUI shared models dir:** `app/config.py:17-19` — `comfy_models_dir = C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models` (env-overridable via `STUDIO_COMFY_MODELS_DIR`; settings use `env_prefix="STUDIO_"`, `config.py:6`). `setup/paths.py:18-48` `default_models_root()` prefers the Comfy shared folder, then `data/models`.

**ComfyUI extra_model_paths.yaml:** only referenced by ad-hoc launch scripts (`.adept-tmp/launch-comfy.bat:3`, `.adept-tmp/launch-comfy.ps1:19`) passing `--extra-model-paths-config ...\shared_model_paths.yaml`. **No app code manages `extra_model_paths.yaml`** (zero matches in `*.py`). ComfyUI resolves models from its shared models dir; Adept verifies on disk via Setup verifiers. Krea 2 weights under `D:\01_Models` therefore require either (a) the existing shared-paths YAML to include that root (operator-level, as today), or (b) a new managed YAML writer — the former is the established pattern.

**Discovery:** `studio-api/app/image_runtime/model_discovery.py`
- `_models_roots` (`:13-55`): `ADEPT_MODELS_ROOT`/`COMFY_MODELS_PATH` env, repo `models/`, `ComfyUI/models`, `C:/D:/E:/ComfyUI/models`, and `settings.comfy_models_dir`.
- `_detect_family` (`:57-67`): substring filename pattern matching across roots.
- `discover_modern_image_models` (`:70`): families `zimage` (`:95`, patterns `("z_image","z-image","zimage")` at `:74`), `flux` (`:102`), `qwen` (`:109`), `imagen` (`:117`, credential-based).
- **Krea extension:** add a `krea2` family with tight patterns (e.g. `("krea-2","krea_2","krea2")`) — see Risks on false positives.

**Install/verify components:** `studio-api/app/setup/catalog.py`
- `zimage_models` (`:77-83`, verifier `zimage_files`, installer `path_link`, category "Still Image Models"), `qwen_image_2512_models` (`:84-90`), plus many experimental `linked_files` entries; gated-reference precedent `ltx23_ic_lora_ingredients` (`:306-312`).
- Verifiers live in `setup/diagnostics.py`: `verify_component` (`:121`), `zimage_files` (`:266-280`: reads `settings.zimage_unet/zimage_clip/zimage_vae` at `config.py:38-41`, searches `diffusion_models|text_encoders|vae|clip|clip_vision` subdirs), `qwen_image_2512_files` (`:282-306`).
- Suggested paths: `setup/paths.py:76-107` (`ensure_suggested_path`); `is_adept_managed_path` (`:143-156`).
- **Krea extension:** new component `krea2_models` ("Krea 2 Turbo (+RAW) Models", verifier e.g. `krea2_files`, installer `path_link`, category "Still Image Models") + new settings keys (precedent `config.py:38-53`) for the Turbo/RAW checkpoints, Qwen3-VL text encoder, and Qwen Image VAE. Because the HF repos are **gated** (`gated: auto`, §14), automated download should NOT be assumed; `path_link` + documented manual placement (the IC-LoRA gated precedent, `references/ic_lora_status.py:68-80`) is the honest pattern.

**Missing-model status → UI:**
- `app/comfy_health.py`: `MODEL_COMPONENT_IDS` (`:33-38`) → `model_component_states` (`:73-106`) → `missingModelComponentIds` + reason codes `MODEL_MISSING`/`DEPENDENCY_*` (`:28-30`, `:109-184`). Add `krea2_models` here.
- `image_runtime/readiness.py:19` `generate_readiness_report()`; `image_runtime/registry_sync.py:15` `sync_registry_status_from_discovery` — promotes Draft/Deferred/Blocked from discovery, **never invents or demotes Certified** (`:23`).
- UI readiness literal: `image_studio/contracts.py:34-42` (`ProviderReadiness` incl. `"not_installed"`), mapped at `image_studio/providers.py:93-105`, rendered by `studio-web/src/components/image-studio/ImageProviderBrowser.tsx`.

---

## 3. ComfyUI Image Workflows

**An image certified-registry equivalent exists and is authoritative** (mirroring `config/video-workflows/certified-registry.json`, 53 KB, keys like `ltx.simple_i2v`, `director.timeline_render`):
- **File:** `config/image-workflows/certified-registry.json` — entries (workflowKey → builderPath):
  - `zimage.txt2img` (`:28-39` → `app.workflows.image_tools:build_zimage_txt2img_workflow`), `zimage.ref_edit` (`:121-132`), `zimage.inpaint` (`:220-231`), `zimage.outpaint` (`:322-333`)
  - `flux.txt2img` (`:421-432`), `flux.img2img`/`reference`/`edit` (`:502`,`:580`,`:656`)
  - `qwen2512.txt2img` (`:732-743` → `app.workflows.qwen_image_2512:build_qwen_2512_txt2img_workflow`), `qwen2512.character_concept` (`:825-836`), `qwen2512.character_profile` (`:918-929`)
  - `qwen.*` (`:1011-1178`), `imagen.*` (`:1242-1393`, builderPath `null` — cloud), `checkpoint.*` (`:1450-1540`), `image.upscale` (`:1604-1615`).
- **Loader:** `image_runtime/certified_registry.py` — status enum `{"Draft","Built","SmokeTested","Certified","Deferred","Blocked","Retired"}` (`:15`), `ImageWorkflow` dataclass (`:33`), `load_registry` (`:142`), `get_workflow` (`:166`), `production_ready_keys` (`:177-178`), `assert_executable` raises when not Certified (`:188-197`).
- **Contract:** `image_runtime/contract.py` — `CanonicalImageWorkflowContract` (`:12`) and `resolve_image_workflow` (`:197`) — the dynamic, capability-checked workflow resolver.
- **Fingerprints (topology immutability):** `image_runtime/fingerprints.py` — `graph_hash` (`:72`), `inventory_hash` (`:76`), `builder_source_hash` (`:90`; hashes the builder's source file), `assert_no_graph_drift` (`:123`).
- **Builder dispatch — SOLE import site:** `image_runtime/workflow_execute.py`, module docstring (`:1-5`): *"Sole production builder import site for image workflows… QueueWorker and product surfaces must call build_leaf_graph — never import builders directly. Allowed builder imports: this module, cert scripts, tests."* `build_leaf_graph` (`:16-39`) dispatches by `contract.workflow_key` (e.g. `zimage.txt2img` at `:48-63`); `prepare_executable_graph` (`:303`) validates fingerprints with `enforce_certified_fingerprint` when the workflow is Certified.
- Builders live in `app/workflows/` (`image_tools.py`, `image_edit_tools.py`, `qwen_image_2512.py`) and legacy `app/imagegen_workflows.py`.

**Krea extension points:**
1. New builders, e.g. `app/workflows/krea2_image.py:build_krea2_turbo_txt2img_workflow` (+ RAW variant, + LoRA variant), using ComfyUI-native Krea2 nodes (UNETLoader + CLIPLoader type `krea2` + Qwen Image VAE; §14).
2. New dispatch branches in `build_leaf_graph` keyed `krea2.turbo_txt2img` / `krea2.raw_txt2img`. **Note:** the current signature (`workflow_execute.py:16-39`) has `steps/cfg/denoise` but **no `mu`/timestep-shift parameter** — Krea 2 Turbo *requires* constant `mu=1.15`; RAW uses resolution-derived shift. This must be added as a contract-governed runtime requirement, not a hardcode.
3. New entries in `config/image-workflows/certified-registry.json` starting at `"status": "Draft"` with `fingerprints` generated via `fingerprints.py` and `requiredModels` referencing the new settings keys.
4. Node requirements recorded per entry (`requiredNodes`) — validated against live ComfyUI `/object_info` (`capability_probe.py:17-37`).

---

## 4. Request → Queue → Asset Path

**Compile:** `image_product/compile.py:90` `compile_image_request(project_id, body)` — preset → prompt intel → family recommendation → `ImageIntent` + pinned contract snapshot (`imageRuntime`).

**Enqueue:** `image_product/service.py:16` `generate_images`
- Batch ≤ 8 (`:35`); per-item `Job` rows (`:78-89`) with `kind="imagegen"` or `"imagegen_edit"` (`:78`), `params_json` carrying `imageIntent`, pinned `imageRuntime`, `allow_draft_cert_harness` (`:66`), references (`refs`, `:72`), spatial bundle fields (`:68-71`).
- Scheduling via `codirector.executive.imagegen_adapter.schedule_job_queue_enqueue` (`:92-95`).
- History entry per job: `append_history` (`:99-113`).
- HTTP: `image_product/api.py:79-94` (`/image-product/generate`, `/projects/{id}/generate`), `/compile` (`:71`).

**Execute:** `queue_worker.py:2610` `QueueWorker._imagegen` — *"Execute-only image path: ImageIntent → pinned contract → workflow_execute → Output Gate"* (`:2611`)
- Retry without silent regeneration: `output_valid_but_unregistered` path (`:2625-2634`).
- Model selection: `_zimage_stack_ready` (`:2149`, via `verify_component("zimage_models")`), `_resolve_ready_still_model` (`:2184-2211`, preferred zimage → alternates flux/hidream/sd35/custom from `config.py:55-58`), special-case `use_zimage` (`:2673-2694`) — **Krea must generalize this (currently zimage-only)** with its own default steps/cfg/mu and no silent family swap (see Risks).
- Pinned contract revalidation — refuses silent version upgrades (`:2696-2734`, esp. `:2704-2708`).
- Graph build + fingerprint enforcement (`:2806-2832`), ComfyUI submit (`:2847` `comfy.queue_prompt`), job `history_json` with workflowKey/Version/certificationRecordId/referenceHash (`:2859-2881`).
- Output staging to `data/projects/{id}/assets/.pending/` (`:2891-2894`), then Output Gate `validate_image_output` (`image_runtime/output_gate.py:75`; edit variant `:256`) — existence/size/decodability/dimensions/checksum/previews.
- **Asset registration + provenance:** `_imagegen_commit_asset` (`:2986`) — copies into `data/projects/{id}/assets/` (`:3010-3014`), builds `ImageProvenance` (`:3026-3038`: workflow, workflowVersion, runtime, provider, references, prompt, seed, parentImages, validation, intentId, settings incl. checkpoint+checksum), creates `Asset` row with `prompt_meta_json` (`:3053-3065`), and asset-graph `add_version`/`add_edge("derived_from"|"reference_of")` (`:3067-3080`).

Everything Krea 2 generates will inherit this path unchanged — including retry, gate, provenance, and asset graph — provided it enters via `image_product`.

---

## 5. Image Planning UI (studio-web)

**Primary surface:** `studio-web/src/components/image-studio/CinematicImageStudio.tsx` (M4.8, 1108 lines), mounted in `ProjectEditor.tsx:35` (import) and `:770`. Modes `generate|edit` (`CinematicImageStudio.tsx:29`); provider state and fetch via `api.imageStudio.providersForMode` (`:214-220`); provider descriptors contract `studio-web/src/contracts/cinematicImageStudio.ts`.
**Planning sub-panel:** `studio-web/src/components/image-studio/ProductionPipelinePanel.tsx` — quality profile select, prepare-plan, candidates, approve (`:65-101`); cert test hooks `image-pipeline-panel`, `image-pipeline-prepare`, `image-pipeline-generate-candidates` (used by the E2E cert, §13).
**Client contracts:** `studio-web/src/contracts/imagePipeline.ts` — `ProductionImageRequest` (`:8-24`), `CreativeDirectionPacket` (`:26-43`), `ImagePipelineModelRoute` (`:65-79`), `ImageGenerationPlan` (`:105-124`), `ImagePipelineCandidate` (`:136-150`), `ImagePipelineCandidateGroup` (`:152-162`).
**API wiring:** `studio-web/src/api.ts:3932-3945` (imageStudio provider endpoints); pipeline endpoints under `/api/image-pipeline/*`.
**Generator/model selector:** `ImageProviderBrowser.tsx` + `providers_for_mode` backend (`image_studio/providers.py:265-316`) with Best Match / Choose Model / All Models modes (`image_studio/contracts.py:9`).

**Where Multi-Shot lives (creator-first rule):** add a third `StudioMode` (`"shots"`) or a collapsible "Multi-Shot" section inside `CinematicImageStudio`, reusing `ProductionPipelinePanel` patterns — scene picker already exists (`sceneId` state, `CinematicImageStudio.tsx:191`, scenes `:208-212`). Do **not** add a new top-level workspace; keep one primary action per view.

---

## 6. References / Moodboards

- **Role vocabulary:** `director_references/roles.py` — `ReferenceRole` literals (`character_identity`, `costume`, `environment`, `style`, `lighting`, …) with vision-validator mapping.
- **Reference sets (timeline-grade):** `director_references/models.py` — `ReferenceBinding` / `ReferenceSetVersion` / `ReferenceSet`.
- **Image-runtime reference assets:** `image_runtime/reference_assets.py` — `ReferenceAsset` model + canonical `REFERENCE_TYPES`; surfaced at `image_runtime/api.py:82` (`/reference-types`).
- **Pipeline bridge:** `image_pipeline/references.py` builds `ImageReferenceAssignment` (contract at `image_pipeline/contracts.py:138`); `image_product/references.py` normalizes UI refs into stored `ReferenceAsset`s (`data/image_product/{project}/`, store at `image_product/store.py:10-23`); HTTP at `image_product/api.py:186-241` incl. `/references/bridge` (character_identity/library asset → ReferenceAsset).
- **Continuity sessions (moodboard-adjacent):** `image_studio/api.py:84-141` (CRUD + approve-image) and `/cinematic/compile-preview` (`:143-200`) which merges continuity extras and spatial reference bundles into `creativeContext`/`referenceAssetIds` before image_product compile — **this is how references currently reach generation requests**.
- **Production Bible / visual canon:** character canon packs `config/character-canon/*.json` loaded by `character_identity/canon.py:13-24` (Korri v1), visual canon promotion `character_identity/api.py:707` (`promote_visual_canonical`), plus Co-Director bible handlers (`codirector/tools/handlers/bible_domain.py`).
- **IC-LoRA reference conditioning:** `references/models.py:42-46` (`INGREDIENTS_*` constants), path probing `references/ic_lora_status.py:26-65`.

Multi-Shot reference semantics should reuse `ImageReferenceAssignment` + `REFERENCE_ROLES` verbatim; per-shot overrides belong in the Multi-Shot shot contract, not a new reference system.

---

## 7. LoRA Infrastructure

**Current state — exactly one first-class LoRA exists:**
- LTX 2.3 Ingredients IC-LoRA: constants `references/models.py:42-46`; `ReferenceModelDefinition` dataclass (`:49-64`) with `base_models`, `workflows`, `license_name` fields — **the metadata shape to copy for Krea LoRA lineage**; status probing `references/ic_lora_status.py` (incl. HF gated-access probe `:68-80`); Setup catalog entry `setup/catalog.py:306-312`.
- Capability probing: `image_runtime/capability_probe.py:33` (`has_lora` via `LoraLoader`/`LoraLoaderModelOnly` nodes), `supportsICLoRA` (`:48`).
- Workflow capability flags: `certified-registry.json` entries carry `capabilities` (e.g. `supportsLoRA`) — the natural place for Krea entries to declare LoRA support.

**No general LoRA registry, training contracts, or LoRA store exists.** Krea LoRA lineage (`baseModel=krea2-raw`, `inferenceTarget=krea2-turbo`) should attach as:
1. `requiredModels`/capabilities metadata on the Krea workflow registry entries (LoRA files under the shared model root `loras/` category);
2. `ReferenceModelDefinition`-style records (new `references/` definition set or a small `loras` registry) carrying `base_models=("krea2-raw",)`, `workflows=("krea2.turbo_txt2img",)`;
3. ComfyUI graph wiring via `LoraLoader` — ComfyUI natively remaps diffusers-format Krea 2 LoRA keys (§14, ComfyUI PR #14589).

---

## 8. Generation History / Retake / Approval

- **Per-generation history:** `image_product/history.py:15` `append_history` (newest-first, capped 500 entries `:22`; prompt history cap 100), `list_history` (`:33`); HTTP `image_product/api.py:244-255`.
- **Non-destructive edit version graph:** `image_product/versions.py` — states `Draft|PendingReview|Approved|Rejected|ProductionMaster|Archived` (`:14-21`), `create_version` (`:36`), `set_state` (`:98`), `mark_master` (`:129`, *"without erasing prior masters"*); HTTP `image_product/api.py:396-454`.
- **Plan-level candidates:** `image_pipeline/contracts.py:261-302` (`ImageCandidateEvaluation`, `ImageCandidate` with `parentCandidateId`, `ImageCandidateGroup` with `selectedCandidateId`/`recommendedCandidateId`); lifecycle in `image_pipeline/candidates.py` + `orchestrator.py:142-191`.
- **Timeline retakes:** `timeline_retakes/` — `router.py:41-92` (`baseline`, `alternate`, set-active per shot; store `timeline_retakes/store.py`).
- **W46 batch approval:** `director_timeline_w46/router.py:218` (`complete`), `:241` (`approve`), `:342` (`retake`); contracts `BatchBlock.candidateVersions` + `ApprovedClip` (`director_timeline_w46/contracts.py`).
- **Failure isolation:** job-level retry without regeneration (`queue_worker.py:2625-2634`), blocked-plan draft isolation (`orchestrator.py:150-158`), per-candidate honest failure explanation (`:188-191`).

Multi-Shot should reuse all of the above: per-shot candidate groups are `ImageCandidateGroup`s keyed by shot; retake = new candidate group with `parentCandidateId` lineage; approval = existing plan approval + W46 `approve`.

---

## 9. Timeline Handoff Contracts (W46)

**Authoritative contracts:** `studio-api/app/director_timeline_w46/contracts.py`
- `TimelineVisualAnchor` (`:84-90`): `{id, kind="image", assetId, label, atTime, strength}` — **the canonical "attach an image" record**.
- `TimelinePromptSegment` (`:93-105`): `{start, length, text, role, strength, negativePrompt, anchorIds, versionId}` — the canonical prompt record.
- `ExecutionSnapshot` (`:107-127`): **immutable** record per generation — `batchBlockId`, `compiledPrompts`, `references`, `selectedGenerator`, `settings` (free-form dict), `providerId`, `sourceAnchors`, `promptIntelligence`.
- `GenerationJobRef` (`:130-143`): `executionSnapshotId`, `queueJobId`, `providerJobId`, `generatorId`, status/progress.
- `CandidateVersion` (`:145`), `BatchClip` (`assetId`, `role` e.g. image `"start"/"middle"/"end"/"guide"`), `ApprovedClip` (`assetId`, `executionSnapshotId`, `candidateId`).

**Endpoints:** `director_timeline_w46/router.py`
- Master GET/PUT (`:34-48`); batches: add `:74`, duplicate `:87`, delete `:95`, **add clip `:132`**, patch `:147`; generation: scene `:176`, batch `:187`, workflow-export `:192`; complete `:218`, approve `:241`, retake `:342`; preflight `:281`; snapshot get `:291`; cert stub endpoints `:381-430`.
- Generators list: `router.py:24-26` → `service.generators()`; adapter registry `generation/registry.py:29-54` (video-only adapters today: MiniMax H3 T2V/I2V, LTX, Seedance, Kling + env-gated stub). `resolve_id` **forbids silent substitution** (`:56-63`).
- Request building: `generation/request_builder.py` maps `BatchBlock`+`ExecutionSnapshot` → `TimelineGenerationRequest` (`generation/contracts.py`: `startImageAssetId`, `endImageAssetId`, `referenceAssetIds`).

**Lineage field mapping for Multi-Shot:** available today — `batchBlockId`, `executionSnapshotId`, `candidateId`, `assetId` (≈ `approvedAssetId`), `queueJobId`. **Not present:** `multiShotPlanId`, `multiShotId`, `imageGenerationId`. The contract-safe carrier is `ExecutionSnapshot.settings` (dict, `:119`) plus the clip's `assetId`; formal fields would be a contract change requiring primary approval (Build Law #16). Image assets enter the timeline as **clips/anchors** (POST clips, `:132`), not through the video generator registry — do not register Krea as a W46 `VideoGeneratorAdapter`.

---

## 10. Co-Director Image Tools

**Registered tool definitions:** `studio-api/app/codirector/tools/definitions.py`
- Image-pipeline reads: `image_pipeline.analyze_request` (`:2729`), `.get_readiness` (`:2743`), `.get_job` (`:2751`), `.preview_posecraft` (`:2763`).
- Image-pipeline mutations: `prepare_plan` (`:5513-5545`), `prepare_creative_direction` (`:5546`), `select_profile` (`:5559`), `assign_reference` (`:5576-5595`, capability `"references"`), `load_spatial_map` (`:5596`), `prepare_posecraft` (`:5608`), `generate_candidates` (`:5622-5633`, capability `"comfyui"`), `evaluate_candidates` (`:5634`), `recommend_candidate` (`:5647`), `select_candidate` (`:5659`), `prepare_repair` (`:5672`), `apply_repair` (`:5686`), `master` (`:5701-5716`, capability `"comfyui"`), `approve` (`:5717`), `cancel` (`:5730`).
- **Definition shape:** `ToolDefinition(tool_id, kind="read"|"mutating", title, description, capability, pinned_resources, parameters=[ToolParameter(...)])` — e.g. `pinned_resources=("project","plan")`, `capability="project"|"references"|"comfyui"`.
- Handlers: `codirector/tools/handlers/image_pipeline_tools.py`; capability labels `capabilities/registry.py:1009-1119` (approval-gated: `image.approve` `:1100-1108` with `requires_approval=True`).

**Capability-scoped exposure layer:** `codirector/tools/exposure.py`
- `_BASELINE_READ_TOOL_IDS` (`:130`), domain derivation `_domains_from_intent` (`:182`) and `_domains_from_surface` (`:222`), main filter at `:264+` — tools are filtered by workspace surface, capability readiness, and intent; domains derive from the `tool_id` prefix.

**Extension pattern for new (Multi-Shot/Krea) tools:**
1. Add `ToolDefinition`s with correct `kind`, `capability`, `pinned_resources`, bounded `ToolParameter`s (definitions.py pattern above).
2. Register handlers in `codirector/tools/handlers/` (image_pipeline_tools.py precedent).
3. If a new domain prefix is introduced (e.g. `multishot.*`), extend `exposure.py` domain maps (`:182`, `:222`) and add capability registry entries; mutating generation tools should use capability `"comfyui"` (or a new readiness-gated capability) so exposure tracks actual model readiness.
4. Approval-gating for anything that spends money or mutates creator work (precedent `image.approve`).

---

## 11. Project Deletion Cascade

**Authoritative cascade:** `app/project_cleanup.py`
- `_INDIRECT_PROJECT_DELETES` (`:9-124`) covers relational children (assets' `asset_versions`/`asset_edges` `:91-99`, codirector proposals/approvals/receipts `:100-107`, timeline reference sets `:35-46`, character tables `:63-82`, voice `:83-90`, etc.).
- `delete_project_residue` (`:131-149`): indirect deletes + generic sweep of **any table** with a `project_id`/`projectId` column (`:141-149`).
- Called from `routers/api.py:869-877` (`DELETE /api/projects/{project_id}`).

**GAP — filesystem artifacts are never deleted.** The cascade is DB-only. Verified by search: no `rmtree`/`unlink` anywhere near project deletion (all `shutil.rmtree` hits are installer/runtime maintenance). Orphaned on delete today:
- `data/projects/{id}/assets/**` (images incl. `.pending/`, `queue_worker.py:2891`,`:3010`)
- `data/image_pipeline/{id}/plans|candidate_groups/**` (`image_pipeline/store.py:12-37`)
- `data/image_product/{id}/**` (history, versions, presets, references, masks — `image_product/store.py:10-23`)
- `timeline_retakes` take store (`timeline_retakes/store.py`), continuity sessions, character/voice sandboxes, etc.

**Multi-Shot implication:** Multi-Shot plans/shots are new project-scoped artifacts. If they reuse the `image_pipeline` store they inherit the same orphan family. A filesystem cascade hook (project asset/JSON dirs) is a prerequisite fix — it benefits the whole image family, and the autonomous cert suites already delete projects via API (e.g. `tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts:62-85`) leaving residue today.

---

## 12. GPU Preflight

- **Law 26 preflight implementation:** `docker_runtime/gpu_preflight.py:22-106` `check_gpu(runtime_id)` — host visibility, in-container `nvidia-smi`, **torch framework proof** (`:73-88`), records `gpuReady`, demotes readiness to `requires_repair` on failure (`:103-104`). Hooked from `docker_runtime/service.py:20`, `docker_runtime/queue_hooks.py:33`, `docker_runtime/api.py:94`, `production_control/resolve.py:91`.
- **ComfyUI device evidence:** `comfy_health.py:45-60` (`_devices` from `/system_stats`: name, vramTotalMb, vramFreeMb) + node catalogue probe (`:187-197`).
- **VRAM tiering:** `vram_profiles.py` — `VramProfile` (`:10-31`) with `PROFILES` for 8/16/24/32 GB (`:33`) incl. `recommended_engine`.
- **Image-path reality:** local imagegen hooks GPU readiness *indirectly* — component verification (`_zimage_stack_ready`, `queue_worker.py:2149-2156`) + ComfyUI reachability; per-job provenance records model/checkpoint (`queue_worker.py:2859-2881`) but **not** device/VRAM/utilization. For a 12B-param model (§14), Krea integration should add: pre-queue VRAM check against the 24 GB-class profile, and post-job device/VRAM evidence written into `ImageProvenance.settings` (extension point `queue_worker.py:3037`). No silent CPU fallback exists in the Comfy path (Comfy itself owns device placement) — keep it that way and surface readiness honestly instead.

---

## 13. Cert / Provider-Boundary Interception

**Timeline (the pattern to mirror):**
- `director_timeline_w46/generation/adapters/stub_cert.py` — adapter enabled **only** when `ADEPT_TIMELINE_CERT_STUB=1` (registry wiring `generation/registry.py:48-54`, *"CERT_STUB_ENV_GATED… Invisible in production"*), records requests to a JSONL sink, programmatic job-state control.
- Cert endpoints: `router.py:381-430` (`/cert/stub-jobs/{id}/state` GET/POST, `/cert/requests`, `/cert/reset`, `/cert/seed-failed-job`).

**Image (today):**
- **No equivalent imagegen execution-boundary stub exists.** Instead, certification avoids GPU cost via:
  - **Honest-draft candidate behavior:** `image_pipeline/orchestrator.py:150-158` (blocked plan → draft slots), `:155-158` (no DB → draft), `:188-191` (enqueue failure → draft with explanation). The Law 28-style autonomous cert asserts plan/candidate/select/repair/master flows **without** requiring real assets (`tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts:158-201`, `:219-267`), plus project-isolation and tool-registration proofs (`:269-303`).
  - **Draft-cert harness flag:** `allow_draft_cert_harness` threaded from `service.py:66` → `queue_worker.py:2697` (`allow_draft`), permitting non-Certified workflows under cert only.
  - **Unit-level contract tests without GPU:** `studio-api/tests/test_m42_w2_image_runtime.py:73-81` (legacy normalization), plus registry/fingerprint tests in the same module.

**Krea cert should reuse:** Draft-status registry entries + `allow_draft_cert_harness` + honest-draft candidates + the Playwright autonomous-cert harness (disposable project, artifact capture, cleanup assertions). **Recommended addition (small, mirroring stub_cert):** an env-gated interception at the `comfy.queue_prompt` boundary (`queue_worker.py:2847`) that fabricates a deterministic valid image through the real Output Gate — this exercises gate/provenance/asset code without GPU, exactly as the timeline stub does at the provider boundary. Do not build a Krea-specific mock subsystem.

---

## 14. Verified Krea 2 Facts (official sources, accessed 2026-08-08)

### Release & checkpoints — VERIFIED
- Krea 2 is an open-weights text-to-image diffusion model from Krea.ai: **12B-parameter single-stream MMDiT (DiT), flow-matching**, Model card "Version v1.0, Release Date June 22, 2026", license field `krea-2-community-license`, HF repos **gated (`gated: auto`)** with `LICENSE.pdf` in-repo.
  - Sources: https://huggingface.co/krea/Krea-2-Turbo · https://huggingface.co/krea/Krea-2-Turbo/blob/main/README.md · https://huggingface.co/krea/Krea-2-Raw/blob/main/README.md · https://www.krea.ai/krea-2-open-source · https://www.krea.ai/blog/krea-2-technical-report
- Checkpoint files: `turbo.safetensors` in `krea/Krea-2-Turbo` (README: "Download `turbo.safetensors` in this repo"; env `OSS_TURBO`) and `raw.safetensors` in `krea/Krea-2-Raw` (env `OSS_RAW`). Official codebase: https://github.com/krea-ai/krea-2.
- **Architecture (plan claim VERIFIED):** "Qwen Image VAE, a 12B dense DiT backbone, and a Qwen3-VL text encoder with multi-layer feature aggregation" (https://www.krea.ai/krea-2-open-source). Diffusers docs: VAE = `AutoencoderKLQwenImage` (f8, 16 latent channels); text encoder = Qwen3-VL (e.g. `Qwen/Qwen3-VL-4B-Instruct`) tapping **12 hidden-state layers** into a text-fusion stage; scheduler `FlowMatchEulerDiscreteScheduler` with `use_dynamic_shifting=True`, `base_shift=0.5`, `max_shift=1.15`, `base_image_seq_len=256`, `max_image_seq_len=6400`; `is_distilled=True` ⇒ fixed `mu=1.15`. (https://huggingface.co/docs/diffusers/en/api/pipelines/krea2 · https://huggingface.co/docs/diffusers/api/models/krea2_transformer2d)

### Recommended inference settings — VERIFIED
- **Turbo:** `uv run inference.py "…" --checkpoint oss_turbo --steps 8 --cfg 0.0 --mu 1.15 --width 2048 --height 2048` — 8-step distilled, CFG disabled (0.0), constant timestep-shift mu **1.15**, resolution range **1024–2048**, *"padded up to a multiple of 16 if needed"*. (https://huggingface.co/krea/Krea-2-Turbo/blob/main/README.md · https://github.com/krea-ai/krea-2)
- **RAW:** README example `--checkpoint oss_raw --steps 52 --cfg 3.5 --width 1024 --height 1024` (https://huggingface.co/krea/Krea-2-Raw/blob/main/README.md). Repo CLI defaults: `--steps 28`, `--cfg 4.5`, `--y1 0.5` (mu at min res), `--y2 1.15` (mu at max res), `--mu` pins a constant (recommended 1.15 for `oss_turbo`). **Nuance:** the plan's "steps ~52, CFG ~3.5" is the official RAW *example invocation*, not the CLI default — treat 52/3.5 as recommended RAW quality settings. (https://github.com/krea-ai/krea-2)

### ComfyUI support — VERIFIED
- Native support since **ComfyUI v0.26.0**: PR https://github.com/Comfy-Org/ComfyUI/pull/14589 adds `comfy/ldm/krea2/model.py` (`SingleStreamDiT`), `comfy/text_encoders/krea2.py` (Qwen3-VL-4B, 12 tapped layers), `CLIPType.KREA2`, `"krea2"` in the `CLIPLoader` node type list, and diffusers-LoRA key remapping in `comfy/lora.py`.
- Official workflow JSON: docs.comfy.org tutorial (https://docs.comfy.org/tutorials/image/krea/krea-2) — "Krea-2 Turbo text-to-image workflow" (subgraph + ResolutionSelector 1K–2K + LoRA CustomCombo + SaveImage), also in the ComfyUI Template Library ("Krea-2"); announcement: https://comfyui.org/en/krea-2-open-source-models-are-now. Comfy-ready weight repacks (incl. FP8) are published under `Comfy-Org/Krea-2` (referenced by Comfy docs/community mirrors).
- Local evidence: the installed runtime snapshot reports ComfyUI **0.28.2** (`docs/audit/_gate_api_json/health.json`) ≥ 0.26.0, i.e. native Krea2 nodes should already be present; re-probe `/object_info` at cert time.
- **UNVERIFIED:** exact filenames inside `Comfy-Org/Krea-2` (FP8 variants, text encoder, VAE, LoRA pack). Official sources name only `turbo.safetensors` / `raw.safetensors`. Do not invent repack filenames — enumerate the repo at install time.

### License — VERIFIED
- **Name:** "Krea 2 Community License" (Agreement), https://www.krea.ai/krea-2-licensing; HF `license_name: krea-2-community-license`.
- **Commercial use:** permitted only if total company-wide annual revenue **< $1,000,000 USD** (trailing twelve-month, all sources, incl. affiliates). At/above threshold → separate **Enterprise/Commercial License** (https://www.krea.ai/krea-2-commercial-license; contact opensource@krea.ai; tiers incl. "Maker" at https://www.krea.ai/open-source-pricing).
- **Attribution/distribution:** distributions of the model/derivatives must (a) include "Krea" at the beginning of the model name, (b) include a copy of the Agreement, (c) retain a Notice text file: *"Krea 2 is licensed under the Krea 2 Community License Agreement. For more information, visit https://krea.ai/krea-2-licensing."* Subject to the Acceptable Use Policy (https://krea.ai/krea-2-use-policy); deployers must implement content filtering/review processes.
- **Hosted alternative:** Krea API (`krea-2/medium`, `krea-2/large`) under standard API terms without checkpoint license acceptance (https://www.krea.ai/docs/developers/krea-2/overview) — irrelevant for the local open-weight milestone but useful context.
- **Product obligations for Adept UI:** surface the license in provider hints (`image_studio/providers.py` `_HINTS.licenseNote`), honor HF gating in install flows (manual/gated download like the IC-LoRA precedent), and keep the required Notice text alongside any redistributed weights.

### LoRA guidance — VERIFIED
- "**TRAIN on Raw and RUN on Turbo**" (https://github.com/krea-ai/krea-2). Raw card: "train LoRAs on midtrain and directly use them on Krea 2 Turbo"; Krea publishes an in-house "Krea-2 LoRA Collection" trained on Raw for Turbo (https://huggingface.co/krea/Krea-2-Raw/blob/main/README.md). The plan's lineage (`baseModel=krea2-raw`, `inferenceTarget=krea2-turbo`) matches official guidance exactly.

---

## 15. Gap List (must be built)

**Krea 2 provider-family integration:**
1. `krea2` family in `config/image-runtime/provider-registry.json` (comfyui entry), `model_discovery.py` families, `runtime_map.py`, `image_studio/providers.py` (`_HINTS`/`_FAMILY_FALLBACK`/`family_catalog`), `production_control/model_registry.py` `_CATALOG` rows, `capabilities/registry.py` capability entries.
2. Settings keys for Krea checkpoints/encoder/VAE (`config.py`, precedent `:38-53`) — **filenames sourced from the actual download, not invented** (§14 UNVERIFIED repack names).
3. Setup catalog component `krea2_models` + `krea2_files` verifier (`setup/catalog.py`, `setup/diagnostics.py`) + `comfy_health.py:33-38` MODEL_COMPONENT_IDS + Source Manager root registration under `D:\01_Models\krea2` (`model_storage/store.py` "image" category).
4. Workflow builders (`app/workflows/krea2_image.py`) + `build_leaf_graph` dispatch branches + **`mu`/timestep-shift plumbing** through `CanonicalImageWorkflowContract` runtime requirements and the dispatch signature (`workflow_execute.py:16-39`).
5. Certified-registry entries (start `Draft`), fingerprints via `fingerprints.py`, then certification evidence before `Certified` (`registry_sync.py:23` never auto-promotes).
6. Queue-worker model selection generalization (`queue_worker.py:2666-2694` is zimage-special-cased) + VRAM/device evidence in image provenance (`:3037`).
7. Family-aware recommendation (`image_product/recommend.py` via `recommend_image_family`, called at `image_studio/providers.py:280-288`).
8. Env-gated imagegen execution-boundary stub for cert (mirror of `director_timeline_w46/generation/adapters/stub_cert.py`).
9. LoRA lineage records (baseModel=krea2-raw → inferenceTarget=krea2-turbo) using the `ReferenceModelDefinition` shape (`references/models.py:49-64`) + workflow `supportsLoRA` capability.

**Multi-Shot (greenfield — zero existing matches):**
10. Multi-Shot contracts (plan → ordered shots → per-shot candidate refs) extending `image_pipeline/contracts.py`.
11. Store under `data/image_pipeline/{project}/` (`image_pipeline/store.py` pattern) or a sibling store — **plus the deletion-cascade fix below**.
12. Orchestrator: scene → shots → per-shot `prepare_plan`/`generate_candidates_for_plan` reuse (`orchestrator.py:29`,`:142`).
13. HTTP API (`image_pipeline/api.py` precedent) + `studio-web` contracts (`contracts/imagePipeline.ts` precedent).
14. Multi-Shot UI mode inside `CinematicImageStudio` (progressive disclosure; Creator-First rule).
15. Co-Director tools `multishot.*` (definitions + handlers + exposure domains + capability entries).
16. W46 handoff: approved shot → `POST …/batches/{id}/clips` (`router.py:132`) + `TimelineVisualAnchor`; lineage carried in `ExecutionSnapshot.settings` (`contracts.py:119`) unless primary approves formal fields.
17. Retake integration via `timeline_retakes` baseline/alternate per shot (`timeline_retakes/router.py:51-92`).

**Cross-cutting:**
18. **Filesystem project-deletion cascade** (assets, image_pipeline, image_product, retakes stores) — prerequisite for Multi-Shot (§11).
19. License/Notice handling for redistributed Krea weights + gated-HF install flow disclosure.

---

## 16. Risk List

1. **Parallel-subsystem temptation (HIGH):** provider truth is already split across `provider-registry.json`, `model_registry.py`, `runtime_map.py`, `image_studio/providers.py` (`_FAMILY_FALLBACK`/`_HINTS`), and `capabilities/registry.py`. Adding Krea in only some of them produces contradictory UI/readiness. Mitigation: the five-point registration checklist in §1; consider a follow-up dedup, not a new Krea registry.
2. **Silent family fallback (HIGH, Law 8):** `_resolve_ready_still_model` (`queue_worker.py:2184-2211`) silently swaps to alternates on `"auto"`, and `:2680`/`:2693-2694` rewrite `intent.enginePreference`. Krea must be selected explicitly (or via disclosed Best-Match recommendation), never via silent fallback; any new fallback needs disclosed `reasons` (already threaded into job history `:2874`).
3. **Windows path pitfalls (MEDIUM):** ComfyUI lists subdirectory model names with backslashes on Windows (`config.py:28-29` comment). Krea weights under `D:\01_Models\krea2\...` subfolders will hit this in loader nodes. Also `default_models_root()` (`setup/paths.py:18-48`) prefers the Comfy shared dir, **not** `D:\01_Models` — verifiers must search the shared-model registry roots, and the shared paths YAML must include the krea2 subtree (operator-level today, §2).
4. **Discovery false positives (LOW/MEDIUM):** substring family matching (`model_discovery.py:57-67`) — use tight patterns (`krea-2`, `krea2`) and assert on `sampleFiles` in tests.
5. **Fingerprint churn (MEDIUM):** `builder_source_hash` (`fingerprints.py:90`) ties a Certified entry to the builder source; any builder edit post-cert breaks `assert_no_graph_drift` (`:123`) and `queue_worker.py:2704-2708` refuses silent version changes. Plan a re-cert flow (new `workflowVersion` + new fingerprints + evidence), never edit-in-place.
6. **Deletion-cascade gap (HIGH):** §11 — Multi-Shot without the filesystem cascade fix guarantees growing orphan residue (violates data hygiene and inflates cert residue; cert suites delete projects via API today).
7. **`allow_draft_cert_harness` leakage (MEDIUM, Law 7):** the draft bypass (`service.py:66` → `queue_worker.py:2697`) must stay cert-only; never default-on, never UI-exposed.
8. **Timeline contract violation (HIGH if misrouted):** do **not** register Krea as a W46 video `VideoGeneratorAdapter` (`generation/registry.py:29-54`); image handoff is clip/anchor attachment. Do not mutate `ExecutionSnapshot` (immutable, `contracts.py:107-113`).
9. **License/compliance (MEDIUM):** HF repos are gated; automated download would bypass license acceptance. Revenue-threshold commercial terms + naming/Notice obligations must surface in UI hints and redistribution paths (§14).
10. **GPU readiness honesty (MEDIUM, Law 26):** 12B DiT + 4B text encoder is a 24 GB-class workload. Without a VRAM gate and device evidence in provenance, creators on 8–16 GB tiers will hit opaque ComfyUI OOMs. Add the pre-queue VRAM check and record device/VRAM in `ImageProvenance.settings`.
11. **M29 legacy path (LOW):** flag-gated `image.generate` M2.9 executive path (`capabilities/registry.py:1009-1017`) is a separate enqueue route; Krea work must route through `image_product`/`image_runtime`, not M29 providers.

---

## 17. Recommended Implementation Sequencing (remaining k2 todos)

**Phase A — Registration & discovery (no GPU):**
1. Settings keys + Setup catalog component `krea2_models` + verifier + `comfy_health` MODEL_COMPONENT_IDS.
2. Provider/family registrations (§1 checklist) + model discovery family + registry sync (lands as Draft/Deferred until models verified).
3. Source Manager / Model Storage registration of `D:\01_Models\krea2` under the "image" category; license note + gated-download guidance in UI hints.

**Phase B — Workflow contracts (no GPU):**
4. `krea2.turbo_txt2img` builder + dispatch + contract runtime-requirements extension for `mu` (+ RAW builder second).
5. Draft registry entries + fingerprints; readiness/reporting; unit tests (contract resolution, fingerprint drift, discovery patterns).

**Phase C — Execution & evidence:**
6. Queue-worker model-selection generalization + VRAM pre-queue check + device/VRAM provenance.
7. Env-gated imagegen execution-boundary stub; cert-harness wiring.
8. Single-shot manual validation on the real stack (explicit creator-triggered), then Playwright autonomous cert (disposable project, stubbed boundary) → only then promote registry entries to `Certified` with recorded evidence.

**Phase D — Multi-Shot:**
9. Filesystem deletion-cascade fix (prerequisite).
10. Multi-Shot contracts/store/orchestrator reusing `image_pipeline`; HTTP API; Co-Director tools with capability metadata.
11. UI mode in CinematicImageStudio; W46 handoff (clips/anchors + lineage in `ExecutionSnapshot.settings`); retake integration.
12. Law 28 Playwright cert for the full Multi-Shot flow; unified completion report.

**Phase E — LoRA lineage:**
13. LoRA lineage records + `supportsLoRA` capability on Krea workflow entries + LoraLoader graph variant (Draft → cert).

---

## Appendix — Source Index (repo)

| Area | Primary files |
|---|---|
| Provider registry | `config/image-runtime/provider-registry.json`; `studio-api/app/image_runtime/provider_registry.py`; `studio-api/app/hosted_providers/registry.py`; `studio-api/app/production_control/model_registry.py`; `studio-api/app/production_control/runtime_map.py`; `studio-api/app/image_studio/providers.py` |
| Model discovery/install | `studio-api/app/image_runtime/model_discovery.py`; `studio-api/app/setup/catalog.py`; `studio-api/app/setup/diagnostics.py`; `studio-api/app/setup/paths.py`; `studio-api/app/model_storage/store.py`; `studio-api/app/comfy_health.py`; `studio-api/app/config.py` |
| Workflows | `config/image-workflows/certified-registry.json`; `config/video-workflows/certified-registry.json`; `studio-api/app/image_runtime/{contract,certified_registry,fingerprints,workflow_execute,output_gate,readiness,registry_sync,capability_probe}.py`; `studio-api/app/workflows/` |
| Request→Asset | `studio-api/app/image_product/{compile,service,api,history,versions,store}.py`; `studio-api/app/queue_worker.py` |
| Planning UI | `studio-web/src/components/image-studio/*`; `studio-web/src/contracts/{imagePipeline,cinematicImageStudio}.ts`; `studio-web/src/pages/ProjectEditor.tsx` |
| References | `studio-api/app/director_references/`; `studio-api/app/image_runtime/reference_assets.py`; `studio-api/app/image_pipeline/references.py`; `studio-api/app/image_product/references.py`; `studio-api/app/image_studio/api.py`; `studio-api/app/character_identity/canon.py` |
| LoRA | `studio-api/app/references/{models,ic_lora_status}.py`; `studio-api/app/setup/catalog.py` |
| History/Retake | `studio-api/app/image_product/{history,versions}.py`; `studio-api/app/timeline_retakes/`; `studio-api/app/director_timeline_w46/router.py` |
| Timeline handoff | `studio-api/app/director_timeline_w46/{contracts,router,service}.py`; `…/generation/{contracts,registry,request_builder}.py` |
| Co-Director tools | `studio-api/app/codirector/tools/definitions.py`; `…/tools/exposure.py`; `…/tools/handlers/image_pipeline_tools.py`; `studio-api/app/capabilities/registry.py` |
| Deletion cascade | `studio-api/app/project_cleanup.py`; `studio-api/app/routers/api.py` |
| GPU preflight | `studio-api/app/docker_runtime/gpu_preflight.py`; `studio-api/app/comfy_health.py`; `studio-api/app/vram_profiles.py` |
| Cert/interception | `studio-api/app/director_timeline_w46/generation/adapters/stub_cert.py`; `tests/e2e/image-pipeline/image-pipeline-foundation-autonomous-cert.spec.ts`; `studio-api/tests/test_m42_w2_image_runtime.py` |

## Appendix — External Sources (all accessed 2026-08-08)

- https://huggingface.co/krea/Krea-2-Turbo and /blob/main/README.md
- https://huggingface.co/krea/Krea-2-Raw and /blob/main/README.md
- https://github.com/krea-ai/krea-2
- https://www.krea.ai/krea-2-open-source
- https://www.krea.ai/blog/krea-2-technical-report
- https://huggingface.co/docs/diffusers/en/api/pipelines/krea2
- https://huggingface.co/docs/diffusers/api/models/krea2_transformer2d
- https://github.com/Comfy-Org/ComfyUI/pull/14589
- https://docs.comfy.org/tutorials/image/krea/krea-2
- https://comfyui.org/en/krea-2-open-source-models-are-now
- https://www.krea.ai/krea-2-licensing
- https://www.krea.ai/krea-2-commercial-license
- https://www.krea.ai/open-source-pricing
- https://www.krea.ai/docs/user-guide/features/krea-2
- https://www.krea.ai/docs/developers/krea-2/overview
