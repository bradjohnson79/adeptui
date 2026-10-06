# 02 — Track Wiring & State Integrity Matrix

**Subagent B — Wiring & State Integrity Auditor**
**Branch:** `feat/timeline-final-certification` @ HEAD `aa6b72b`  —  **Status:** AUDIT-ONLY (no files modified)
**Method:** static code audit; every claim cites file:line evidence below.

> Classification: **WIRED** = round-trips UI → API → persistence → reload (and reaches the generator where applicable). **PARTIAL** = round-trips but is bypassed/duplicated/partial. **UI-ONLY** = UI/local only, never persisted. **BACKEND-ONLY** = backend/persisted, no UI writes/reads. **STALE** = declared/persisted, never read by any consumer. **BROKEN** = creator-visible path does not do what the UI implies.

## 1. Per-field classification table

| # | Field | Chain | Status | Evidence (file:line) | Notes |
|---|-------|-------|--------|----------------------|-------|
| 1 | batchBlock.id | UI batch lane → POST/PATCH batch → director_json.timelineMaster.batchBlocks[].id → reload | WIRED | UI: DirectorTracks.tsx:1688-1696; api.ts:3633; service.py:98-115; store.py:147-151; migration.py:261-264 | Stable server-generated bb_ id (contracts.py:219,238-245); never re-keyed on reorder. |
| 2 | batch.order | add/duplicate/delete → sort by order → reload | WIRED | service.py:97,109-114,160-165,199-201; completion.py:297 | Reorder mutates order only; ids stable. |
| 3 | batch.label | Batch Inspector Name (Inspector.tsx:1142-1144) → PATCH label → orchestrator.py:705-706 → reload | WIRED | Inspector.tsx:1142-1144; orchestrator.py:705-706 | |
| 4 | batch.generatorId | Batch Inspector Generator select (Inspector.tsx:1206-1233) → PATCH generatorId → orchestrator.py:707-709 → snapshot.selectedGenerator (orchestrator.py:134,220) → request.generatorId (request_builder.py:62-66) → registry (registry.py:58-72) → reload | WIRED | Inspector.tsx:1206-1233; orchestrator.py:707-709,220,341-354; request_builder.py:62-66 | Hard lock against silent substitution (orchestrator.py:341-354). |
| 5 | batch.duration.plannedDuration | Inspector Planned Duration (Inspector.tsx:1146-1158) → PATCH → orchestrator.py:712-713 → request.duration (request_builder.py:185) → adapter check (adapter.py:82-90) → reload | WIRED | Inspector.tsx:1146-1158; orchestrator.py:712-713; request_builder.py:185; adapter.py:82-90 | |
| 6 | duration.generatedDuration / timelineVisibleDuration / sourceMediaDuration | complete_batch_candidate (orchestrator.py:529-532) → reload; shown Master panel (MasterPanel.tsx:283-289) | WIRED | orchestrator.py:529-532; MasterPanel.tsx:283-289 | Visible = min(planned,generated), no silent stretch (orchestrator.py:532). |
| 7 | batch.promptSegments[].text (Batch prompt) | Batch Inspector Prompt (Inspector.tsx:1159-1170 via persistBatchPrompt 640-662) → PATCH promptSegments → orchestrator.py:714-717 → request prompt (request_builder.py:69-70) → adapter → reload | WIRED (batch path) | Inspector.tsx:640-662,1159-1170; orchestrator.py:714-717; request_builder.py:69-70 | Only the Batch Inspector prompt drives generation. See #8. |
| 8 | Legacy prompt_segments (TIMED PROMPT lane) | lane add/move/trim (DirectorTracks.tsx:1049-1061,1901-1962) → putDirector → director_json.prompt_segments → reload (certified e2e) | PARTIAL / DISCONNECTED from generation | DirectorTracks.tsx:1049-1061,1901-1962; routers/api.py:934-952; timeline-timed-prompt-track.spec.ts:69-199 | Visible lane edits do NOT sync into batch.promptSegments after one-time migration (migration.py:56-61,95-118). Generation reads batch only (request_builder.py:69-70). §2.2. |
| 9 | TimelinePromptSegment.userDirection / productionPrompt / dialogue | declared backend (contracts.py:125-127) + frontend (contracts.ts:81-83) | STALE / BACKEND-ONLY | contracts.py:125-127; contracts.ts:81-83; request_builder.py:69-70; speech_compile.py:172 | No UI field writes them; no generator code reads them. Co-Director tool writes legacy user_direction/production_prompt (codirector/tools/handlers/director_timeline_tools.py:1353-1356), not the W46 batch fields. |
| 10 | batch.sourceAnchors[] (Start/End image, video refs) | Batch Start Image select (Inspector.tsx:1171-1204) → PATCH sourceAnchors → orchestrator.py:718-721 → request_builder start/end (request_builder.py:73-88,116-145) → I2V referenceAssignments (minimax_h3_i2v_local.py:97-103) → reload | WIRED | Inspector.tsx:1171-1204; orchestrator.py:718-721; request_builder.py:73-88; minimax_h3_i2v_local.py:97-103 | No implicit fallback to another image (request_builder.py:113-128; adapter.py:54-59,77-78). Quirk: first anchor labelled 'end' becomes end_image (request_builder.py:80-86). |
| 11 | batch.visualClips (per-batch image/video/audio/sfx/camera) | Add image w/ batch selected (DirectorTracks.tsx:864-908) → directorTimelineAddClipToBatch → orchestrator.add_clip_to_batch (orchestrator.py:791-850) → persisted → reload | PARTIAL | DirectorTracks.tsx:864-908; orchestrator.py:791-850; resolveTimelineAtTime.ts:83-97 | Persisted + used by preview resolver, but never rendered on any track (VISUAL lane renders legacy image_clips; DirectorTracks.tsx:1733-1897). Generation reads sourceAnchors, not visualClips. §2.1. |
| 12 | Legacy image_clips / video_clips (VISUAL lane) | add/drag/trim → putDirector → director_json → reload | WIRED to legacy store; NOT generation input | DirectorTracks.tsx:1733-1897; routers/api.py:934-952 | Reach generation only via one-time migration into sourceAnchors (migration.py:71-95). |
| 13 | Approved batch → bbclip_{batch.id} video clip | approve_candidate (orchestrator.py:594-606) → place_approved_batches_on_timeline (completion.py:270-330) → director_json.video_clips → reload | WIRED | orchestrator.py:594-606; completion.py:270-330; two-batch spec:343-349 | Idempotent upsert; sequential cursor start in batch order (completion.py:296-317). Batch visualClips[].start is not used for placement. |
| 14 | batch.approvedClip {assetId,executionSnapshotId,candidateId} | watcher → apply_shared_completion → approve_candidate (orchestrator.py:594-598) → reload | WIRED | watcher.py:43-61; completion.py:114-267; orchestrator.py:594-598 | |
| 15 | candidateVersions take lineage (takeId, parentTakeId, reTakeReason, sequenceMemory, userCorrection) | New take (Inspector.tsx:1399-1412) → retake_batch (orchestrator.py:1349-1416) → complete_batch_candidate (orchestrator.py:510-527) → take buttons (Inspector.tsx:1413-1430) → activate-take → approve_candidate → reload | WIRED (w46 path) | Inspector.tsx:1399-1430; orchestrator.py:1349-1416,510-527,1419-1426 | parentTakeId = last approved candidate's takeId (orchestrator.py:510,518). |
| 16 | batch.activeTakeId | activate → approve_candidate (orchestrator.py:600) → reload | WIRED | orchestrator.py:600 | |
| 17 | Re-take drawer registry (sourceTakeId, activeTakeId in data/timeline_retakes/{project}.json) | Drawer ensureBaseline/addAlternate/setActive (RetakeDrawer.tsx:61-91,173-251) → /api/timeline-retakes/* → JSON file | BROKEN (disconnected parallel system) | RetakeDrawer.tsx:61-91,173-251; api.ts:4824-4874; timeline_retakes/store.py:78-249; router.py:41-92 | Only router+tests touch this store (grep: zero other production callers). 'Replace Current Take' never updates batch.approvedClip or the timeline. §2.6. |
| 18 | batch.references[timelineGenerationLineage] (provenance) | completion._stash_generation_lineage (completion.py:46-111) → persisted → reload | WIRED (persistence); UI does not surface it | completion.py:46-111 | No UI component reads lineage (tests only). |
| 19 | executionSnapshots[...] (immutable) | create_execution_snapshot (orchestrator.py:96-143) → master → snapshot GET (router.py:323-328) → reload | WIRED | orchestrator.py:96-143,221-223; store.py:147-151 | Immutability asserted at completion (orchestrator.py:490-491). |
| 20 | batch.lora | LoRA selector (Inspector.tsx:406-448) → PATCH lora (orchestrator.py:710-711) → providerOptions.lora (request_builder.py:191) → ltx_local.py:118 → reload | WIRED | Inspector.tsx:433-448; orchestrator.py:710-711; request_builder.py:191; ltx_local.py:118 | Scene-level selector writes every batch (coarse default). |
| 21 | master.mode | Header/panel mode buttons → set_mode (service.py:242-252) → reload | WIRED | service.py:242-252; EditorShell.tsx:846-863; MasterPanel.tsx:80-98 | |
| 22 | continuityPolicy + continuityBridges[] | Inspector Extend & Continuity (Inspector.tsx:835-862) → set_continuity_policy (orchestrator.py:1328-1346) → bridge → request (request_builder.py:133-155) → reload | WIRED | Inspector.tsx:835-862; orchestrator.py:1328-1346; request_builder.py:133-155 | |
| 23 | batch.repairRanges[] + inpaint mask metadata | Inpaint workspace (InpaintWorkspace.tsx:400-479) → PATCH repairRanges (orchestrator.py:724-731) → reload | PARTIAL/BROKEN at execution | InpaintWorkspace.tsx:400-509; orchestrator.py:724-731 | Mask strokes + prompt persist in repairRanges[].metadata but NO generation code reads them (grep generation/ for repairRanges|inpaint = zero). 'Generate Candidates' just re-runs generate-batch (InpaintWorkspace.tsx:496-509). Preview: no endpoint (InpaintWorkspace.tsx:486-488). |
| 24 | batch.status lifecycle | generate/stage/submit/watcher → status transitions → reload | WIRED | orchestrator.py:419,533,599,749; watcher.py:166 | TERMINAL_STATUS_GUARD (watcher.py:156-165). |
| 25 | scene.engine (Scene Generator select) | Inspector.tsx:766-775 → updateScene → scenes.engine → reload | WIRED to scene; NOT propagated to batches | Inspector.tsx:766-775 | master.sceneGeneratorId is never written (only read: service.py:102; orchestrator.py:1255,1340,1369,1490). New batches default generatorId=None → GENERATOR_REQUIRED (orchestrator.py:246-252). |
| 26 | scene.aspect_ratio → request.aspectRatio/resolution | Scene Picture Shape (EditorShell.tsx:781-799) → scenes.aspect_ratio → request_builder.py:159,187 → providers | WIRED | EditorShell.tsx:781-799; request_builder.py:159,187; seedance_api.py:100 | |
| 27 | scene.prompt (Scene Prompt) | Inspector textarea (Inspector.tsx:725-739) → updateScene → scenes.prompt → reload | WIRED to scene; NOT propagated to batches | Inspector.tsx:725-739; migration.py:115-118,231-234 | Scene prompt edits never update batch.promptSegments (migration/fallback only). |
| 28 | draftMode / draftPathway | Batch Draft checkbox (Inspector.tsx:1235-1245) → UI state → Generate Draft (Inspector.tsx:1271-1294) → request draftMode (request_builder.py:160-163,199) → resolution (request_builder.py:41-47) | WIRED | Inspector.tsx:1235-1294; request_builder.py:160-163,199; seedance_api.py:96-99 | Per-generation UI state, not persisted (by design). |
| 29 | batch.speechWindows | apply_compiled_speech (speech_compile.py:219-239) → persisted → reload | BACKEND-ONLY / STALE | speech_compile.py:219-239; orchestrator.py:63-65 | No adapter or UI consumes it; adapters get plain request.prompt (minimax_h3_local.py:93-99). Dialogue cues come from legacy prompt_segments text (speech_compile.py:171-215). |
| 30 | Timeline layout/settings (density, displayMode, zoom, drawers, snap, guidancePriority) | SettingsDrawer/WorkspaceStack → localStorage (workspaceLayout.ts) | WIRED (local only) | SettingsDrawer.tsx:58-65; WorkspaceStack.tsx:102-160 | guidancePriority also written to legacy director_json.guidance_priority (DirectorTracks.tsx:1203-1207) and snapshots (orchestrator.py:105-108). |
| 31 | dismissedFailureJobIds | Preview Monitor Dismiss (EditorShell.tsx:957-959) → dismiss-failure (service.py:48-80) → reload | WIRED (Job-row based only) | service.py:48-80; router.py:58-64 | Only works for failures with a Job row (§2.9). |
| 32 | Job → Library asset → clip binding | adapter.collect_result → import_output_to_project_library → Asset row → outputAssetIds → complete_batch_candidate (orchestrator.py:470-567) → approvedClip → video_clips (completion.py:306-317) | WIRED | minimax_h3_local.py:220-291; minimax_h3_i2v_local.py:238-323; seedance_api.py:168-185; completion.py:114-330 | |

## 2. Chain traces for the 11 requested items

### 2.1 Clip placement (UI clip → POST/PUT → persisted JSON → reload → UI state)

Three clip models coexist:
- Legacy clips (image_clips, video_clips, audio_clips, sfx_clips, camera_clips, prompt_segments, lipsync.tracks) live in scenes.director_json under the DirectorTimeline schema. UI edits: DirectorTracks.tsx:1744-1811, 1917-1960, 2133-2263, 2265-2347. Persist: putDirector → routers/api.py:934-952 → dumps_director_timeline_preserving_embedded (director_timeline.py:292) merges over the blob so timelineMaster survives. Reload: getDirector (routers/api.py:926-931). Client ids are Math.random() strings (DirectorTracks.tsx:147-149; EditorShell.tsx:572,669) — persisted verbatim so they reload, but not collision-safe UUIDs.
- Batch-owned clips (batch.visualClips/audioClips/sfxClips/cameraInstructions): created via directorTimelineAddClipToBatch (DirectorTracks.tsx:881-888) → orchestrator.add_clip_to_batch (orchestrator.py:791-850) → BatchClip.model_validate keeps client id or generates clip_ (orchestrator.py:813-817) → persisted in timelineMaster.batchBlocks[].visualClips. Reload via master GET (store.py:81-106). **Never rendered on any track** (VISUAL lane shows legacy clips); used only by resolveTimelineAtTime preview (resolveTimelineAtTime.ts:83-97).
- Approved placement clips: bbclip_{batch.id} in video_clips (completion.py:306-317), created on approve, idempotent upsert, sequential start=cursor in batch order (completion.py:296-317).

Verdict: **PARTIAL** — ids/duration/start/type persist and reload in all three, but the visible lane (legacy) is a different store from generation input (batch), and batch-owned clips have no visual track.

### 2.2 Timed Prompt chain

- Visible TIMED PROMPT lane edits legacy prompt_segments (DirectorTracks.tsx:1901-1962, addPromptSegment 1049-1061) → putDirector → director_json.prompt_segments → reload (certified by timeline-timed-prompt-track.spec.ts:69-199).
- Generation input = batch.promptSegments[].text joined (request_builder.py:69-70). Batch segments are written by the Batch Inspector Prompt textarea (Inspector.tsx:1159-1170 via persistBatchPrompt 640-662 → PATCH → orchestrator.py:714-717) or by one-time migration (migration.py:95-118).
- userDirection / productionPrompt / dialogue: declared (contracts.py:125-127; contracts.ts:81-83) but no UI field writes them and no generator code reads them (request_builder.py:69-70; speech_compile.py:172 read only .text). STALE/BACKEND-ONLY.
- Dialogue: speech_compile extracts '@Token says "..."' cues from **legacy** prompt_segments (speech_compile.py:90-126,171-215) into batch.speechWindows (speech_compile.py:238); no adapter consumes speechWindows (adapters receive plain prompt: minimax_h3_local.py:93-99). Lip Sync clips gate generation via LIPSYNC_SPEAKER_REQUIRED (speech_compile.py:44-61; orchestrator.py:311-318) but their audio is not sent to adapters.

Verdict: **PARTIAL/BROKEN** — the visible prompt lane is disconnected from generation input; distinct userDirection/productionPrompt/dialogue are dead.

### 2.3 Source image binding (I2V)

Batch Start Image select (Inspector.tsx:1171-1204) → PATCH sourceAnchors → orchestrator.py:718-721 → request_builder picks start_image = first non-'end'-labelled image anchor (request_builder.py:76-88), mode=image_to_video when caps support I2V (request_builder.py:116-121) → minimax_h3_i2v_local maps to H3ReferenceAssignment(role='start') (minimax_h3_i2v_local.py:97-103) → Comfy LoadImage→first_frame verified fail-closed (minimax_h3_i2v_local.py:129-133,326-353). No implicit fallback: no start image + no I2V caps → T2V (request_builder.py:122-128); validation refuses I2V without startImageAssetId (adapter.py:77-78; minimax_h3_i2v_local.py:72-73); T2V-only profile refuses I2V (minimax_h3_local.py:75-76).

Verdict: **WIRED**.

### 2.4 Batch semantics / scoping

Creation: toolbar/panel/lane → directorTimelineAddBatch (api.ts:3627-3639) → service.add_batch (service.py:83-134) → stable bb_ id + order + configFingerprint. Scoping: submit_batch_generation loads only the target batch (orchestrator.py:242-244); generate_scene iterates eligible batches and stages sequential snapshots (orchestrator.py:1294-1314); submit_next_queued_batch submits lowest-order Queued only and refuses while another batch is Generating (orchestrator.py:1175-1179); approval auto-advances the chain (orchestrator.py:616). Result binding: apply_shared_completion scoped by batch_id + execution_snapshot_id with duplicate-candidate guard (completion.py:169-177); placement per batch in order (completion.py:297-317). Cross-batch leakage prevented by BATCH_OWNED_CLIPS (orchestrator.py:736-742,791-850); certified by two-batch spec:255-266.

Verdict: **WIRED**.

### 2.5 Generation result → asset → clip → Library + provenance

Adapter collect_result imports to Library (minimax_h3_local.py:238-244; minimax_h3_i2v_local.py:253-268; seedance_api.py:168-179) → result.outputAssetIds → watcher → apply_shared_completion (completion.py:114-267) → complete_batch_candidate creates CandidateVersion + generatedDuration + CandidateReady (orchestrator.py:510-536) → auto-approve (completion.py:231-246) → approve_candidate sets approvedClip + places clip (orchestrator.py:594-613; completion.py:270-330). Provenance on batch.references[timelineGenerationLineage]: generatorId, snapshotId, job ids, startImage + sha256, comfyImageName, workflowId, videoReferenceAssetId, draftMode/draftPathway, aspectRatio, resolution, quality (completion.py:76-99). Retake lineage rides candidateVersions (parentTakeId) + activeTakeId. LoRA/generator in snapshots + request.

Verdict: **WIRED** for persistence; provenance not surfaced in any UI (tests only).

### 2.6 Retake

- W46 batch retake (Batch Inspector 'New take', Inspector.tsx:1399-1412) → directorTimelineRetakeBatch → orchestrator.retake_batch (orchestrator.py:1349-1416) → new submission w/ continuity memory → candidate with parentTakeId (orchestrator.py:510-518) → take buttons (Inspector.tsx:1413-1430) → activate-take → approve_candidate → activeTakeId + re-place (orchestrator.py:600-606). **WIRED end-to-end.**
- Re-take drawer (Master panel + shell): TimelineRetakeDrawer (RetakeDrawer.tsx) uses the OLD MiniMax H3 plan panel (MiniMaxH3PlanPanel.tsx → /api/minimax-h3/*) and the file-based timeline_retakes registry (store.py:78-249) via api.timelineRetakes.* (api.ts:4824-4874). Add-as-Alternate / Replace-Current-Take only write data/timeline_retakes/{project}.json — never touch batch.approvedClip/candidates/activeTakeId, never place a clip. Zero production readers of that JSON outside its router. Baseline prompt is a hardcoded 'glowing glass bottle' string (EditorShell.tsx:1011; MasterPanel.tsx:131).

Verdict: **WIRED (w46) + BROKEN (drawer)** — two visible retake UIs; the drawer is disconnected and cannot update the timeline.

### 2.7 Generator config (id, aspect ratio, LoRA, advanced)

- Generator id: batch select → PATCH → orchestrator.py:707-709 → snapshot/request (orchestrator.py:134,220; request_builder.py:62-66); capability-gated (orchestrator.py:258-267). WIRED.
- Aspect ratio: scene select (EditorShell.tsx:781-799) → scenes.aspect_ratio → request_builder.py:159 → resolution (request_builder.py:35-47) → providerOptions. WIRED.
- LoRA: selector writes every batch (Inspector.tsx:433-448) → PATCH lora (orchestrator.py:710-711) → providerOptions.lora (request_builder.py:191) → LTX params (ltx_local.py:118). WIRED.
- Advanced (camera, seed, stabilization, negative): persisted as legacy fields (Inspector.tsx:989-1135) but request_builder sends cameraMotion=None, seed=None (request_builder.py:188-189); only negativePrompt maps via migration (migration.py:104) and is sent when caps support it (request_builder.py:179). PARTIAL/BACKEND-ONLY for most advanced fields.

### 2.8 Audio / dialogue tracks

Legacy audio_clips/sfx_clips/lipsync.tracks persist + reload (routers/api.py:934-980). Lip Sync speaker gating blocks generation (speech_compile.py:44-61; orchestrator.py:311-318). batch.speechWindows compiled + persisted (speech_compile.py:219-239) but never consumed by adapters or UI. Audio does not reach any generator request. Verdict: **PARTIAL** (persists + gates, no generation/assembly influence; speechWindows STALE).

### 2.9 Error paths

Structured codes from orchestrator: GENERATOR_REQUIRED, GENERATOR_UNSUPPORTED_FOR_TIMELINE, GENERATOR_UNKNOWN, DURATION_EXCEEDS_GENERATOR, LIPSYNC_SPEAKER_REQUIRED, REQUEST_BUILD_FAILED, GENERATOR_MISMATCH, FALLBACK_NOT_AUTHORIZED, CAPABILITY_VALIDATION_FAILED, ADAPTER_SUBMIT_FAILED (orchestrator.py:246-389). Watcher marks batch Failed/Cancelled w/ provider code + advances chain (watcher.py:135-177), TERMINAL_STATUS_GUARD (watcher.py:156-165). Adapter honest errors: H3_LIBRARY_IMPORT_MISSING, H3_SILENT_FALLBACK, H3_I2V_DOWNGRADED_TO_T2V (minimax_h3_i2v_local.py:270-300), SEEDANCE_FAILED (seedance_api.py:188-191).

**Failure overlay is Job-row-based**: useGenerationState polls api.listJobs (PreviewComposer.tsx:108-138); failed/cancelled overlay keys off activeJob (PreviewComposer.tsx:241-252); dismiss-failure validates against the Job table (service.py:58-66). The MiniMax H3 local/i2v batch path creates **no Job row** (adapter → create_job_or_block writes disk jobs, minimax_h3/service.py:131-145; only the cert stub seeds Job rows, router.py:544-572). Only LTX creates a Job row w/ batchBlockId (ltx_local.py:141-161). Verdict: **PARTIAL/BROKEN** — a failed MiniMax batch shows only as a lane badge + batch inspector; no overlay, no render-queue entry, no Dismiss.

### 2.10 Idempotency

Backend stable ids: bb_ / clip_ / bbclip_{batch.id} (contracts.py:15-17,219; completion.py:306) with idempotent upsert (completion.py:307). Duplicate candidate guard keyed by (snapshotId, assetId) (completion.py:169-177); already-approved short-circuit (completion.py:152-167). No double-submit: Generating skipped (orchestrator.py:1290-1291); sequential chain idempotent (orchestrator.py:1175-1179); MiniMax _RUNNING_JOBS dedupe returns 'duplicate' (minimax_h3/service.py:173-183); baseline registration idempotent (timeline_retakes/store.py:101-104).

Client-generated clip ids are Math.random() strings (DirectorTracks.tsx:147-149; EditorShell.tsx:572,669) — not UUIDs. No client idempotency key on POST generate/clips (api.ts:3627-3704). Verdict: **PARTIAL** — server-side dedupe exists for completion; retry safety lacks client keys.

### 2.11 Reload / hydration

Survives reload: batchBlocks (all fields incl. prompts, anchors, clips, repairs, lora, references+lineage, fingerprint), approvedClip, candidateVersions + take lineage, activeTakeId, executionSnapshots, continuityPolicy/bridges, dismissedFailureJobIds, mode, legacy director_json (all lanes + lipsync + playhead), scene fields (prompt/aspect/engine/duration). Does NOT survive: draftMode checkbox (UI state), layout/settings (localStorage), in-flight watcher threads (daemon; after backend restart a stuck 'Generating' batch has no recovery path). Verdict: **WIRED** for persisted fields; watcher/restart resilience not covered.

## 3. Items that would block a two-batch live production (priority order)

1. [BROKEN] **Timed Prompt lane → generation disconnect** (§2.2). The primary visible prompt surface (TIMED PROMPT lane / legacy prompt_segments) does not feed the request; only the Batch Inspector's separate prompt does. A creator who types prompts on the lane and presses Generate gets the batch's (empty/migrated) prompt. Evidence: DirectorTracks.tsx:1049-1061/1901-1962 vs request_builder.py:69-70 vs orchestrator.py:714-717; migration.py:56-61.
2. [BROKEN] **Re-take drawer is a disconnected parallel system** (§2.6). Replace-Current-Take never updates batch.approvedClip or the timeline; active take lives in a file nobody reads. Two visible retake UIs with divergent behavior.
3. [PARTIAL/BROKEN] **Inpaint execution is a stub** (row 23). Mask strokes + prompt persist in repairRanges[].metadata but no generation code reads them; 'Generate Candidates' re-runs plain batch generation; Preview has no endpoint.
4. [PARTIAL/BROKEN] **MiniMax batch failures invisible to Job-based monitoring** (§2.9). No Job row → no failed overlay, no render-queue entry, no Dismiss. Failure visible only as a lane badge.
5. [PARTIAL] **Two divergent clip stores** (§2.1). Batch-owned visualClips never render on tracks; legacy VISUAL lane edits don't reach generation.
6. [STALE] **userDirection / productionPrompt / dialogue** (§2.2). Declared in both contracts; never written by UI, never read by generation. Mission Part 14 prompt lineage not delivered.
7. [STALE] **batch.speechWindows** (§2.8). Compiled + persisted; consumed by nothing.
8. [PARTIAL] **Advanced generator settings (seed/camera/negative)** not wired to requests (§2.7); camera clips, seed, stabilization never reach adapters (request_builder.py:188-189).
9. [PARTIAL] **scene.engine / scene.prompt / sceneGeneratorId** do not propagate to batches (rows 25/27). New batches default to no generator → GENERATOR_REQUIRED on Generate until per-batch selection.
10. [PARTIAL] **Idempotency lacks client request keys** (§2.10); client clip ids are non-UUID Math.random() strings.

## 4. Not implemented (found during audit)

- Any UI display of timelineGenerationLineage provenance (persisted, unread by UI).
- Any consumer of batch.speechWindows.
- Sync of legacy prompt_segments / image_clips / scene.prompt into W46 batch state after initial migration.
- Inpaint mask execution path (metadata only) and inpaint preview endpoint.
- Any write path for master.sceneGeneratorId (reads only).
- UI to set master.orchestratorMode (defaults sequential_continuity; never changed by any UI).
- Kling adapter is an in-memory ledger with no real provider call (kling_api.py:64-92,113-137) — cannot produce real media in production; Seedance is live only via fal.ai credentials (seedance_api.py:78-191).
