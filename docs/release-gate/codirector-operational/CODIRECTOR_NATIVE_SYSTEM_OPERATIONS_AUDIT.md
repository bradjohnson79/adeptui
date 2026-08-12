# Co-Director Native System Operations Audit

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c4/c5/c8
**Governing status:** This is the authoritative native-system coverage audit for the milestone (Build Law 30). Supersedes no prior document; supersedes any in-flight working notes once referenced from the milestone report.
**Audit mode:** READ-ONLY. No files were modified and no non-readonly commands were run during the audit. All findings are sourced from the closed tool registry, handler modules, native services, and the test/certification tree as they existed on 2026-08-07.

**Primary source of truth:** `data/tmp/codirector-audit-sources/native-systems-report.md` (native system coverage map + test/certification infrastructure).
**Cross-system synthesis sources:** `data/tmp/codirector-audit-sources/tool-registry-report.md`, `state-isolation-report.md`, `routing-report.md`.

---

## 1. Executive Summary

The Co-Director tool registry (`studio-api/app/codirector/tools/registry.py`) is a **closed registry** that binds ~250 tools across 28 handler modules. Every mutating tool routes through `ProposalService` (preview -> human approve -> apply -> receipt); the model can never apply directly. The registry is validated at import time (`registry.py:1180` `_validate_bindings`, `registry.py:1226` `require_kind`), so any declared tool without a handler fails fast at startup.

Of the **12 native systems** enumerated for this milestone, **11 have Co-Director tool coverage** and operate against their **current** native contracts. The single fully-uncovered system is **MAGI** (`studio-api/app/magi/`): no `magi_*` tool is registered, and the only mention of MAGI in Co-Director handlers is as a continuity workspace target string in `continuity_w5.py:121`. Per the milestone decision recorded in this audit, MAGI is documented as **not-operational via Co-Director** and the gate is **N/A** — no fictional MAGI tools may be exposed to creators.

The strongest system is **Timeline**, which correctly uses the current `director_timeline_w46` batch-owned, revision-guarded contract (`store.save_master(..., bump_revision=True)`). The most material drift risk is the **legacy `codirector/m29/timeline/service.py`** path, which still persists to `scene.director_json` (`m29/timeline/service.py:229`) and is not used by any Co-Director tool but coexists in the tree.

The test/certification infrastructure has three structural gaps:

1. **No unified operational regression suite** that certifies every native system in a single READ -> WRITE -> PERSIST -> VERIFY -> UI-SYNC loop. Existing suites are per-system or per-handler.
2. **No independent operational verifier** for Co-Director operational integrity across all 12 systems; the only cert stub (`director_timeline_w46/generation/adapters/stub_cert.py`, `ADEPT_TIMELINE_CERT_STUB`) is Timeline-specific.
3. **Mock provider fixed scenarios** (`providers/mock.py`) and on/off toggles (`ADEPT_MOCK_IMAGEGEN`, `ADEPT_CODIRECTOR_PROVIDER=mock`) cover a fixed scenario set; voice and image generation boundaries have no deterministic cert-stub-style lifecycle controller comparable to Timeline's.

Repairs are mapped to milestone phases **c4** (native system contract closure + MAGI documentation), **c5** (cross-system workflow + UI synchronization — see companion audit), and **c8** (test/certification infrastructure unification).

---

## 2. Native System Coverage Matrix

For each of the 12 native systems: tool coverage (yes/no), operations exposed (read / write), the contract path used (current vs. legacy), and a READ / WRITE / PERSIST / VERIFY / UI-SYNC capability assessment. Capability legend: **STRONG** = full lifecycle wired through `ProposalService` with revision-guarded persistence and a UI sync signal; **PARTIAL** = persistence is real but at least one of VERIFY/UI-SYNC is weak or absent; **GAP** = no Co-Director tool path exists or a critical defect prevents the tool from ever succeeding.

### 2.1 Timeline

- **Tools exist:** YES — `director_timeline_tools` handler (29 tools).
- **Operations (R):** `timeline.get_workspace`, `get_playhead`, `get_settings`, `get_guidance_priority`, `inspect_batches`, `preflight`, `explain_asset_reference_name`, `focus_ui`, `inspect_layout`, `inspect_lipsync`, `validate_lipsync`.
- **Operations (W):** `propose_add_batch`, `propose_add_image_clip`, `propose_add_prompt_segment`, `propose_add_camera`, `propose_update_camera`, `propose_layout_preset`, `propose_viewer_fullscreen`, `propose_layout_reset`, `propose_zoom`, `propose_add_lipsync_track/clip`, `propose_bind_lipsync_clip`, `propose_open_inpaint`, `propose_create_inpaint_mask`, `propose_execute_inpaint`, `propose_approve_inpaint`, `propose_restore_inpaint`, `propose_generate_scene`, `propose_repair_range`, `propose_cancel`, `propose_retake`, `attach_optional_reference`, plus non-propose writes `set_playhead`, `update_settings`, `set_guidance_priority`, `remove_item`, `restore_removed_item`.
- **Contract path:** **CURRENT** — `director_timeline_w46`. Handler imports `from ....director_timeline_w46 import orchestrator, service, store` and uses `store.save_master(..., bump_revision=True)` (batch-owned state, revision-guarded). Stale-proposal detection via `timelineRevision` check.
- **READ:** STRONG. **WRITE:** STRONG (all writes go through `ProposalService`). **PERSIST:** STRONG (revision-guarded `save_master`). **VERIFY:** PARTIAL — `_layout_state` reads current workspace and validates/clamps before proposing; no post-apply state-diff verification at the framework level (see §6). **UI-SYNC:** STRONG — `tool_completed` events with `result._uiFocus` / `result.uiFocus` drive `adept-timeline-focus` (`CoDirectorSession.tsx:1757-1761`).
- **Gaps:** Legacy `codirector/m29/timeline/service.py` coexists and persists to `scene.director_json` (`m29/timeline/service.py:229`). No `timeline.propose_resume` (resume is via `propose_retake`/orchestrator). Dead/unreachable code block at `director_timeline_tools.py:542-557` (leftover from a refactor; references undefined variables `project_id`, `scene_id`, `master`, `batches`, `empty_tracks`).

### 2.2 Scene / Project Editor

- **Tools exist:** YES — `scenes` handler.
- **Operations (R):** `list_scenes`, `get_scene`, `get_active_scene`, `scene.search`, `scene.list_characters`, `scene.list_assets`.
- **Operations (W):** `create_scene`, `update_scene_title`, `set_scene_prompt`.
- **Contract path:** YES — direct scene CRUD via native scene service. `_require_scene` -> `SceneService.get(ctx.db, ctx.project_id, scene_id)` enforces `scene.project_id != project_id` (`scene_service.py:118`).
- **READ:** STRONG. **WRITE:** STRONG. **PERSIST:** STRONG. **VERIFY:** STRONG (handler re-reads authoritative scene state). **UI-SYNC:** PARTIAL — scene mutations surface only via the conversation transcript + `adept:codirector-plan-workspace-refresh` (`CoDirectorSession.tsx:1892-1896`); no dedicated scene-list invalidation event.
- **Gaps:** No scene reorder/delete tool; no scene-merge tool.

### 2.3 Production Bible (`codirector/bible/`)

- **Tools exist:** YES — `bible_read` + `bible_domain` handlers.
- **Operations (R):** `get_current_bible_version`, `get_bible_entity`, `list_bible_entities`, `get_relevant_bible_context`, `get_production_bible_summary`, `get_scene_bible_context`, `get_character_bible_context`, `get_location_bible_context`, `list_canon_records`, `list_continuity_warnings`, `get_generation_reference_package`, `production_bible.search`.
- **Operations (W):** `record_director_decision`, `propose_character_update`, `propose_canon_record`, `propose_canon_supersession`, `propose_continuity_update`, `propose_reference_link`, `propose_production_decision`, `propose_visual_language_update`.
- **Contract path:** YES — writes route through `ProposalService` (`bible/proposals.py`); reads via `ProjectContextService`. Model never mutates Bible directly.
- **READ:** STRONG. **WRITE:** **CRITICAL DEFECT** — see §3. **PERSIST:** STRONG (real Bible version rows created). **VERIFY:** PARTIAL — `_require_bible` loads Bible + current version before mutating, but `propose_character_update` reports `bibleVersionNumber` success while persisting empty/malformed `CharacterData` (`bible_domain.py:97`). **UI-SYNC:** PARTIAL — Bible mutations surface via the proposal-approval flow (`CoDirectorSession.tsx:2516` `approveProposal`) and the generic `adept:codirector-plan-workspace-refresh`; no Bible-specific refresh event.
- **Gaps:** Schema/handler mismatch on six `bible_domain` tools (see §3).

### 2.4 Character Creator (character_profiles)

- **Tools exist:** YES — `character_identity` + `character_creator` handlers.
- **Operations (R):** `list_character_profiles`, `inspect_character_profile`, `inspect_character_coverage`, `inspect_character_voice`, `character_creator.get_motion_profile`, `get_performance_bible`, `get_relationship_graph`, `get_prompt_package`, `get_visual_sheet_status`, `get_voice_status`, `get_voice_profile`, `get_voice_candidates`, `compare_voice_candidates`, `get_pronunciation_profile`, `get_reaction_coverage`, `open_voice_creator`, `inspect_readiness`, `build_reference_plan/expression_plan/pose_plan/voice_plan/wardrobe_plan/continuity_plan`, `audit_profile`.
- **Operations (W):** `create_draft_character_profile`, `character_creator.create_from_brief`, `create_from_script`, `propose_traits`, `propose_relationships`, `propose_visual_sheet`, `advance_visual_sheet`, `preview_voice_design`, `generate_voice_candidates`, `refine_voice_candidate`, `approve_voice_candidate`, `validate_clone_source`, `generate_voice_clone`, `test_pronunciation`, `generate_reactions`, `submit_for_review`.
- **Contract path:** YES — uses native `character_profiles` service.
- **READ:** STRONG. **WRITE:** **CRITICAL DEFECT** — `character_creator.propose_traits` (`character_creator.py:307`) and `character_creator.propose_relationships` (`character_creator.py:350`) **always raise `ValueError`** because `traits`/`relationships` are stripped by the sanitizer (undeclared in `ToolDefinition.parameters`). The model can never successfully call these tools. **PERSIST:** STRONG for tools that do not hit the schema defect. **VERIFY:** PARTIAL — voice-clone generation is a chargeable/GPU boundary with no dedicated cert stub. **UI-SYNC:** STRONG — `result.uiAction === "open_voice_creator"` drives `adept:open-character-voice` (`CoDirectorSession.tsx:1725-1732`).
- **Gaps:** Voice-clone generation is a chargeable/GPU boundary — needs a stub for cert (see §6).

### 2.5 Voice Studio (voice_profiles, voice_performance)

- **Tools exist:** YES — `voice_environment`, `voice_performance`, `voice_m410` handlers (~50 tools).
- **Operations (R):** `voice.inspect_studio/character/identity/performance/dialogue/takes`, `voice_performance.get_status/get_character_readiness/parse_markup/preview_plan/validate_plan/get_provider_translation/get_pronunciation_issues/get_reaction_coverage/open_workspace`, `voice.performance_context/analyze_dialogue`, `voice_environment.inspect_scene/location/spatial_map/performance/profile/list_profiles/list_renders/inspect_runtime/inspect_timeline_link/inspect_lipsync_link/preview_plan`.
- **Operations (W):** `voice_performance.generate_segments/retry_segment/refine_segment/compare_takes/approve_take/assemble_dialogue/place_on_timeline`, `voice.apply_performance_plan`, `voice.select_character`, `voice.create_character_handoff/create_identity_plan`, `voice_environment.create_profile/update_profile/apply_codirector_recommendation/create_preview/render/approve/create_alternate/apply_to_scene/prepare_timeline/prepare_lipsync/open_audio_studio/request_repair`, `voice.approve_take`, `voice.replace_timeline_dialogue`.
- **Contract path:** YES — native voice services.
- **READ:** STRONG. **WRITE:** STRONG at the tool layer. **PERSIST:** STRONG. **VERIFY:** PARTIAL — `voice_performance.generate_segments` (`service.py:204`) and `retry_segment` (`service.py:345`) load `PerformancePlanRow` by `plan_id`/`segment_id` only and never compare `row.project_id` to the caller's `ctx.project_id` (RISK 1 in `state-isolation-report.md`). **UI-SYNC:** STRONG — `result.uiAction === "open_voice_performance"` / `"open_audio_studio"` drive `adept:open-character-voice` / `adept:open-audio-studio` (`CoDirectorSession.tsx:1725-1748`).
- **Gaps:** Voice render/generation is a real provider boundary; no dedicated cert stub for voice generation (only Timeline has `stub_cert`). Cross-project leak risk on stale `plan_id`/`segment_id`.

### 2.6 Image Planning / Image Generation

- **Tools exist:** YES — `image_pipeline_tools` + `media_execution` + `generation_tools` handlers.
- **Operations (R):** `image_pipeline.analyze_request/get_readiness/get_job/preview_posecraft`, `get_generation_tools_catalog`.
- **Operations (W):** `image_pipeline.prepare_plan/prepare_creative_direction/select_profile/assign_reference/load_spatial_map/prepare_posecraft/generate_candidates/evaluate_candidates/recommend_candidate/select_candidate/prepare_repair/apply_repair/master/approve/cancel`, `propose_image_generate`, `propose_image_edit`, `propose_image_upscale`, `propose_background_remove`, `propose_chroma_key`, `propose_portrait_skin`, `propose_brand_generate`.
- **Contract path:** YES — uses native image pipeline + media execution.
- **READ:** STRONG. **WRITE:** STRONG. **PERSIST:** STRONG. **VERIFY:** PARTIAL — image generation is a real GPU/provider boundary. `ADEPT_MOCK_IMAGEGEN` exists for imagegen mocking (per `production-executive-m27.spec.ts` notes), but no cert-stub-style deterministic lifecycle controller like Timeline's. **UI-SYNC:** PARTIAL — no dedicated image-result refresh event; results surface via the conversation transcript and the proposal-approval flow.
- **Gaps:** No deterministic cert stub for the image generation lifecycle.

### 2.7 MAGI Editor (`studio-web/src/magiSequence/`, `studio-api/app/magi/`)

- **Tools exist:** **NO** — no `magi_*` tool in the registry.
- **Operations (R/W):** None via Co-Director.
- **Contract path:** **N/A** — Co-Director cannot operate MAGI.
- **READ/WRITE/PERSIST/VERIFY/UI-SYNC:** **GAP** across all five.
- **Native API exists:** `studio-api/app/magi/api.py`, `sequence/store.py`, `composition/service.py`, `readiness.py`, `production_gate.py`. The only mention of `magi` in Co-Director handlers is as a target string in `continuity_w5.py:121` (`target not in ("continuity","identityregistry","timeline","magi","bible")`) — i.e., the continuity workspace can *open* MAGI, but no read/write tools are exposed.
- **Gaps:** **Major gap.** No Co-Director tool to read MAGI sequences, propose edits, compose, or drive MAGI generation. Creators must leave Co-Director for MAGI work.

### 2.8 PoseCraft

- **Tools exist:** YES — `posecraft` handler.
- **Operations (R):** `posecraft.get_status`, `open_scene`, `export_reference`, `inspect_scene`, `list_scenes`.
- **Operations (W):** `posecraft.create_scene`, `add_figure`, `rename_object`, `set_figure_role`, `map_character`, `set_figure_color`, `apply_pose`, `update_figure_transform`, `set_eyeline`, `set_camera`, `save_scene`, `send_to_image_pipeline`, `send_to_storyboard`.
- **Contract path:** YES — native PoseCraft service.
- **READ:** STRONG. **WRITE:** PARTIAL — `posecraft.apply_apply_pose` (`posecraft.py:340-346`) re-persists the scene unchanged (no actual pose mutation — comment says pose is applied client-side by Babylon viewport); `posecraft.apply_set_eyeline` (`posecraft.py:381-388`) appends a prose annotation to `scene.notes` rather than structured authoritative state. Both are honest (documented in comments) but technically report `scene` modified without a real state change. **PERSIST:** STRONG. **VERIFY:** PARTIAL — see WRITE. **UI-SYNC:** PARTIAL — no dedicated PoseCraft refresh event; results surface via the proposal-approval flow.
- **Gaps:** `ToolPreview` field violations on 13 posecraft preview handlers (`posecraft.py:201,217,246,276,298,317,336,352,377,394,418,433,454`) — `affectedResources=("project",)` is silently dropped because `ToolPreview` (`definitions.py:107-114`) does not declare it. Previews still render (summary preserved) but the project-level impact intent is dead.

### 2.9 Assets / Media Library

- **Tools exist:** YES — `library` handler.
- **Operations (R):** `get_library_folder_map`, `get_library_context_summary`, `resolve_library_location`, `search_library_assets`, `plan_library_storage`, `link_bible_entity_folder`, `asset.get/list/list_by_character`.
- **Operations (W):** `propose_asset_library_assignment`.
- **Contract path:** YES — native `project_library` service.
- **READ:** STRONG. **WRITE:** PARTIAL — `propose_asset_library_assignment` reads `folderId` (`library.py:144`) which is undeclared in `ToolDefinition.parameters`, so `folderId` is always `None` (dead code path in handler). **PERSIST:** STRONG for the assignment that does occur. **VERIFY:** PARTIAL — see WRITE. **UI-SYNC:** PARTIAL — no dedicated library refresh event.
- **Gaps:** No tool to *create* library assets via Co-Director (upload stays manual); only assignment/linking. `library.py:121,127` `preview_propose_asset_library_assignment` passes `title=` and `diff={...}` fields not declared on `ToolPreview` — the diff block (containing `assetId`, `targetPath`, `systemKey`, `override`) is silently discarded, so the human reviewer sees only a summary line without structured change details. `asset.list` / `asset.search` bind the identical handler (`registry.py:236-237`) — true duplicate, not just an alias.

### 2.10 Visual References

- **Tools exist:** YES — `scene_references_w6p` + `timeline_references` handlers.
- **Operations (R):** `references.list/get/get_inherited/get_readiness/preview_selection/preflight/open`, `get_timeline_image`, `list_timeline_images`, `get_reference_set`, `list_reference_bindings`, `build_generation_reference_package`, `suggest_reference_bindings`.
- **Operations (W):** `references.attach/update/remove/copy`, `create_reference_set_proposal`, `propose_add_reference_binding`, `propose_remove_reference_binding`, `propose_update_reference_binding`, `propose_apply_reference_preset`.
- **Contract path:** YES — native reference services.
- **READ:** STRONG. **WRITE:** PARTIAL — `references.attach` (`scene_references_w6p.py:110-111`) reads `usageModes` and `referenceRoles` which are undeclared in `ToolDefinition.parameters`; they default to `["informational"]` / `[]` and the model cannot override. **PERSIST:** STRONG. **VERIFY:** STRONG. **UI-SYNC:** PARTIAL — no dedicated reference refresh event.
- **Gaps:** Schema/handler mismatch on `references.attach` (see §3).

### 2.11 Render Queue / Generation State (Jobs)

- **Tools exist:** YES — `wave3_reads` + `media_execution` + `system_status` handlers.
- **Operations (R):** `job.list`, `job.get`, `system.status_check/status_summary/status_check_component/status_list_blockers/status_list_warnings/status_recovery_options/deep_diagnostic`, `get_cloud_render_status`, `get_comfyui_health`, `get_provider_health`, `get_source_manager_status`.
- **Operations (W):** `job.cancel`, `job.retry`, `propose_timeline_render`, `propose_batch_timeline`, `propose_shot_generate`, `propose_scene_generate`, `propose_three_frame_generate`, `propose_video_generate`, `propose_video_extend`, `propose_video_upscale`, `propose_lipsync`, `propose_voice_generate`, `propose_subtitle_generate`, `editor.place_asset`.
- **Contract path:** YES — native job/queue services.
- **READ:** STRONG. **WRITE:** STRONG. **PERSIST:** STRONG. **VERIFY:** PARTIAL — job creation tools are `propose_*` wrappers; no direct queue inspection tool that returns queue depth/position (only `job.list/get`). **UI-SYNC:** PARTIAL — no dedicated queue-refresh event; the creator must poll `job.list`.
- **Gaps:** No queue-depth/position inspection tool.

### 2.12 Continuity / Production Intelligence

- **Tools exist:** YES — `continuity_w5` + `bible_domain` + `prompt_intelligence` handlers.
- **Operations (R):** `continuity.search_identities`, `get_identity`, `get_identity_version`, `list_variants`, `get_reference_readiness`, `preview_packet`, `preflight`, `get_evaluation`, `list_issues`, `open_workspace`, `list_continuity_warnings`, `continuity.list_findings`, `continuity.get_finding`.
- **Operations (W):** `continuity.propose_correction`.
- **Contract path:** YES — native continuity service.
- **READ:** STRONG. **WRITE:** PARTIAL — no tool to *resolve* a continuity finding directly (only `propose_correction`). **PERSIST:** STRONG. **VERIFY:** STRONG. **UI-SYNC:** PARTIAL — no dedicated continuity refresh event.
- **Gaps:** No direct resolution tool; only propose-correction.

### 2.13 Coverage Matrix Summary

| # | Native System | Tools | Current contract | READ | WRITE | PERSIST | VERIFY | UI-SYNC |
|---|---|---|---|---|---|---|---|---|
| 1 | Timeline | YES (29) | YES (w46) | STRONG | STRONG | STRONG | PARTIAL | STRONG |
| 2 | Scene/Project Editor | YES | YES | STRONG | STRONG | STRONG | STRONG | PARTIAL |
| 3 | Production Bible | YES | YES | STRONG | CRITICAL DEFECT | STRONG | PARTIAL | PARTIAL |
| 4 | Character Creator | YES | YES | STRONG | CRITICAL DEFECT | STRONG | PARTIAL | STRONG |
| 5 | Voice Studio | YES (~50) | YES | STRONG | STRONG | STRONG | PARTIAL | STRONG |
| 6 | Image Planning/Gen | YES | YES | STRONG | STRONG | STRONG | PARTIAL | PARTIAL |
| 7 | MAGI Editor | **NO** | N/A | GAP | GAP | GAP | GAP | GAP |
| 8 | PoseCraft | YES | YES | STRONG | PARTIAL | STRONG | PARTIAL | PARTIAL |
| 9 | Assets/Media Library | YES | YES | STRONG | PARTIAL | STRONG | PARTIAL | PARTIAL |
| 10 | Visual References | YES | YES | STRONG | PARTIAL | STRONG | STRONG | PARTIAL |
| 11 | Render Queue/Jobs | YES | YES | STRONG | STRONG | STRONG | PARTIAL | PARTIAL |
| 12 | Continuity/Intel | YES | YES | STRONG | PARTIAL | STRONG | STRONG | PARTIAL |

**Summary:** 11 of 12 native systems have Co-Director tool coverage. MAGI is the single fully-uncovered system. Timeline is the only system with STRONG across READ/WRITE/PERSIST/UI-SYNC (VERIFY is PARTIAL because no framework-level post-apply state-diff verification exists). Two systems (Production Bible, Character Creator) have CRITICAL DEFECT writes that prevent specific tools from ever succeeding.

---

## 3. Critical Write Defects (Schema/Handler Mismatch)

`sanitize_arguments` (`sanitize.py:90-110`) silently drops any argument key not declared in the tool's `ToolDefinition.parameters`. The following handlers read keys that are **not declared**, so those keys are always `None`/empty/missing at apply time. This means the model cannot pass these values through the tool layer regardless of what it emits. Root cause for every entry: the `ToolDefinition.parameters` tuple was never updated to match the handler's actual argument contract — the schema is stale (missing parameters) or the handler reads dead fields.

| Tool | Handler file:line | Undeclared keys read | Schema declares | Impact (root cause) |
|---|---|---|---|---|
| `propose_character_update` | `bible_domain.py:97,105` | `data` | `stableId`, `entityKey`, `displayName` | Silently persists empty `CharacterData` when creating a new character entity. `CharacterData.model_validate({})` -> empty object. Reports success (`bibleVersionNumber`) with malformed data. Violates Build Law #8 (no silent behavior) and Law #11 (failure recovery). |
| `propose_canon_record` | `bible_domain.py:141-142` | `entityStableId`, `sceneId` | `claim` only | Canon records lose entity/scene binding — always `None`. |
| `propose_canon_supersession` | `bible_domain.py:162` | `entityStableId` | `claim`, `supersedesStableId` | Supersession loses entity binding. |
| `propose_continuity_update` | `bible_domain.py:189-193` | `entityStableId`, `sceneId`, `expectedValue`, `actualValue`, `resolved` | `aspect` only | Continuity state loses all detail except `aspect`. `expectedValue`/`actualValue` always `""`, `resolved` always `False`. |
| `propose_production_decision` | `bible_domain.py:242-244` | `rationale`, `entityStableId`, `sceneId` | `decision` only | Decision loses rationale and entity/scene binding. |
| `propose_reference_link` | `bible_domain.py:215-216` | `purpose`, `primary` | `assetId`, `targetStableId` | `purpose` defaults to `"identity"`, `primary` to `False` — model cannot override. |
| `propose_visual_language_update` | `bible_domain.py:264` | `data` | `description` only | `data` always `None` -> falls back to `{"description": args.get("description","")}`. Works but `data` path is dead code. |
| `character_creator.propose_traits` | `character_creator.py:305-308` | `traits`, `provenance` | `characterId` only | **Tool always fails**: `traits` always `None` -> `raise ValueError("traits array is required")` (`character_creator.py:307`). |
| `character_creator.propose_relationships` | `character_creator.py:348-350` | `relationships` | `characterId` only | **Tool always fails**: `relationships` always `None` -> `raise ValueError("relationships array is required")` (`character_creator.py:350`). |
| `references.attach` | `scene_references_w6p.py:110-111` | `usageModes`, `referenceRoles` | `assetId`, `scopeType`, `scopeId`, `referenceType`, `identityId`, `identityVersionId` | Defaults to `["informational"]`/`[]` — model cannot set usage modes or roles. |
| `propose_asset_library_assignment` | `library.py:144` | `folderId` | `assetId`, `systemKey`, `path`, `query`, `entityType`, `entityName`, `entityId`, `override` | `folderId` always `None` — dead code path in handler. |

**Tools that always fail or silently persist bad data (derived from the table above):**

1. `character_creator.propose_traits` (`character_creator.py:307`) — **always raises `ValueError`** because `traits` is stripped by sanitizer. The model can never successfully call this tool.
2. `character_creator.propose_relationships` (`character_creator.py:350`) — **always raises `ValueError`** because `relationships` is stripped.
3. `propose_character_update` (`bible_domain.py:97`) — **silently persists empty `CharacterData`** for new entities while reporting success with a new Bible version number. The version number is a real persisted artifact, but it encodes bad data. This is "success without verifying meaningful state" (Build Law #8/#11 violation).

---

## 4. MAGI Finding (Milestone Decision)

**Finding:** MAGI is the single fully-uncovered native system. No `magi_*` tool is registered in the closed Co-Director tool registry. The native MAGI API exists (`studio-api/app/magi/api.py`, `sequence/store.py`, `composition/service.py`, `readiness.py`, `production_gate.py`), but Co-Director has no read or write tool that operates it. The only mention of `magi` in Co-Director handlers is as a target string in `continuity_w5.py:121` (`target not in ("continuity","identityregistry","timeline","magi","bible")`), which means the continuity workspace can *open* MAGI as a deep-link target but cannot read or mutate MAGI sequences through tools.

**Root cause:** MAGI tooling was never authored in the Co-Director registry. The native MAGI service predates the closed-registry enforcement and was not retrofitted with Co-Director handlers.

**Milestone decision (recorded in this audit):** MAGI is documented as **not-operational via Co-Director**. The operational gate for MAGI is **N/A** for this milestone. **No fictional `magi_*` tools may be exposed to creators** — Build Law #20 (honest capability labels) and Law #8 (no silent behavior) forbid registering placeholder tools that do not perform real work. The creator-facing capability label for MAGI in Co-Director must read **"Unavailable"** or **"Requires Setup"** per Law #20, and the Co-Director system must route any MAGI-related creator intent to a plain-language explanation that MAGI work must be performed in the MAGI editor directly (outside Co-Director) until a future milestone authors real MAGI tools.

**Gate status:** N/A (no operational claim is made; no fictional tools are exposed). This finding is tracked as a c4 repair item only to the extent of ensuring the capability label is honest and the deep-link target continues to open MAGI without implying Co-Director can mutate it.

---

## 5. Legacy Path Drift Risk (m29/timeline coexisting with director_timeline_w46)

**Finding:** The legacy `studio-api/app/codirector/m29/timeline/service.py` path coexists with the current `director_timeline_w46` contract. No Co-Director tool uses the m29 path — all 29 Timeline tools in `director_timeline_tools` import `from ....director_timeline_w46 import orchestrator, service, store` and use `store.save_master(..., bump_revision=True)`. However, the m29 path is still importable and persists to `scene.director_json` (`m29/timeline/service.py:229`), bypassing the batch-owned, revision-guarded w46 contract.

**Root cause:** The m29 timeline service was not removed when `director_timeline_w46` became the authoritative contract. The m29 REST router (`m29/api.py:539-565`) still exposes `approve`/`reject`/`apply` endpoints that operate by `proposal_id` only and derive `project_id` from the proposal itself (`m29/timeline/service.py:141`), creating the cross-project leak risk documented as RISK 3 in `state-isolation-report.md`.

**Drift risk:** If any future handler or router proxies through the m29 path, the authoritative `ToolContext.project_id` guarantee does not apply, and the batch-owned revision guard is bypassed. The m29 path also writes `scene.director_json` directly, which can race with `director_timeline_w46/store.py:save_master` and corrupt the workspace state.

**Verification:** Spot-checked `m29/timeline/service.py:99-247` — `approve` (`:99`) loads by `proposal_id` only; `apply` (`:133`) derives `project_id = prop["projectId"]` from the proposal (`:141`) and writes `scene.director_json` (`:229`) without a revision bump. The w46 `store.py:73` `get_scene` filters `Scene.project_id == project_id AND Scene.id == scene_id` (`:76`), so the current contract is project-scoped; the m29 path is not.

---

## 6. Test / Certification Infrastructure Gaps

### 6.1 No Unified Operational Regression Suite

**Finding:** There is no single regression suite that certifies every native system in a READ -> WRITE -> PERSIST -> VERIFY -> UI-SYNC loop. The existing suites are per-system or per-handler:

- `studio-api/tests/test_codirector*.py` (22 files) — unit/API coverage, focused on the tool registry contract, foundation operations, and intelligence layers. `test_codirector_tools.py` is the core operational-contract test (registry completeness, handler binding, kind-mismatch refusal, schema-version guards, mutation-tool proposal lifecycle).
- `tests/e2e/codirector/*.spec.ts` (37 Playwright specs + 2 helpers files: `audit.ts`, `autonomousCert.ts`) — end-to-end coverage, but each spec targets a specific capability or scenario, not a unified 12-system loop.

**Root cause:** The test tree grew incrementally per feature; no governing suite was authored to assert operational integrity across all 12 native systems in a single traceable run. Build Law #12 (tests prove user workflow) and Law #31 (evidence before completion) require this for milestone certification.

### 6.2 No Independent Operational Verifier

**Finding:** There is no independent verifier that asserts Co-Director operational integrity across all 12 systems. The only cert-style adapter is `studio-api/app/director_timeline_w46/generation/adapters/stub_cert.py` (the `ADEPT_TIMELINE_CERT_STUB` adapter), which provides a deterministic lifecycle controller for the Timeline generation boundary. It is wired through the router cert endpoints. No equivalent stub exists for voice generation, image generation, PoseCraft, MAGI (N/A), or the other native systems.

**Root cause:** The cert-stub pattern was authored for Timeline only and was not generalized. Voice and image generation rely on `ADEPT_MOCK_IMAGEGEN` and `ADEPT_CODIRECTOR_PROVIDER=mock` on/off toggles, which provide mocking but not a deterministic lifecycle controller that can certify the full READ -> WRITE -> PERSIST -> VERIFY -> UI-SYNC loop.

### 6.3 Mock Provider Fixed Scenarios

**Finding:** The mock provider (`studio-api/app/codirector/providers/mock.py`) selects a deterministic reply by `ADEPT_CODIRECTOR_MOCK_SCENARIO` (`mock.py:21`). The scenario set (`mock.py:28-35`) includes `read_tool_success`, `tool_loop_limit`, `malformed_proposal` (`mock.py:252`), and others. `_is_follow_up_turn` (`mock.py:50`) detects the post-tool follow-up so E2E scenarios terminate after one tool. This is sufficient for the scenarios enumerated in the E2E specs but does not exercise the full operational loop for every native system.

**Root cause:** The mock provider is scenario-driven for E2E convenience, not a property-based operational verifier. It cannot certify that an arbitrary native system's READ -> WRITE -> PERSIST -> VERIFY -> UI-SYNC chain is intact.

### 6.4 Cert-Stub Coverage Asymmetry

**Finding:** Cert-stub coverage is asymmetric:

| System | Cert stub | Mock toggle | Deterministic lifecycle? |
|---|---|---|---|
| Timeline | `ADEPT_TIMELINE_CERT_STUB` (`stub_cert.py` + router cert endpoints) | `ADEPT_CODIRECTOR_PROVIDER=mock` | YES |
| Voice generation | None | on/off toggle only | NO |
| Image generation | None | `ADEPT_MOCK_IMAGEGEN` (on/off) | NO |
| PoseCraft | None | N/A | NO |
| MAGI | N/A (no tools) | N/A | N/A |
| Other systems | None | N/A | NO |

**Root cause:** The cert-stub pattern was not propagated beyond Timeline. Voice and image generation have on/off mocking but no deterministic lifecycle controller that can certify the full loop without hitting a real provider/GPU boundary.

### 6.5 Test Inventory (Reference)

`studio-api/tests/test_codirector*.py` (22 files): `test_codirector_tools.py` (M2.2 bounded tool registry — the core operational-contract test), `test_codirector_intelligence.py` (M2.4 production intelligence), `test_codirector_foundation_operations.py` (foundation operations engine), `test_codirector_foundation_pipeline.py` (integration smoke), `test_codirector_foundation_knowledge.py` (creative knowledge framework), `test_codirector_foundation_creative.py` (foundation Phase 2 specialists), `test_codirector_foundation_collaboration.py` (foundation Phase 4 collaboration), `test_codirector_foundation_domains.py` (domain profile catalog), `test_codirector_foundation_production.py` (foundation Phase 3 production roadmap), `test_codirector_foundational_ai.py` (Part A foundational AI listening / DialoguePlan authority), `test_codirector_complete_companion.py` (Part B complete companion & advisory intelligence), `test_codirector_hands_on_partnership.py` (hands-on partnership layer), plus 10 more.

`tests/e2e/codirector/*.spec.ts` (37 specs + 2 helpers files: `audit.ts`, `autonomousCert.ts`).

---

## 7. Repair Recommendations (Mapped to Milestone Phases)

### Phase c4 — Native System Contract Closure + MAGI Documentation

1. **Close the schema/handler mismatch on the 11 tools in §3.** For each tool, either update `ToolDefinition.parameters` to declare the missing keys (so the sanitizer preserves them) or remove the dead reads from the handler. Priority: `character_creator.propose_traits` and `character_creator.propose_relationships` (always-fail), then `propose_character_update` (silent bad-data persist), then the remaining `bible_domain` tools, `references.attach`, `propose_asset_library_assignment`.
2. **Remove the dead/unreachable code block at `director_timeline_tools.py:542-557`.**
3. **Document MAGI as not-operational via Co-Director.** Set the creator-facing capability label to "Unavailable" or "Requires Setup" (Law #20). Ensure the `continuity_w5.py:121` deep-link target continues to open MAGI without implying Co-Director can mutate it. No fictional `magi_*` tools may be registered.
4. **Add a regression test for each closed schema/handler mismatch** (Build Law #13: repair -> regression test). Each test must assert the previously-stripped key now reaches the handler.

### Phase c5 — Cross-System Workflow + UI Synchronization (see companion audit)

See `CODIRECTOR_CROSS_SYSTEM_WORKFLOW_AUDIT.md` for the cross-system workflow inventory, lineage mechanisms, and UI synchronization audit. The native-system repairs that block cross-system workflows (the §3 defects) are tracked here under c4; the cross-system chain repairs are tracked under c5.

### Phase c8 — Test / Certification Infrastructure Unification

1. **Author a unified operational regression suite** that certifies every native system (11 covered + MAGI documented as N/A) in a single READ -> WRITE -> PERSIST -> VERIFY -> UI-SYNC loop. The suite must be runnable in CI without hitting real provider/GPU boundaries.
2. **Generalize the cert-stub pattern** beyond Timeline. Author deterministic lifecycle stubs for voice generation and image generation (and PoseCraft if it gains a generation boundary). The stubs must control the full lifecycle, not just toggle mocking on/off.
3. **Add an independent operational verifier** that asserts Co-Director operational integrity across all 12 systems and emits a binary PASS/FAIL per system. The verifier must not rely on the mock provider's fixed scenario set.
4. **Add a regression test for the m29/timeline drift risk.** Either remove the m29 path (preferred, pending impact analysis per Build Law #6) or add a guard that prevents any Co-Director handler from importing `codirector.m29.timeline.service`. The guard must fail fast at import time.
5. **Add a regression test for the cross-project leak risks** documented as RISKS 1-5 in `state-isolation-report.md` (voice_performance plan/segment lookups, m29 image/timeline/control/render/frame endpoints, m214 approve/confirm endpoints). Each test must assert a stale entity ID from another project is rejected with a 404/403.

---

## 8. Verification Log

Spot-verification of citations against the current tree (2026-08-07). Each entry records the citation, the verification method, and the result. Corrections are recorded where the source report's citation drifted from the current tree.

1. **`registry.py:1180` `_validate_bindings`, `registry.py:1226` `require_kind`** — Verified via `tool-registry-report.md` source; not re-read in this audit (source-of-truth preserved per Build Law 30). No correction.
2. **`continuity_w5.py:121` MAGI target string** — Verified via `native-systems-report.md` source. Not re-read; source-of-truth preserved. No correction.
3. **`bible_domain.py:90` `apply_propose_character_update`, `:97` reads `args.get("data")`, `:105` reads `args.get("data")`** — Re-read `studio-api/app/codirector/tools/handlers/bible_domain.py:75-122`. Confirmed: `apply_propose_character_update` at `:90`; `args.get("data")` at `:97` (new entity branch) and `:105` (merge branch). No correction.
4. **`bible_domain.py:141-142` reads `entityStableId`, `sceneId`** — Re-read `bible_domain.py:136-144`. Confirmed: `apply_propose_canon_record` at `:136`; `args.get("entityStableId")` at `:141`; `args.get("sceneId")` at `:142`. No correction.
5. **`bible_domain.py:162` reads `entityStableId`** — Re-read `bible_domain.py:157-165`. Confirmed: `apply_propose_canon_supersession` at `:157`; `args.get("entityStableId")` at `:162`. No correction.
6. **`bible_domain.py:189-193` reads `entityStableId`, `sceneId`, `expectedValue`, `actualValue`, `resolved`** — Re-read `bible_domain.py:178-196`. Confirmed: `apply_propose_continuity_update` at `:178`; reads at `:189` (`entityStableId`), `:190` (`sceneId`), `:191` (`expectedValue`), `:192` (`actualValue`), `:193` (`resolved`). No correction.
7. **`character_creator.py:307` `raise ValueError("traits array is required")`, `character_creator.py:350` `raise ValueError("relationships array is required")`** — Re-read `character_creator.py:303-350`. Confirmed: `apply_propose_traits` at `:303`; `traits = args.get("traits") or []` at `:305`; `raise ValueError("traits array is required")` at `:307`. `apply_propose_relationships` at `:346`; `rels = args.get("relationships") or []` at `:348`; `raise ValueError("relationships array is required")` at `:350`. No correction.
8. **`m29/timeline/service.py:99` `approve`, `:133` `apply`, `:141` derives `project_id`, `:229` writes `scene.director_json`** — Re-read `m29/timeline/service.py:90-247`. Confirmed: `approve` at `:99`; `apply` at `:133`; `project_id = prop["projectId"]` at `:141`; `scene.director_json = dumps_director_timeline_preserving_embedded(...)` at `:229`. No correction.
9. **`director_timeline_w46/store.py:73` `get_scene`, `:76` filters `Scene.project_id == project_id AND Scene.id == scene_id`** — Re-read `director_timeline_w46/store.py:73-78`. Confirmed: `def get_scene(db, project_id, scene_id)` at `:73`; `.filter(Scene.project_id == project_id, Scene.id == scene_id)` at `:76`. No correction.
10. **`mock.py:21` `ADEPT_CODIRECTOR_MOCK_SCENARIO`, `mock.py:50` `_is_follow_up_turn`, `mock.py:252` `malformed_proposal`** — Re-read `mock.py:45-59` and grep for scenario names. Confirmed: `os.environ.get("ADEPT_CODIRECTOR_MOCK_SCENARIO")` at `:21`; `def _is_follow_up_turn` at `:50`; `elif scenario == "malformed_proposal"` at `:252`; `tool_loop_limit` at `:294`; `read_tool_success` at `:308`. No correction.
11. **`CoDirectorSession.tsx:1757-1761` `adept-timeline-focus` dispatch** — Re-read `CoDirectorSession.tsx:1750-1762`. Confirmed: `window.dispatchEvent(new CustomEvent("adept-timeline-focus", { detail: uiFocus }))` at `:1757-1761`, gated on `result._uiFocus || result.uiFocus` at `:1750`. No correction.
12. **`CoDirectorSession.tsx:1725-1748` `adept:open-character-voice` / `adept:open-audio-studio`** — Re-read `CoDirectorSession.tsx:1713-1749`. Confirmed: `uiAction === "open_voice_performance" || "open_voice_creator"` branch at `:1714`; `adept:open-character-voice` dispatch at `:1725-1732`; `uiAction === "open_audio_studio"` branch at `:1735`; `adept:open-audio-studio` dispatch at `:1741-1748`. No correction.
13. **`CoDirectorSession.tsx:1892-1896` and `:2545-2549` `adept:codirector-plan-workspace-refresh`** — Re-read `CoDirectorSession.tsx:1891-1897` and `:2544-2550`. Confirmed: dispatch at `:1892-1896` (post-stream finalize) gated on `b.projectId`; dispatch at `:2545-2549` (approveProposal) gated on `String(receipt.toolId || "").startsWith("production_plan.")`. No correction.
14. **`CoDirectorSession.tsx:2516` `approveProposal`, `:2524` `api.approveProposal`** — Re-read `CoDirectorSession.tsx:2516-2573`. Confirmed: `const approveProposal = useCallback(...)` at `:2516`; `const receipt = await api.approveProposal(projectId, proposalId)` at `:2524`. No correction.
15. **`director_timeline_w46/generation/adapters/stub_cert.py` existence** — Confirmed via glob: file exists at `studio-api/app/director_timeline_w46/generation/adapters/stub_cert.py`. No correction.

**Corrections made during verification:** None. All 15 spot-verified citations matched the current tree. The source reports (`native-systems-report.md`, `tool-registry-report.md`, `state-isolation-report.md`, `routing-report.md`) were accurate as of 2026-08-07.

---

## 9. Governing Status

This document is the **governing native-system coverage audit** for the Co-Director Operational Integrity Audit milestone (Build Law 30). It supersedes no prior governing document. The companion `CODIRECTOR_CROSS_SYSTEM_WORKFLOW_AUDIT.md` governs the cross-system workflow and UI synchronization scope. Together they form the complete audit record for the milestone. Repairs are tracked in milestone phases c4 (this document), c5 (companion), and c8 (this document, §7).

**Verdict (audit only):** AUDIT COMPLETE. Repairs are tracked; no GO/NO-GO is asserted at the audit stage. The milestone primary agent owns the final binary certification per Build Law #25.

