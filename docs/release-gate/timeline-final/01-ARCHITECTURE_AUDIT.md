# Timeline Architecture Audit & Reuse Map — feat/timeline-final-certification

**Auditor:** Subagent A (Timeline Architecture Auditor) — AUDIT ONLY, no files modified except this report.
**Repo:** C:/AdeptFilmWorks/AIVideoStudio
**Branch:** `feat/timeline-final-certification` — **HEAD `aa6b72bb0970e651bb25bd323c55ff3e40bb1b88`**
**Method:** Read-only code tracing (backend + frontend + config + docs). Every claim below is verified against code with file:line evidence. Unverified claims are explicitly labelled NOT VERIFIED. Nothing is certified from hearsay.

> Scope note: Avatar / Scene Creator Mini / Spatial Map / Movement Segments workstreams in the working tree were intentionally NOT audited. They are not Timeline.

---

## 0. Verdict posture

This is an **architecture audit + reuse map**, not a certification. It does **not** issue GO/NO-GO. It reports what exists, what is wired end-to-end, what is gated, and what is NOT implemented — so the primary agent can decide certification scope. Honest classification is used throughout: **READY / PARTIAL / UNAVAILABLE / NOT IMPLEMENTED**, never inferred.

---

## 1. Canonical persisted Timeline state (data model)

**Canonical store: the `scenes.director_json` TEXT column** — there is NO separate timeline table. `director_json` is a JSON blob containing three layers:

1. **`timelineMaster`** — the W46 production container (`SceneTimelineMaster`, pydantic), embedded via `embed_master_into_director_dict` (migration.py:261-264) and persisted COW by `save_master` (store.py:109-151).
2. **`timelineWorkspace`** — UI settings (trackDensity, displayMode, showFilenames, showThumbnails, snapEnabled, guidancePriority, timelineRevision, removedItems, layoutIntent, inpaintIntent) — `normalize_timeline_workspace` (store.py:32-58).
3. **Legacy Director 2.0 track keys** — `image_clips`, `prompt_segments`, `video_clips`, `audio_clips`, `sfx_clips`, `camera_clips`, `lipsync`, `playhead`, `duration_sec`, `media_mode` (`DirectorTimeline` model, director_timeline.py:127-153). These remain as the interactive NLE surface and as the flattened output view for approved batches (`bbclip_*` video clips, completion.py:270-330).

**Master schema** (`SceneTimelineMaster`, contracts.py:330-346): `version: int = 1`, `mode` (`image_planning`|`video_finishing`), `sceneGeneratorId`, `orchestratorMode`, `repairOverlapPolicy`, `preflightMode`, `batchBlocks[]`, `executionSnapshots{}`, `dismissedFailureJobIds[]`, `continuityPolicy`, `continuityBridges[]`, `migratedFromDirectorJson`, `migrationNote`.

**Versioning / migration:** there is no schema-version column or multi-version migration ladder. `version=1` is a frozen single contract; versioning is **code-driven** through `migrate_director_to_master` (migration.py:42-246):
- COW: never wipes working scenes; idempotent when already migrated (migration.py:50-61).
- `NEVER_COLLAPSE_EXISTING_MULTI_BATCH` — an existing master with batchBlocks is always preserved (migration.py:56-59).
- One legacy migration rule: all legacy clips → a single "Batch 1", preserving original legacy clip IDs in `legacyClipId` (migration.py:120-193) and audit metadata in `migrationMetadata`.
- `NO_AUTO_PERSIST_ON_READ`: GET /master only persists when the blob has no embedded timelineMaster at all (store.py:91-98) — prevents cementing a collapsed single-batch migration.

**Separate persisted stores (NOT in director_json):**
- `timeline_retakes`: per-project JSON files `data_dir/timeline_retakes/{project_id}.json`, schemaVersion 1 (timeline_retakes/store.py:18-37). Take registry per shot (baseline/alternate/active, append-only editHistory). MiniMax-specific engine labels.
- MiniMax H3 jobs/plans: file-based `project_dir(project_id)/jobs|plans` (minimax_h3/store.py, minimax_h3/route_a_adapter.py).
- LTX generation jobs: the relational `jobs` table (db.py:118-137, `kind=render_scene`, `params_json` carries the Timeline request).
- Frontend layout (viewer height, drawer widths, zoom, presets, track density): **localStorage** via `workspaceLayout.ts` — NOT backend-persisted. (workspaceLayout.ts load/save; TimelineWorkspaceStack.tsx:39-46)

---

## 2. Track matrix (implemented tracks, verified)

Legend: UI = creator-visible editor affordance; Gen input = reaches the generator request; Preview = appears in the Preview Monitor; Reload = restored after reload.

| Track | UI | Persistence | Generator input | Preview | Reload | Co-Director |
|---|---|---|---|---|---|---|
| **Image** | AssetTray → add: batch-aware → `directorTimelineAddClipToBatch` → batch.visualClips (DirectorTracks.tsx:869-913); no batch selected → legacy `image_clips` via putDirector (TimelineEditorShell.tsx:664-698) | legacy `image_clips` + batch `visualClips` (BatchClip kind=image) | YES → `sourceAnchors` → `startImageAssetId` / `planningStartImageAssetId` (request_builder.py:73-100); I2V-capable generators use it as start frame | YES — `activeVisual` via resolveTimelineAtTime.ts:81-96 | YES | `timeline.add_asset`, `timeline.propose_add_image_clip` (ProposalService-gated) |
| **Video** | AssetTray → legacy `video_clips` (handleAddAssetToTimeline) or batch `visualClips`; approved batches placed as `bbclip_*` video_clips | legacy `video_clips` + batch `visualClips` + placed `bbclip_*` | YES as **video reference** (`videoReferenceAssetId`/trim, request_builder.py:13-32) — gated per adapter caps (LTX/Seedance support, request_builder keeps it, adapter.validate refuses silent drop, adapter.py:99-123) | YES | YES | YES (read tools + references) |
| **Timed Prompt** | Inspector prompt field → `patch_batch` promptSegments (TimelineInspector.tsx:660-690); legacy `prompt_segments` in DirectorTracks | batch `promptSegments` (TimelinePromptSegment) + legacy `prompt_segments` (PromptSegment) | YES — joined text + negativePrompt (request_builder.py:69-71); `@Token says "…"` dialogue cues compiled to `speechWindows` (speech_compile.py:90-216) | YES — prompt lower-third overlay (resolveTimelineAtTime, TimelinePreviewComposer) | YES | `timeline.propose_add_prompt_segment` (ProposalService-gated) |
| **Dialogue / Voice** | Prompt `dialogue` field + `@Token says` syntax; Lip Sync clips with speaker binding | `dialogue` on PromptSegment/TimelinePromptSegment; `speechWindows` on batch; lipsync tracks | **NOT delivered as TTS/audio to the video generator** — speech_compile produces metadata windows only; Lip Sync audio without a speaker **blocks generation** (`LIPSYNC_SPEAKER_REQUIRED`, speech_compile.py:44-61, orchestrator.py:311-318) | Prompt overlay only | YES | `voice.prepare_timeline_dialogue`, `voice.replace_timeline_dialogue` (codirector registry) |
| **Audio** | AssetTray → legacy `audio_clips` (handleAddAssetToTimeline); batch `audioClips` exists in API but no verified UI add path | legacy `audio_clips` + batch `audioClips` | **NOT passed to video generators** (no audio-reference caps on any current adapter; LTX 2.5 `audio_generation` is provider-native audio, not clip audio) | YES — `activeAudio` (resolveTimelineAtTime.ts:148) | YES | `timeline.add_audio` (ProposalService) |
| **Music** | NOT implemented as a Timeline clip affordance — generation_tools catalog `audio.music.generate` / `audio.sfx.generate` (generation_tools/catalog.py:92-114) creates Library assets, gated by `STUDIO_FEATURE_AUDIO_PRODUCTION_V1` + M210B sandbox (ops.py:43-67); no verified path to place result on a Timeline track | Library asset (audio.music) only | NO | NO | Library asset reloads; clip placement NOT IMPLEMENTED | `audio.generate_music` codirectorTool |
| **SFX** | Same as Music — catalog tool exists; Timeline SFX clip UI NOT verified | batch `sfxClips` + legacy `sfx_clips` schema exists; UI creation NOT verified | NO | YES — `activeSfx` (resolveTimelineAtTime.ts:169) | YES (if present) | `audio.generate_sfx` codirectorTool |
| **Generation (batch state)** | TimelineMasterPanel/Toolbar: Add Batch, Generate Scene/Batch, cancel, repair, retake, approve/reject | `batchBlocks` → `generationJobs`, `candidateVersions`, `approvedClip`, `executionSnapshots` (all in timelineMaster) | N/A (it is the pipeline) | YES — generation state machine (TimelinePreviewComposer.tsx:35-52, 81+) | YES | `timeline.propose_generate_scene`, `timeline.propose_retake`, `timeline.propose_repair_range` |
| **Reference** | ReferencesPane / TimelineReferencesPanel + ReferenceTokenAutocomplete; AssetTray "Add to References" | `reference_binding_ids` on prompts, `batch.references`, `sourceAnchors`; scene_references tables (db.py:923-987: `timeline_reference_sets` / `_versions` / `_bindings`) | YES — compiled to `referenceAssetIds` / `videoReferenceAssetId` (reference_compile.py:155+), never as alias text; over-limit/unsupported refs kept and refused at generate (honest) | Chips/thumbnails | YES | `timeline_references.*` tools + `timeline.attach_optional_reference` |
| **Camera / production metadata** | Camera track (DirectorTracks camera_clips) + camera catalog dropdown (camera_catalog.py) | legacy `camera_clips` (CameraClip: motion_type, rig) + batch `cameraInstructions` | **NOT passed as `cameraMotion`** — every current adapter has `supportsCameraControls=False`, so request_builder sets `cameraMotion=None` (request_builder.py:189); camera strategy is summarized into snapshot settings + preflight warnings (orchestrator.py:1044-1067) | YES — `activeCameraInstruction` (resolveTimelineAtTime.ts:188) | YES | `timeline.propose_add_camera`, `timeline.propose_update_camera` (execution_authority.py:36-37) |

**Not-present tracks (asked in audit brief):** "Generation" is a pipeline not a track; "Timed Prompt" is the prompt track; there is no dedicated "Music" or "SFX" clip creation UI verified in timeline-master. Dialogue is metadata, not audio output. All verified above.

---

## 3. Clip / item contracts (frozen, contracts.py)

- **`BatchClip`** (contracts.py:211-235): `id` (clip_), `kind` (image|video|audio|sfx|camera), `assetId`, `start`, `length`, `trimStart`, `label`, `role` (start/middle/end/guide), `volume`, `fade_in`, `fade_out`, `motion_type`, `rig`, `legacyClipId` (migration audit).
- **`TimelinePromptSegment`** (contracts.py:110-127): `id` (ps_), `start`, `length`, `text`, `role`, `strength`, `negativePrompt`, `anchorIds`, `executionStrategy` (native|compiled|split), `versionId` (psv_), `legacyPromptSegmentId`, `referenceBindingIds`, `userDirection`, `productionPrompt`, `dialogue`.
- **`TimelineVisualAnchor`** (contracts.py:101-107): `id` (anc_), `kind` (image|video|end_frame), `assetId`, `label`, `atTime`, `strength`.
- **`GenerationJobRef`** (contracts.py:153-165): `id` (job_), `executionSnapshotId`, `queueJobId`, `providerJobId`, `generatorId`, `status`, `locality` (local|hosted), `hostedCancelSupport`, `apiUsed`, `progress`, `error`.
- **`CandidateVersion`** (contracts.py:168-186): `id` (cand_), `executionSnapshotId`, `assetId`, `label`, `generatedDuration`, `approved`, `takeId` (take_), `parentTakeId`, `incomingBridgeId`, `continuityAware`, `reTakeReason`, `sequenceMemory`, `incomingContinuity`, `originalTakeIntent`, `takeState`, `userCorrection`.
- **`ApprovedClip`** (contracts.py:203-208): `assetId`, `executionSnapshotId`, `candidateId`, `approvedAt`, `playable`.
- **`ExecutionSnapshot`** (contracts.py:130-150): `id` (snap_), `batchBlockId`, `immutable: True`, `compiledPrompts`, `promptLayerVersionIds`, `references`, `selectedGenerator`, `capabilityStrategy`, `settings`, `runtime`, `providerId`, `duration`, `sourceAnchors`, `continuityState`, `inPaintStrategy`, `promptIntelligence`. Immutable — created once, never mutated (orchestrator.py:221-223).
- **`BatchStatus`** (contracts.py:26-37): Draft, Ready, Queued, Generating, Failed, Cancelled, CandidateReady, Approved, ApprovedConfigurationChanged, RegenerationRecommended.
- Frontend parity: `studio-web/src/timelineMaster/contracts.ts` mirrors the Python models (1:1, incl. BatchStatus/InPaintStrategy/ContinuityStrategy).

---

## 4. Library ingest → Timeline clips

1. **Library** = `assets` table (db.py:94-115). Timeline Library filter admits **image/video/audio only** (`TIMELINE_MEDIA_TYPES`, timelineMediaTypes.ts:10).
2. **Add to Timeline**: batch selected → `api.directorTimelineAddClipToBatch` → `orchestrator.add_clip_to_batch` (batch-owned `visualClips`, orchestrator.py:791-850, event `timeline.clip_added`); no batch selected → legacy `putDirector` writing `image_clips`/`video_clips`/`audio_clips` (TimelineEditorShell.tsx:664-698).
3. **Add as reference**: `api.sceneReferences.attach` → scene_references binding (TimelineEditorShell.tsx:700-710); compiled by `apply_compiled_references` at generate/preflight (reference_compile.py:155+).
4. **Approved-media flow (verified end-to-end)**: adapter `collect_result` → `import_output_to_project_library` (minimax_h3/route_a_adapter.py) → Asset row → `apply_shared_completion` (completion.py:114-267) → `complete_batch_candidate` (candidate) → `approve_candidate` (approvedClip + activeTakeId, orchestrator.py:570-635) → `place_approved_batches_on_timeline` (idempotent `bbclip_*` upsert into director_json.video_clips, completion.py:270-330). Draft outputs are tagged `-draft` and never auto-approved (completion.py:206-216).
5. **Source image bindings**: `sourceAnchors[].assetId` + lineage record in `batch.references[timelineGenerationLineage]` carrying `startImageAssetId`, `startImageSha256`, `comfyImageName`, `workflowId` (completion.py:77-111) — the I2V cert verified these survive reload.

---

## 5. Generation / batch contracts

- **`BatchBlock`** (contracts.py:238-287): stable `id` (bb_), `order` (mutable), `label`, `status`, `generatorId`, `generatorOverride`, `duration` (DurationState: planned/generated/timelineVisible/sourceMedia — never a single overloaded duration), `sourceAnchors`, `promptSegments`, owned clip arrays (`visualClips`/`audioClips`/`sfxClips`/`cameraInstructions` — BATCH_OWNED_CLIPS), `generationJobs`, `candidateVersions`, `approvedClip`, `repairRanges`, `references`, `speechWindows`, `lora`, `configFingerprint` (sha256 of config), `pendingSnapshotId`, `activeTakeId`, `incomingBridgeId`, `continuityAwareRetake`, `downstreamStale`.
- **Grouping**: `generate_scene` (scope full/selected/ready/current, orchestrator.py:1240-1325). **Sequential (default)** — first eligible batch submitted; later batches `stage_batch_snapshot` → status Queued + `pendingSnapshotId`; `submit_next_queued_batch` submits the lowest-order Queued batch when the active one reaches a terminal state (provider concurrency = 1). **Parallel** mode submits each eligible batch immediately.
- **Result binding**: `executionSnapshotId` joins `GenerationJobRef` → `CandidateVersion` → `ApprovedClip`; the watcher (generation/watcher.py) polls `adapter.get_status` every 3 s (timeout 1200 s), on completion calls `adapter.collect_result` then `apply_shared_completion`; terminal failures mark the batch Failed/Cancelled but **never rewrite an Approved/CandidateReady batch** (TERMINAL_STATUS_GUARD, watcher.py:156-165).

---

## 6. Generator registry & adapters — honest readiness

Registry: `generation/registry.py:30-56` (MiniMaxH3LocalAdapter, MiniMaxH3I2VLocalAdapter, LtxLocalAdapter, SeedanceApiAdapter, KlingApiAdapter, + env-gated cert stub). `capabilities.py:10-219` is the UI-facing capability registry; `video_runtime/certified_registry.py` + `config/video-workflows/certified-registry.json` is the workflow-certification authority; `video_runtime/production_gate.py` + `config/video-workflows/production-gate.json` defines production-required workflow keys.

| Generator | Registry capability (capabilities.py) | Adapter reality | Workflow-cert authority | Classification |
|---|---|---|---|---|
| **ltx-local / ltx-2.5-full / ltx-2.5-distilled / ltx-2.5-comfy** | `capabilityLabel="Certified"`, `executable=True`, max 20 s, native audio (except comfy), draft `local_live` (capabilities.py:38-111) | Submits studio `Job(kind=render_scene, engine=ltx)` → in-process queue_worker → Comfy (ltx_local.py:96-185); polls Job row; cancel via codirector `_cancel_job`; validates LTX 2.5 components for ltx-2.5-* variants (ltx_local.py:78-94) | `ltx.scene`, `ltx.simple_i2v`, `ltx.ingredients_ic_lora`, `ltx_25.i2v` = **CERTIFIED** (certified-registry.json:85,175,260,446); **`ltx_25.t2v` = Built (NOT certified)** (line 277) | **READY** (subject to model install + Comfy reachability). Registry-honesty gap: capabilities.py calls ltx-2.5-full/distilled "Certified" while the certified-registry t2v leaf is "Built". |
| **minimax-h3-local (T2V)** | `capabilityLabel="Testing"`, `executable=True`, 5 s, 480x256, no draft (capabilities.py:17-36) | Real Route A adapter → minimax_h3 package: plan/preflight → `create_job_or_block` → isolated ComfyUI :8192 (minimax_h3_local.py:70-148); polls `get_job`; refuses LTX fallback (H3_SILENT_FALLBACK, minimax_h3_local.py:266-274) | Not in certified-registry.json; minimax_h3/capability.py:61-108 declares private-local Route A "Testing/ready" when gate active | **PARTIAL / GATED-READY**: genuinely implemented + **model files VERIFIED PRESENT on this machine** (`D:/01_Models/Video/MiniMax-H3/ComfyUI/*` — all 4 required .safetensors), but locked behind `feature_flags.minimax_h3_private_local` **default False** (feature_flags.py:91), owner-only, isolated :8192 runtime (private_access.py:16-86) and live `RouteARuntimeAdapter().readiness()` probe (preflight.py:100-115). NOT certified as a workflow; cert'd as a private profile only. |
| **minimax-h3-i2v-local** | NOT listed in capabilities.py:10-219 (menu comes from adapter registry via `service.generators()` → `timelineAdapters`, service.py:260-266; draftCapabilities.ts:28-29 mirrors it) | Real Route A I2VA (one-frame) with **fail-closed I2V graph binding** (LoadImage + first_frame verified post-submit, minimax_h3_i2v_local.py:128-133, 326-353), refuses T2V downgrade and LTX fallback | GO per `TIMELINE_TWO_BATCH_MINIMAX_I2V_FINAL_CERTIFICATION_REPORT.md` (route-a-experimental-private-i2va, Playwright 1 passed, 56 unit/API tests) | **PARTIAL / GATED-READY**: certified GO for the private owner-only Route A profile; same feature-flag/runtime gating as T2V. Not in the capabilities.py dock list (surfaced only through adapter registry). |
| **wan-local** | `capabilityLabel="Certified"`, **`supportsTimelineGeneration=False`** (capabilities.py:112-125) | No Timeline adapter registered | wan.first_last_frame / wan.three_frame CERTIFIED for scene render | **UNAVAILABLE for Timeline** (capability-flipped, by design) |
| **hunyuan-video-1.5 / 13b-local** | Certified/Requires Setup, **`supportsTimelineGeneration=False`** (capabilities.py:126-155) | No Timeline adapter | Built leaves allowed until per-provider cert (workflow_resolver.py:69-73) | **UNAVAILABLE for Timeline** |
| **seedance-kie (seedance-api)** | `capabilityLabel="Testing"`, **`executable=False`** (capabilities.py:156-171) | Adapter HAS a live fal.ai path (fal_api_key from secrets_store → upload → run_fal_model → download → library import; seedance_api.py:78-191) + in-memory ledger | `fal.seedance` = **BLOCKED** (certified-registry.json:1030) | **PARTIAL**: real provider path exists but capability-gated off; requires fal_api_key secret; cloud workflow not certified. |
| **kling-fal (kling-api)** | `capabilityLabel="Certified"` but **`executable=False`** (capabilities.py:172-186) | Adapter is an **in-memory ledger only** — records status "running"; completes only via `testInjectResult`; **no real provider call** (kling_api.py:64-92) | `fal.kling` = **BLOCKED** (certified-registry.json:1095) | **UNAVAILABLE / NOT LIVE** (contract shell only). "Certified" label is misleading; honest flag is `executable=False`. |
| **comfy-workflow** | Available, executable=False, Requires Setup (capabilities.py:187-196) | — | — | **UNAVAILABLE** |
| **cert-stub-local** | Appears only when `ADEPT_TIMELINE_CERT_STUB=1` (capabilities.py:199-218) | Records requests to JSONL sink; test-controlled lifecycle; no GPU code (stub_cert.py) | — | **TEST ONLY** (env-gated) |

**MiniMax H3 vs LTX headline:** MiniMax H3 (T2V + I2V) is genuinely runnable on this machine (models present, adapter real, I2V Playwright-certified GO) but is **feature-flag gated off by default** (`minimax_h3_private_local=False`) and labeled "Testing". LTX is the **default production engine** ("Certified") routed through the studio job queue; its certified workflow set is solid, but the `ltx_25.t2v` leaf is "Built" not "Certified" while the UI claims Certified for ltx-2.5-full/distilled — verify before certifying LTX 2.5 T2V specifically.

---

## 7. Generation history, retake, provenance

- **History**: `batch.generationJobs` + immutable `master.executionSnapshots` + `candidateVersions` (take labels Take A/B/…). Per-generation lineage appended to `batch.references` as `timelineGenerationLineage` (completion.py:46-111): generatorId, providerJobId, queueJobId, outputAssetId, startImageAssetId/Sha256/comfyImageName, workflowId, draftMode/pathway, aspectRatio, resolution, quality.
- **Retake — two systems**:
  1. **Batch retake** (orchestrator.retake_batch, orchestrator.py:1349-1416): new job + new immutable snapshot; structured retake memory (sequenceMemory, incomingContinuity, originalTakeIntent, takeState, userCorrection) compiled via continuity.compile_retake_memory; never mutates prior snapshots; `activate_take` = `approve_candidate`; event `timeline.retake_started`.
  2. **timeline_retakes store** (separate JSON file per project): baseline/alternate/active takes with append-only editHistory, ghost-take guard (cancelled jobs cannot register), MiniMax-specific provenance (timeline_retakes/store.py:78-249). Used by TimelineRetakeDrawer (retake drawer) which also embeds MiniMaxH3PlanPanel.
  - Two retake registries coexist; the store is file-based, MiniMax-hardcoded (`engine: "MiniMax H3"`), and not integrated with the batch candidateVersions.
- **Provenance**: `generation_tools/lineage.py` (`register_derived_asset` — parent_asset_id, op, model, asset_graph add_version/add_edge, library assign); `video_runtime/certification_ledger.py`; `minimax_h3/provenance.py` (`build_receipt`).

---

## 8. Co-Director Timeline surface

- **Context package**: `codirector/timeline_context/service.py` `build_timeline_context_package` — bundles wiki canon (story, characters, locations), casting, continuity locks, production notes, reference assets, generation constraints, **readiness consumed from the Production Readiness Service** (Timeline never invents it), `gateLevel`, SceneCraft-ready hierarchy (contracts.py:81-114). Consumed by the Timeline via `useTimelineContextPackage` → `/api/codirector/projects/{id}/timeline-context/{sceneId}`.
- **Smart gates**: `smart_gates.py` — EXPLORATION always allowed; PRODUCTION_LOCK blocks final generation when readiness BLOCKED; PRODUCTION_WARNING warns on PARTIAL; `can_generate_scene` guard.
- **Read tools** (codirector/tools/registry.py:280-290): `timeline.get_workspace`, `get_playhead`, `get_settings`, `get_guidance_priority`, `inspect_batches`, `preflight`, `explain_asset_reference_name`, `focus_ui`, `inspect_layout`, `inspect_lipsync`, `validate_lipsync`; plus `timeline_references.*` (get_timeline_image, list_timeline_images, get_reference_set, list_reference_bindings, build_generation_reference_package, suggest_reference_bindings).
- **Mutation tools** — approval-gated via ProposalService (preview → approve → apply): `timeline.render`, `timeline.add_asset`, `timeline.add_audio`, `timeline.prepare`, `timeline.build_shot`, `voice.prepare_timeline_dialogue`, `voice.replace_timeline_dialogue`, `voice_performance.place_on_timeline`, `propose_timeline_render`, `propose_batch_timeline`, etc. (registry.py:434-826). Execution authority explicitly gates `timeline.propose_add_image_clip`, `propose_add_prompt_segment`, `propose_add_batch`, `propose_add_camera`, `propose_update_camera`, `update_settings`, `set_playhead` (execution_authority.py:33-48).
- **HTTP dispatch surface** (`timeline_tools.py`): `/director-timeline/tools` + `/tools/dispatch` with a soft `approved` bool; mutations refuse without approval (`APPROVAL_REQUIRED`, timeline_tools.py:82-90); add_image_clip / add_prompt_segment refuse direct HTTP dispatch entirely (USE_CODIRECTOR_PROPOSAL_SERVICE, timeline_tools.py:105-118). Co-Director path is the registry + ProposalService; HTTP dispatch is legacy/direct.

---

## 9. Production events (emitted names, verified)

Recorded via `production_events.record_production_event` (best-effort try/except):

- `timeline.batch_created` — service.py:123 (add), service.py:174 (duplicate)
- `timeline.batch_deleted` — service.py:224
- `timeline.clip_added` — orchestrator.py:839
- `timeline.generation_started` — orchestrator.py:439
- `timeline.generation_completed` — orchestrator.py:545
- `timeline.candidate_approved` — orchestrator.py:624
- `timeline.candidate_rejected` — orchestrator.py:668
- `timeline.retake_started` — orchestrator.py:1405

**NOT implemented** (asked in brief but absent): `prompt_added`, `clip_updated`, `candidate.generated`. There is no `timeline.clip_updated` (clip edits go through `patch_batch` silently) and no per-segment prompt event. Event recording failures are swallowed (never break the operation).

---

## 10. Save / reload (hydration path)

- GET `/director-timeline/projects/{p}/scenes/{s}/master` → `service.workspace` → `store.load_master` → `load_or_migrate_scene_master` (migrates only if no embedded master; NO_AUTO_PERSIST_ON_READ) → returns `{master, legacyMediaMode}` (store.py:81-106).
- GET bundle → `service.load_timeline_bundle` → `{master, directorTimeline, workspace, playhead}` (service.py:21-41).
- Frontend: TimelineEditorShell loads `api.directorTimelineMaster` + `api.getDirector` on scene select; DirectorTracks renders legacy tracks; Inspector edits batch config via `patch_batch` (patch, not full replace). PUT /master (full replace) exists in the API but **no web component calls it** (verified — api.ts has no directorTimelinePutMaster consumer). Workspace settings live in `timelineWorkspace` inside director_json; UI layout lives in localStorage.
- Approved batches place `bbclip_*` video clips into director_json on every approve/completion (idempotent upsert), so reload shows the finished sequence in the NLE view (completion.py:270-330).

---

## 11. Idempotency (existing contracts)

- **Migration**: idempotent (existing master preserved; multi-batch never collapsed) — migration.py:50-61; gate flag `migrationIdempotentPassed` (contracts.py:429).
- **Completion**: `apply_shared_completion` — same approvedClip asset+snapshot+Approved → idempotent re-place; existing candidate (snapshot+asset) → idempotent (completion.py:152-184); `bbclip_` placement upsert by stable id (completion.py:306-316).
- **Submission**: `generate_scene` skips Generating batches; `submit_next_queued_batch` no-ops while any batch is Generating or none Queued (orchestrator.py:1175-1181).
- **Staged-snapshot invalidation**: config fingerprint change on a Queued batch clears `pendingSnapshotId` and returns it to Ready (orchestrator.py:760-769); approval invalidation → `ApprovedConfigurationChanged` (orchestrator.py:746-753).
- **dismiss_failure**: idempotent append (service.py:71-73).
- **Config fingerprint**: sha256 over generatorId/duration/anchors/prompts/refs/repairs/lora (migration.py:21-39).
- **NOT implemented**: client-supplied idempotency keys for clip/job creation. POST /clips always creates a new clip (orchestrator.py:813-817 assigns a fresh id if absent); POST /generate has no `requestId`. The Co-Director layer has `codirector_plan_command_idempotency` (db.py:475) but the Timeline HTTP path does not use it.

---

## 12. Reuse map — what EXISTS and MUST BE REUSED (not rebuilt)

Backend (studio-api):
1. **`director_timeline_w46`** — the canonical Timeline Master system: frozen contracts (contracts.py), COW store (store.py), service façade (service.py), orchestrator (orchestrator.py), idempotent migration (migration.py), capability registry (capabilities.py), camera catalog (camera_catalog.py), repair overlap policy (repair_policy.py), continuity (continuity.py), approval-gated tools (timeline_tools.py), env-gated workflow export (workflow_export.py), production gate (production_gate.py).
2. **`director_timeline_w46/generation`** — provider-agnostic generation layer: normalized contracts, request builder, adapter protocol + shared validation, registry (no silent substitution), watcher, shared completion + placement (completion.py), speech/reference compilers.
3. **Adapters**: `minimax_h3_local.py`, `minimax_h3_i2v_local.py`, `ltx_local.py`, `seedance_api.py`, `kling_api.py`, `stub_cert.py` (env-gated).
4. **`minimax_h3`** — MiniMax H3 runtime surface (Route A adapter, preflight, capability/territory gating, private access, provenance, store, planner, api). Reuse — do NOT re-implement.
5. **`video_runtime`** — certified workflow registry, compatibility registry, production gate, workflow resolver/execute (fingerprint + graph drift checks), output gate (playable media validation), certification ledger.
6. **`scene_references`** (tables + repository) — reference bindings used by reference_compile.
7. **`production_events`** — event ledger.
8. **`timeline_retakes`** — take registry store + router.
9. **`generation_tools`** — tool catalog (upscale, chroma key, music/SFX generation gated), ops, lineage (non-destructive derived assets), api.
10. **`codirector/timeline_context` + codirector/tools registry + ProposalService** — CD Timeline read/mutate surface.
11. **`queue_worker` / Job table** — LTX execution path.

Frontend (studio-web):
12. `timeline-master/*` — TimelineMasterPanel, TimelineEditorShell, TimelineToolbar, TimelineInspector, TimelineSettingsDrawer, TimelineRetakeDrawer, TimelinePreviewComposer (sole preview source of truth), resolveTimelineAtTime (pure resolver), CompactRenderQueue, TimelineGeneratorBanner, TimelineInpaintWorkspace, SceneStatusStrip, useTimelineContextPackage.
13. `DirectorTracks.tsx` — interactive track rendering (legacy tracks + batch-aware clip add).
14. `timelineMaster/*` — frozen TS contracts, draftCapabilities (generator options from adapter registry), timelineFocus (CD↔shell focus bus), timelineHotkeys, workspaceLayout (localStorage persistence), helpCatalog.
15. `timelineMediaTypes.ts` (library media purity), `api.ts` director-timeline + timeline-retakes + timeline-context clients.

Tests/evidence to reuse:
16. `studio-api/tests/test_timeline_generation_adapters.py` (24 test fns, 904 lines), `test_m42_w46_director_timeline.py` (12 test fns), `test_timeline_retakes.py`, `test_timeline_reference_bindings.py`, `test_timeline_continuity_contracts.py`, `test_timeline_context_gates.py`, `test_m42_w46_codirector_timeline.py`, `test_timeline_prompt_refs_speech.py`, `test_timeline_camera_motion_refs.py`, `test_timeline_handoff_integrity.py`.
17. `tests/e2e/timeline/*.spec.ts` — 14 specs incl. `timeline-two-batch-minimax-i2v-final-certification.spec.ts`, `timeline-two-batch-final-certification.spec.ts`, `timeline-multi-batch-wiring-cert.spec.ts`, `timeline-multi-batch-preview-monitor-cert.spec.ts`, `timeline-nle-usability-cert.spec.ts`, `timeline-timed-prompt-track.spec.ts`, `timeline-semantic-references-lipsync.spec.ts`, `timeline-camera-motion-library-preview.spec.ts`, `timeline-draft-aspect-videoref.spec.ts`, `timeline-layout-library-references.spec.ts`, `timeline-audit-repair-production-readiness-cert.spec.ts` (also tests/e2e/m42/m42-w46-* and tests/e2e/final-systems/timeline-minimax-retake.spec.ts).
18. Certification docs: `TIMELINE_TWO_BATCH_MINIMAX_I2V_FINAL_CERTIFICATION_REPORT.md` (GO), `TIMELINE_TWO_BATCH_FINAL_CERTIFICATION_REPORT.md` (NO-GO for I2V requirement but GO for batching/lineage/placement/reload sub-gates), `TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md` (pre-implementation audit — superseded for the generation layer, which is now implemented).

---

## 13. Canonical state contracts (exact shapes to build against)

**TIMELINE EDIT STATE** = `scenes.director_json` blob with three layers:
```jsonc
{
  // legacy interactive tracks (DirectorTimeline)
  "media_mode": "image" | "video",
  "duration_sec": 5.0,
  "image_clips": [{ "id", "asset_id", "start", "length", "role": "start|middle|end|guide", "label" }],
  "prompt_segments": [{ "id", "start", "length", "text", "weight", "negative_prompt",
                        "reference_binding_ids": [], "user_direction", "production_prompt", "dialogue" }],
  "video_clips": [{ "id", "asset_id", "start", "length", "trim_start", "label" }],
  "audio_clips": [{ "id", "asset_id", "start", "length", "volume", "fade_in", "fade_out" }],
  "sfx_clips":   [ /* same as audio_clips */ ],
  "camera_clips":[{ "id", "start", "length", "motion_type", "rig", "label" }],
  "lipsync": { "tracks": [{ "id", "clips": [{ "id", "start", "length", "audio_asset_id",
              "speaker_binding_id", "character_id", "character_name" }] }] },
  "playhead": 0.0,
  // W46 production container
  "timelineMaster": {
    "version": 1, "mode": "image_planning" | "video_finishing",
    "sceneGeneratorId": null, "orchestratorMode": "sequential_continuity",
    "repairOverlapPolicy": "block", "preflightMode": "warnings_only",
    "batchBlocks": [ /* BatchBlock (see section 5) */ ],
    "executionSnapshots": { "<snap_*>": { "id", "batchBlockId", "immutable": true,
      "compiledPrompts": { "segments": [...], "finalProviderPrompt"?, "creatorPrompt"? },
      "promptLayerVersionIds": [], "references": [], "selectedGenerator", "capabilityStrategy",
      "settings": { "label", "order", "guidancePriority"?, "cameraStrategy"? },
      "runtime": "local"|"hosted", "providerId", "duration": { "plannedDuration",
      "generatedDuration"?, "timelineVisibleDuration"?, "sourceMediaDuration"? },
      "sourceAnchors": [], "continuityState": {}, "inPaintStrategy"?, "promptIntelligence"? } },
    "dismissedFailureJobIds": [],
    "continuityPolicy": { "autoContinuity", "configuredTailDuration", "locality", "continuityAwareRetake" },
    "continuityBridges": [{ "bridgeId", "sceneId", "sourceBatchId", "targetBatchId",
      "sourceTakeId"?, "contextVersion", "configuredTailDuration", "effectiveTailDuration",
      "tailAssetId"?, "lastFrameAssetId"?, "continuityStrategy", "continuityModel"?,
      "continuityState", "status", "createdAt", "supersededAt"?, "error"? }],
    "migratedFromDirectorJson": false, "migrationNote": null
  },
  "timelineWorkspace": { "settings": { "trackDensity", "displayMode", "showFilenames",
      "showThumbnails", "snapEnabled" }, "guidancePriority", "timelineRevision",
      "removedItems": [], "layoutIntent": {}, "inpaintIntent": {} }
}
```

**BATCH STATE** (BatchBlock): see sections 3/5 — `status` lifecycle Draft→Ready→Queued→Generating→(Failed|Cancelled)→CandidateReady→Approved→(ApprovedConfigurationChanged|RegenerationRecommended); `generationJobs[]` (per snapshot), `candidateVersions[]` (per take), `approvedClip` (single), `configFingerprint` (sha256), `pendingSnapshotId` (sequential staging), `downstreamStale`.

**GENERATION RESULT STATE**:
- Provider-normalized: `TimelineGenerationResult` {internalJobId, providerJobId, queueJobId, generatorId, status(queued|running|completed|failed|cancelled|blocked), progress, outputAssetIds[], duration?, resolution?, apiUsed, providerMetadata, errorCode?, errorMessage?} (generation/contracts.py:125-138).
- Persisted: CandidateVersion(assetId, executionSnapshotId, takeId) + ApprovedClip(assetId, executionSnapshotId, candidateId) + lineage record in batch.references + placed `bbclip_{batchId}` video_clip (completion.py).

---

## 14. Architecture risks / gaps (concrete)

1. **Dual editing surfaces can diverge** — legacy director_json tracks vs BatchBlock-owned clips are both editable; legacy edits made after migration do not propagate into batch clips, and batch edits only write back to legacy tracks via approved placement (bbclip_). resolveTimelineAtTime prefers batch-owned visualClips when present, else legacy tracks — a deliberate but fragile precedence. Any new clip feature must pick ONE owner (batch-owned is canonical; legacy is the flattened NLE view per BATCH_OWNED_CLIPS).
2. **MiniMax H3 is gated off by default despite being certified-ready**: `feature_flags.minimax_h3_private_local=False` (feature_flags.py:91). All four model files exist on this machine (verified), and I2V is Playwright-certified GO, but the capability label is "Testing" and every generate fails closed unless the flag + isolated :8192 runtime + readiness probe pass (preflight.py:100-115). Certification claiming "MiniMax H3 is ready" must state the gating explicitly.
3. **`ltx-2.5-full/distilled` claim "Certified" while `ltx_25.t2v` workflow is "Built"** in config/video-workflows/certified-registry.json:277 — capabilities.py:52-93 (Certified) vs the workflow authority (Built) is a registry-honesty mismatch to reconcile before certifying LTX 2.5 T2V.
4. **Kling adapter is not live** — in-memory ledger, completes only via test injection (kling_api.py:64-92); registry honestly sets executable=False but keeps capabilityLabel="Certified" (capabilities.py:177), and fal.kling is BLOCKED in the certified registry. Do not advertise Kling as usable.
5. **Seedance has a live fal.ai path but is capability-gated off** (`executable=False`, capabilities.py:161) and fal.seedance is BLOCKED; requires fal_api_key secret. PARTIAL.
6. **Music/SFX generation does not reach the Timeline** — generation_tools catalog exists (gated by STUDIO_FEATURE_AUDIO_PRODUCTION_V1 + sandbox flags) but there is no verified UI path that places a generated music/SFX Library asset onto a Timeline track or batch clip. NOT IMPLEMENTED as a Timeline feature.
7. **Dialogue is not synthesized to audio in the generation path** — speech_compile produces metadata windows (`speechWindows`) and blocks generation on missing Lip Sync speakers, but no TTS step exists; voice tools are separate surfaces.
8. **Two retake systems coexist**: batch retake (master-integrated, continuity-aware, provider-agnostic) and timeline_retakes file store (MiniMax-hardcoded, per-project JSON, separate API). The file store's engine/provenance labels assume "MiniMax H3 / private-local / route-a"; it is not reconciled with candidateVersions. Risk of duplicate take truth.
9. **No client idempotency keys** on clip/job creation (POST /clips, POST /generate). Duplicate clicks can create duplicate clips/jobs (mitigated only by status guards server-side). If retry-safety matters, add requestId/clientToken or rely on the status guards + completion idempotency that already exist.
10. **Job persistence is split**: LTX jobs in the relational `jobs` table; MiniMax jobs in minimax_h3 file store; hosted jobs in in-memory ledgers (Seedance/Kling). No unified generation-job query surface for Timeline history.
11. **Production events are best-effort** (try/except swallow) and missing for clip updates and prompt edits — audit trail is incomplete for edit operations.
12. **Camera/production metadata does not drive generation**: no current Timeline adapter supports camera controls; camera instructions affect prompt/planning + preflight warnings only. Camera catalog + dropdown exist; execution fidelity is "Approximate"/"Unsupported" by design.
13. **Timeline generator menu is split across two registries**: capabilities.py dock list (drives `supportsTimelineGeneration` gating) vs generation adapter registry (drives `timelineAdapters` in /generators). minimax-h3-i2v-local lives only in the adapter registry — keep them in sync or menu/execution can disagree.
14. **Workspace layout persistence is localStorage-only** — viewer height/zoom/drawers do not survive device/incognito changes and are not part of the canonical scene state; the `timelineWorkspace` backend block covers only display/settings, not layout geometry.
15. **Full PUT /master replace endpoint exists** and can collapse state if ever used by a stale client (it does not merge workspace/layout); no web component currently calls it, but the endpoint is exposed — consider deprecating or hardening it.
16. **directorTimelineGo gate is artifact-driven** (production_gate.py reads artifacts/*.json + doc stamps; REQUIRED_GATE_FLAGS contracts.py:419-561). The current tree contains artifacts for timeline-ux / timeline-viewer / timeline-camera / timeline-lipsync-inpaint only — the final gate's live status was NOT verified by running the server in this audit (audit is static).

---

## 15. What was NOT verified (honest)

- Live runtime behavior of any generator (server not started; this is a static audit). MiniMax model files presence was verified on disk; ComfyUI :8192 readiness was NOT probed.
- Whether `directorTimelineGo` currently evaluates GO — production_gate.py reads artifacts; not executed.
- Playwright suite status at HEAD aa6b72b — the two-batch reports were certified at older HEAD fa09c99d on branch feature/ai-guided-setup.
- UI affordances I could not trace (music/SFX clip creation, batch audio add) are reported as NOT VERIFIED rather than assumed.

---

*End of audit. Report file: docs/release-gate/timeline-final/01-ARCHITECTURE_AUDIT.md (this file). No other files modified.*